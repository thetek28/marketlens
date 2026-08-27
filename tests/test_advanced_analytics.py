"""Tests for analyzers.advanced_analytics."""

from analyzers.advanced_analytics import (
    CategoryAnalyzer,
    ProductComparator,
    ReportGenerator,
    TrendAnalyzer,
)


def make_product(**overrides):
    base = {
        "name": "Test Product",
        "asin": "B0TEST001",
        "price": 29.99,
        "rating": 4.2,
        "review_count": 500,
        "estimated_margin_pct": 35,
        "ai_score": 0.6,
        "consistency_score": 0.5,
        "category": "Electronics",
        "source": "Amazon",
        "url": "https://example.com",
        "seller_info": {
            "seller_name": "TestSeller",
            "seller_rating": 4.5,
            "is_fba": True,
            "brand": "TestBrand",
            "monthly_sales_est": 1200,
            "bsr": 5000,
            "num_sellers": 3,
            "competition_level": "Low",
            "is_prime": True,
            "is_amazon_retail": False,
        },
    }
    base.update(overrides)
    return base


# ── ProductComparator ──────────────────────────────────────────────


class TestProductComparator:
    def setup_method(self):
        self.comp = ProductComparator()

    def test_error_on_single_product(self):
        result = self.comp.compare([make_product()])
        assert result == {"error": "Need at least 2 products"}

    def test_error_on_empty_products(self):
        result = self.comp.compare([])
        assert result == {"error": "Need at least 2 products"}

    def test_compare_returns_all_fields(self):
        p1 = make_product(name="Alpha", price=10)
        p2 = make_product(name="Beta", price=20)
        result = self.comp.compare([p1, p2])
        assert "products" in result
        assert "winner" in result
        assert "metrics" in result
        assert len(result["products"]) == 2

    def test_compare_winner_is_highest_composite(self):
        p1 = make_product(name="Low", ai_score=0.2, margin=10)
        p2 = make_product(name="High", ai_score=0.9, margin=50)
        result = self.comp.compare([p1, p2])
        assert result["winner"] == "High"

    def test_compare_sorts_by_composite_desc(self):
        p1 = make_product(name="Low", ai_score=0.1, margin=5)
        p2 = make_product(name="Mid", ai_score=0.5, margin=30)
        p3 = make_product(name="High", ai_score=0.9, margin=60)
        result = self.comp.compare([p1, p2, p3])
        scores = [p["composite_score"] for p in result["products"]]
        assert scores == sorted(scores, reverse=True)

    def test_metrics_calculation(self):
        p1 = make_product(price=10, rating=4.0, estimated_margin_pct=20)
        p2 = make_product(price=30, rating=4.8, estimated_margin_pct=40)
        result = self.comp.compare([p1, p2])
        m = result["metrics"]
        assert m["avg_price"] == 20.0
        assert m["avg_rating"] == 4.4
        assert m["avg_margin"] == 30.0
        assert m["price_range"] == [10, 30]

    def test_name_truncated_to_50_chars(self):
        long_name = "A" * 100
        p1 = make_product(name=long_name)
        p2 = make_product(name="Short")
        result = self.comp.compare([p1, p2])
        assert len(result["products"][0]["name"]) == 50

    def test_composite_reviews_over_10000(self):
        p = make_product(review_count=15000)
        entry = p.copy()
        entry["composite_score"] = 0
        score = self.comp._calc_composite(entry)
        assert score > 0

    def test_composite_reviews_tiers(self):
        base = {"ai_score": 0, "margin": 0, "rating": 0, "consistency": 0}
        s10k = self.comp._calc_composite({**base, "reviews": 10001})
        s1k = self.comp._calc_composite({**base, "reviews": 1001})
        s100 = self.comp._calc_composite({**base, "reviews": 101})
        s0 = self.comp._calc_composite({**base, "reviews": 10})
        assert s10k == 15
        assert s1k == 10
        assert s100 == 5
        assert s0 == 0

    def test_composite_capped_ai_score(self):
        base = {"margin": 0, "rating": 0, "reviews": 0, "consistency": 0}
        assert self.comp._calc_composite({**base, "ai_score": 1.0}) == 30
        assert self.comp._calc_composite({**base, "ai_score": 2.0}) == 30

    def test_composite_capped_margin(self):
        base = {"ai_score": 0, "rating": 0, "reviews": 0, "consistency": 0}
        assert self.comp._calc_composite({**base, "margin": 100}) == 25

    def test_composite_capped_rating(self):
        base = {"ai_score": 0, "margin": 0, "reviews": 0, "consistency": 0}
        assert self.comp._calc_composite({**base, "rating": 5.0}) == 15

    def test_composite_capped_consistency(self):
        base = {"ai_score": 0, "margin": 0, "rating": 0, "reviews": 0}
        assert self.comp._calc_composite({**base, "consistency": 1.0}) == 15

    def test_composite_perfect_score(self):
        base = {"ai_score": 1.0, "margin": 50, "rating": 5.0, "reviews": 10001, "consistency": 1.0}
        assert self.comp._calc_composite(base) == 100

    def test_fulfillment_fba_vs_fbm(self):
        p_fba = make_product(name="FBA", seller_info={"is_fba": True})
        p_fbm = make_product(name="FBM", seller_info={"is_fba": False})
        result = self.comp.compare([p_fba, p_fbm])
        fba_entry = [e for e in result["products"] if e["name"] == "FBA"][0]
        fbm_entry = [e for e in result["products"] if e["name"] == "FBM"][0]
        assert fba_entry["fulfillment"] == "FBA"
        assert fbm_entry["fulfillment"] == "FBM"

    def test_missing_fields_defaults(self):
        p1 = {}
        p2 = {"name": "OnlyName"}
        result = self.comp.compare([p1, p2])
        assert len(result["products"]) == 2
        assert result["products"][1]["name"] == "OnlyName"

    def test_title_fallback_for_name(self):
        p = make_product()
        del p["name"]
        p["title"] = "Title Based"
        p2 = make_product(name="Second")
        result = self.comp.compare([p, p2])
        names = [e["name"] for e in result["products"]]
        assert "Title Based" in names


# ── CategoryAnalyzer ───────────────────────────────────────────────


class TestCategoryAnalyzer:
    def setup_method(self):
        self.analyzer = CategoryAnalyzer()

    def test_multiple_categories(self):
        products = [
            make_product(category="Electronics", ai_score=0.8, estimated_margin_pct=45, price=100),
            make_product(category="Home", ai_score=0.4, estimated_margin_pct=20, price=50),
            make_product(category="Electronics", ai_score=0.7, estimated_margin_pct=40, price=80),
        ]
        result = self.analyzer.analyze(products)
        assert result["total_categories"] == 2
        assert result["total_products"] == 3
        assert "Electronics" in result["categories"]
        assert "Home" in result["categories"]

    def test_empty_products(self):
        result = self.analyzer.analyze([])
        assert result["total_categories"] == 0
        assert result["total_products"] == 0
        assert result["top_category"] is None
        assert result["category_rankings"] == []

    def test_single_category(self):
        products = [make_product(category="Books") for _ in range(3)]
        result = self.analyzer.analyze(products)
        assert result["total_categories"] == 1
        assert result["top_category"] == "Books"

    def test_top_category_is_highest_composite(self):
        products = [
            make_product(category="Low", ai_score=0.1, estimated_margin_pct=5, rating=3.0),
            make_product(category="High", ai_score=0.9, estimated_margin_pct=50, rating=5.0),
        ]
        result = self.analyzer.analyze(products)
        assert result["top_category"] == "High"

    def test_category_rankings_sorted_by_composite(self):
        products = [
            make_product(category="A", ai_score=0.2, estimated_margin_pct=10),
            make_product(category="B", ai_score=0.9, estimated_margin_pct=50),
            make_product(category="C", ai_score=0.5, estimated_margin_pct=30),
        ]
        result = self.analyzer.analyze(products)
        scores = [c["composite_score"] for c in result["category_rankings"]]
        assert scores == sorted(scores, reverse=True)

    def test_classify_high_opportunity(self):
        assert self.analyzer._classify_opportunity(40, 0.7, 10) == "HIGH OPPORTUNITY"
        assert self.analyzer._classify_opportunity(50, 0.9, 1) == "HIGH OPPORTUNITY"

    def test_classify_moderate(self):
        assert self.analyzer._classify_opportunity(30, 0.5, 10) == "MODERATE"
        assert self.analyzer._classify_opportunity(35, 0.6, 20) == "MODERATE"

    def test_classify_underserved(self):
        assert self.analyzer._classify_opportunity(20, 0.3, 3) == "UNDERSERVED"
        assert self.analyzer._classify_opportunity(10, 0.2, 4) == "UNDERSERVED"

    def test_classify_saturated(self):
        assert self.analyzer._classify_opportunity(10, 0.2, 10) == "SATURATED"
        assert self.analyzer._classify_opportunity(25, 0.4, 5) == "SATURATED"

    def test_classify_boundary_margin_39_not_high(self):
        assert self.analyzer._classify_opportunity(39, 0.8, 10) != "HIGH OPPORTUNITY"

    def test_classify_boundary_ai_069_not_high(self):
        assert self.analyzer._classify_opportunity(40, 0.69, 10) != "HIGH OPPORTUNITY"

    def test_category_stats_averages(self):
        products = [
            make_product(category="X", price=10, estimated_margin_pct=20, ai_score=0.4, rating=4.0, review_count=100),
            make_product(category="X", price=30, estimated_margin_pct=40, ai_score=0.8, rating=4.8, review_count=200),
        ]
        result = self.analyzer.analyze(products)
        cat = result["categories"]["X"]
        assert cat["avg_price"] == 20.0
        assert cat["avg_margin"] == 30.0
        assert cat["avg_ai_score"] == 0.6
        assert cat["total_reviews"] == 300
        assert cat["product_count"] == 2

    def test_default_category_unknown(self):
        p1 = make_product()
        p2 = make_product()
        del p1["category"]
        del p2["category"]
        result = self.analyzer.analyze([p1, p2])
        assert "Unknown" in result["categories"]


# ── TrendAnalyzer ──────────────────────────────────────────────────


class TestTrendAnalyzer:
    def setup_method(self):
        self.analyzer = TrendAnalyzer()

    def test_empty_products(self):
        result = self.analyzer.analyze([])
        assert result["price_trends"]["avg"] == 0
        assert result["price_trends"]["median"] == 0
        assert result["price_trends"]["distribution"] == {}
        assert result["market_gaps"] == []

    def test_price_distribution_buckets(self):
        products = [
            make_product(price=5),
            make_product(price=15),
            make_product(price=35),
            make_product(price=75),
            make_product(price=150),
        ]
        result = self.analyzer.analyze(products)
        dist = result["price_trends"]["distribution"]
        assert dist["under_10"] == 1
        assert dist["10_to_25"] == 1
        assert dist["25_to_50"] == 1
        assert dist["50_to_100"] == 1
        assert dist["over_100"] == 1

    def test_price_avg_and_median(self):
        products = [make_product(price=10), make_product(price=20), make_product(price=30)]
        result = self.analyzer.analyze(products)
        assert result["price_trends"]["avg"] == 20.0
        assert result["price_trends"]["min"] == 10
        assert result["price_trends"]["max"] == 30

    def test_price_excludes_zero_prices(self):
        products = [make_product(price=0), make_product(price=50)]
        result = self.analyzer.analyze(products)
        assert result["price_trends"]["avg"] == 50

    def test_price_amazon_price_fallback(self):
        p = make_product()
        del p["price"]
        p["amazon_price"] = 42.0
        result = self.analyzer.analyze([p])
        assert result["price_trends"]["avg"] == 42.0

    def test_sweet_spot_finding(self):
        products = [
            make_product(price=15, estimated_margin_pct=50),
            make_product(price=15, estimated_margin_pct=60),
            make_product(price=80, estimated_margin_pct=20),
        ]
        result = self.analyzer.analyze(products)
        sweet = result["price_trends"]["sweet_spot"]
        assert sweet["bracket"] == "10_to_25"
        assert sweet["avg_margin"] == 55.0

    def test_sweet_spot_no_valid_products(self):
        products = [make_product(price=0, estimated_margin_pct=0)]
        result = self.analyzer.analyze(products)
        assert "sweet_spot" not in result["price_trends"]

    def test_sweet_spot_over_50_bracket(self):
        products = [
            make_product(price=60, estimated_margin_pct=40),
            make_product(price=200, estimated_margin_pct=50),
        ]
        result = self.analyzer.analyze(products)
        sweet = result["price_trends"]["sweet_spot"]
        assert sweet["bracket"] == "over_50"

    def test_sweet_spot_under_10_bracket(self):
        products = [make_product(price=8, estimated_margin_pct=30)]
        result = self.analyzer.analyze(products)
        sweet = result["price_trends"]["sweet_spot"]
        assert sweet["bracket"] == "under_10"

    def test_sweet_spot_25_to_50_bracket(self):
        products = [make_product(price=30, estimated_margin_pct=45)]
        result = self.analyzer.analyze(products)
        sweet = result["price_trends"]["sweet_spot"]
        assert sweet["bracket"] == "25_to_50"

    def test_rating_distribution(self):
        products = [
            make_product(rating=4.6),
            make_product(rating=4.2),
            make_product(rating=3.5),
            make_product(rating=2.0),
        ]
        result = self.analyzer.analyze(products)
        dist = result["rating_distribution"]
        assert dist["5_stars"] == 1
        assert dist["4_stars"] == 1
        assert dist["3_stars"] == 1
        assert dist["below_3"] == 1

    def test_rating_boundary_4_5_is_5stars(self):
        products = [make_product(rating=4.5), make_product(rating=4.49)]
        result = self.analyzer.analyze(products)
        assert result["rating_distribution"]["5_stars"] == 1
        assert result["rating_distribution"]["4_stars"] == 1

    def test_review_velocity_tiers(self):
        products = [
            make_product(review_count=50),
            make_product(review_count=500),
            make_product(review_count=5000),
            make_product(review_count=20000),
        ]
        result = self.analyzer.analyze(products)
        vel = result["review_velocity"]
        assert vel["new_0_100"] == 1
        assert vel["growing_100_1k"] == 1
        assert vel["established_1k_10k"] == 1
        assert vel["viral_10k_plus"] == 1

    def test_review_boundary_99_is_new(self):
        products = [make_product(review_count=99), make_product(review_count=100)]
        result = self.analyzer.analyze(products)
        assert result["review_velocity"]["new_0_100"] == 1
        assert result["review_velocity"]["growing_100_1k"] == 1

    def test_gap_low_review_high_margin(self):
        products = [
            make_product(category="Niche", review_count=100, estimated_margin_pct=50),
            make_product(category="Niche", review_count=200, estimated_margin_pct=45),
        ]
        result = self.analyzer.analyze(products)
        gaps = [g for g in result["market_gaps"] if g["type"] == "low_competition_high_margin"]
        assert len(gaps) == 1
        assert gaps[0]["opportunity"] == "HIGH"

    def test_gap_rising_products(self):
        products = [
            make_product(category="Rising", rating=4.6, review_count=500),
        ]
        result = self.analyzer.analyze(products)
        gaps = [g for g in result["market_gaps"] if g["type"] == "rising_products"]
        assert len(gaps) == 1
        assert gaps[0]["opportunity"] == "MEDIUM"

    def test_gap_no_low_review_no_gap(self):
        products = [
            make_product(category="Saturated", review_count=5000, estimated_margin_pct=50),
        ]
        result = self.analyzer.analyze(products)
        gaps = [g for g in result["market_gaps"] if g["type"] == "low_competition_high_margin"]
        assert len(gaps) == 0

    def test_gap_high_rating_below_threshold(self):
        products = [make_product(category="X", rating=4.6, review_count=1500)]
        result = self.analyzer.analyze(products)
        gaps = [g for g in result["market_gaps"] if g["type"] == "rising_products"]
        assert len(gaps) == 0

    def test_gap_both_types_in_same_category(self):
        products = [
            make_product(category="Both", review_count=100, estimated_margin_pct=50, rating=4.7),
        ]
        result = self.analyzer.analyze(products)
        types = {g["type"] for g in result["market_gaps"]}
        assert "low_competition_high_margin" in types
        assert "rising_products" in types

    def test_gap_multiple_categories(self):
        products = [
            make_product(category="Cat1", review_count=50, estimated_margin_pct=45),
            make_product(category="Cat2", review_count=50, estimated_margin_pct=45),
        ]
        result = self.analyzer.analyze(products)
        gap_cats = {g["category"] for g in result["market_gaps"]}
        assert "Cat1" in gap_cats
        assert "Cat2" in gap_cats


# ── ReportGenerator ────────────────────────────────────────────────


class TestReportGenerator:
    def setup_method(self):
        self.gen = ReportGenerator()

    def _full_analysis(self, products):
        cat_result = CategoryAnalyzer().analyze(products)
        trend_result = TrendAnalyzer().analyze(products)
        return {
            "total_categories": cat_result["total_categories"],
            "category_analysis": cat_result,
            "trend_analysis": trend_result,
        }

    def test_full_report_basic(self):
        products = [
            make_product(name="Widget", ai_score=0.8, estimated_margin_pct=45, price=29.99),
            make_product(name="Gadget", ai_score=0.5, estimated_margin_pct=30, price=19.99),
        ]
        analysis = self._full_analysis(products)
        report = self.gen.generate_summary(products, analysis)
        assert "MARKETLENS ANALYSIS REPORT" in report
        assert "END OF REPORT" in report
        assert "Widget" in report
        assert "Gadget" in report

    def test_report_product_count(self):
        products = [make_product(name=f"P{i}") for i in range(5)]
        analysis = self._full_analysis(products)
        report = self.gen.generate_summary(products, analysis)
        assert "Total Products Analyzed: 5" in report

    def test_report_with_top_category(self):
        products = [
            make_product(category="Top", ai_score=0.9, estimated_margin_pct=50),
            make_product(category="Low", ai_score=0.1, estimated_margin_pct=5),
        ]
        analysis = self._full_analysis(products)
        report = self.gen.generate_summary(products, analysis)
        assert "Top Category: Top" in report

    def test_report_without_top_category(self):
        analysis = {"total_categories": 0, "category_analysis": {}, "trend_analysis": {}}
        report = self.gen.generate_summary([], analysis)
        assert "Top Category" not in report

    def test_report_with_market_gaps(self):
        products = [
            make_product(category="Gap", review_count=50, estimated_margin_pct=50),
        ]
        analysis = self._full_analysis(products)
        report = self.gen.generate_summary(products, analysis)
        assert "MARKET GAPS IDENTIFIED" in report

    def test_report_without_market_gaps(self):
        products = [make_product(review_count=5000)]
        analysis = self._full_analysis(products)
        report = self.gen.generate_summary(products, analysis)
        assert "MARKET GAPS IDENTIFIED" not in report

    def test_report_empty_products(self):
        analysis = {
            "total_categories": 0,
            "category_analysis": {"category_rankings": []},
            "trend_analysis": {"market_gaps": []},
        }
        report = self.gen.generate_summary([], analysis)
        assert "Total Products Analyzed: 0" in report
        assert "END OF REPORT" in report

    def test_report_high_ai_and_margin_counts(self):
        products = [
            make_product(ai_score=0.8, estimated_margin_pct=45),
            make_product(ai_score=0.3, estimated_margin_pct=20),
            make_product(ai_score=0.9, estimated_margin_pct=50),
        ]
        analysis = self._full_analysis(products)
        report = self.gen.generate_summary(products, analysis)
        assert "High AI Score Products: 2" in report
        assert "High Margin Products (40%+): 2" in report

    def test_report_top_10_limited(self):
        products = [make_product(name=f"P{i:02d}", ai_score=i / 10) for i in range(15)]
        analysis = self._full_analysis(products)
        report = self.gen.generate_summary(products, analysis)
        for i in range(1, 11):
            assert f"{i}." in report

    def test_report_category_rankings(self):
        products = [
            make_product(category="Best", ai_score=0.9, estimated_margin_pct=50),
            make_product(category="Best", ai_score=0.85, estimated_margin_pct=45),
            make_product(category="Worst", ai_score=0.1, estimated_margin_pct=5),
        ]
        analysis = self._full_analysis(products)
        report = self.gen.generate_summary(products, analysis)
        assert "CATEGORY RANKINGS" in report
        assert "Best" in report
        assert "Worst" in report

    def test_report_seller_info_lines(self):
        products = [make_product(name="TestItem")]
        analysis = self._full_analysis(products)
        report = self.gen.generate_summary(products, analysis)
        assert "TestSeller" in report
        assert "TestBrand" in report

    def test_report_title_fallback(self):
        p = make_product(name="Original")
        del p["name"]
        p["title"] = "TitleName"
        analysis = self._full_analysis([p])
        report = self.gen.generate_summary([p], analysis)
        assert "TitleName" in report

    def test_report_contains_date(self):
        analysis = {"total_categories": 0, "category_analysis": {"category_rankings": []}, "trend_analysis": {}}
        report = self.gen.generate_summary([], analysis)
        assert "Generated:" in report
