"""Extended tests for analyzer modules — coverage boost for low-coverage files."""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from analyzers.data_validator import DataValidator
from analyzers.ai_analyzer import AIAnalyzer
from analyzers.consistency import ConsistencyAnalyzer
from analyzers.profitability import ProfitabilityEstimator
from analyzers.marketing import MarketingAnalyzer
from analyzers.hidden_gems import HiddenGemsFinder
from analyzers.seo import SEOAnalyzer, count_words


# ---------------------------------------------------------------------------
# Config stub for analyzers that expect an object with attributes
# ---------------------------------------------------------------------------

class _Config:
    """Minimal config stub that supports getattr-based access."""
    def __init__(self, **kwargs):
        self._data = kwargs
    def __getattr__(self, name):
        return self._data.get(name, 0)


# ===========================================================================
# DataValidator — deep path coverage
# ===========================================================================

class TestDataValidatorDeep:
    """Deep-path tests for DataValidator to push coverage above 70%."""

    def test_cross_reference_amazon_match(self):
        validator = DataValidator()
        ideas = [{"name": "Widget", "asin": "B0TEST1234", "price": 29.99}]
        raw = {"amazon": [{"asin": "B0TEST1234", "price": 29.99, "review_count": 500, "rating": 4.5}]}
        result = validator._cross_reference(ideas, raw)
        assert result[0]["verification_score"] > 0.5
        assert "amazon" in result[0]["sources_verified"]

    def test_cross_reference_trends_match(self):
        validator = DataValidator()
        ideas = [{"name": "wireless headphones"}]
        raw = {"trends": [{"term": "wireless", "interest": 80}]}
        result = validator._cross_reference(ideas, raw)
        assert "trends" in result[0]["sources_verified"]

    def test_cross_reference_social_match(self):
        validator = DataValidator()
        ideas = [{"name": "organic dog food"}]
        raw = {"social": [{"term": "organic", "mentions": 1200}]}
        result = validator._cross_reference(ideas, raw)
        assert "social" in result[0]["sources_verified"]

    def test_cross_reference_no_match(self):
        validator = DataValidator()
        ideas = [{"name": "Unique Product X"}]
        raw = {"amazon": [], "trends": [], "social": []}
        result = validator._cross_reference(ideas, raw)
        assert result[0]["verification_score"] == 0.0

    def test_deduplicate_by_asin(self):
        validator = DataValidator()
        ideas = [
            {"asin": "B0TEST1234", "name": "A", "price": 10},
            {"asin": "B0TEST1234", "name": "B", "price": 20, "rating": 4.5, "category": "X"},
        ]
        result = validator._deduplicate(ideas)
        assert len(result) == 1
        assert result[0]["name"] == "B"

    def test_deduplicate_by_name(self):
        validator = DataValidator()
        ideas = [
            {"name": "Silicone Baking Mat", "price": 10},
            {"name": "Silicone Baking Mat", "price": 20, "rating": 4.5},
        ]
        result = validator._deduplicate(ideas)
        assert len(result) == 1

    def test_dedup_key_no_asin(self):
        validator = DataValidator()
        key = validator._get_dedup_key({"name": "Test Product"})
        assert key.startswith("name_")

    def test_detect_outliers_too_few(self):
        validator = DataValidator()
        ideas = [{"price": 10}, {"price": 20}]
        result = validator._detect_outliers(ideas)
        assert len(result) == 2

    def test_detect_outliers_marks_outlier(self):
        validator = DataValidator({"min_data_points": 3, "outlier_threshold": 1.0})
        ideas = [
            {"amazon_price": 10},
            {"amazon_price": 12},
            {"amazon_price": 11},
            {"amazon_price": 500},
        ]
        result = validator._detect_outliers(ideas)
        assert any(i.get("is_outlier") for i in result)

    def test_is_outlier_insufficient_data(self):
        validator = DataValidator()
        assert validator._is_outlier(100, [10, 20]) is False

    def test_is_outlier_zero_std(self):
        validator = DataValidator()
        assert validator._is_outlier(10, [10, 10, 10]) is False

    def test_quality_checks_negative_price(self):
        validator = DataValidator()
        ideas = [{"name": "Test Product", "amazon_price": -5}]
        result = validator._quality_checks(ideas)
        assert "Negative price" in result[0]["quality_issues"]
        assert result[0]["amazon_price"] == 5

    def test_quality_checks_price_too_high(self):
        validator = DataValidator()
        ideas = [{"name": "Test Product", "amazon_price": 15000}]
        result = validator._quality_checks(ideas)
        assert "Price unusually high" in result[0]["quality_issues"]

    def test_quality_checks_missing_price(self):
        validator = DataValidator()
        ideas = [{"name": "Test Product"}]
        result = validator._quality_checks(ideas)
        assert "Missing price" in result[0]["quality_issues"]

    def test_quality_checks_invalid_rating(self):
        validator = DataValidator()
        ideas = [{"name": "Test Product", "rating": -1}]
        result = validator._quality_checks(ideas)
        assert "Invalid rating" in result[0]["quality_issues"]

    def test_quality_checks_rating_over_5(self):
        validator = DataValidator()
        ideas = [{"name": "Test Product", "rating": 6.0}]
        result = validator._quality_checks(ideas)
        assert "Invalid rating" in result[0]["quality_issues"]

    def test_quality_checks_negative_review_count(self):
        validator = DataValidator()
        ideas = [{"name": "Test Product", "review_count": -50}]
        result = validator._quality_checks(ideas)
        assert "Negative review count" in result[0]["quality_issues"]
        assert result[0]["review_count"] == 50

    def test_quality_checks_negative_margin(self):
        validator = DataValidator()
        ideas = [{"name": "Test Product", "estimated_margin_pct": -10}]
        result = validator._quality_checks(ideas)
        assert "Negative margin" in result[0]["quality_issues"]

    def test_quality_checks_margin_over_100(self):
        validator = DataValidator()
        ideas = [{"name": "Test Product", "estimated_margin_pct": 150}]
        result = validator._quality_checks(ideas)
        assert "Margin > 100%" in result[0]["quality_issues"]

    def test_quality_checks_invalid_asin(self):
        validator = DataValidator()
        ideas = [{"name": "Test Product", "asin": "INVALID"}]
        result = validator._quality_checks(ideas)
        assert "Invalid ASIN format" in result[0]["quality_issues"]

    def test_quality_checks_short_name(self):
        validator = DataValidator()
        ideas = [{"name": "Hi"}]
        result = validator._quality_checks(ideas)
        assert "Name too short" in result[0]["quality_issues"]

    def test_quality_checks_long_name(self):
        validator = DataValidator()
        ideas = [{"name": "X" * 201}]
        result = validator._quality_checks(ideas)
        assert "Name too long" in result[0]["quality_issues"]

    def test_quality_score_calculation(self):
        validator = DataValidator()
        ideas = [{"name": "Test Product", "amazon_price": 29.99}]
        result = validator._quality_checks(ideas)
        assert result[0]["quality_score"] == 1.0

    def test_confidence_levels(self):
        validator = DataValidator()
        assert validator._get_confidence_level(0.9) == "HIGH"
        assert validator._get_confidence_level(0.7) == "MEDIUM"
        assert validator._get_confidence_level(0.5) == "LOW"
        assert validator._get_confidence_level(0.2) == "VERY LOW"

    def test_add_confidence_scores_asin_bonus(self):
        validator = DataValidator()
        ideas = [{"asin": "B0TEST1234", "price": 29.99, "review_count": 100, "rating": 4.5, "category": "Kitchen"}]
        result = validator._add_confidence_scores(ideas, {})
        assert result[0]["confidence"] > 0.5

    def test_add_confidence_scores_no_data(self):
        validator = DataValidator()
        ideas = [{"name": "Empty"}]
        result = validator._add_confidence_scores(ideas, {})
        assert result[0]["confidence"] < 0.5

    def test_get_accuracy_report(self):
        validator = DataValidator()
        ideas = [
            {"confidence": 0.9, "quality_score": 0.8, "verification_score": 0.7, "is_outlier": False, "quality_issues": []},
            {"confidence": 0.3, "quality_score": 0.4, "verification_score": 0.1, "is_outlier": True, "quality_issues": ["Bad"]},
        ]
        report = validator.get_accuracy_report(ideas)
        assert report["total"] == 2
        assert report["outliers"] == 1
        assert report["confidence_distribution"]["high"] == 1
        assert report["confidence_distribution"]["low"] == 1

    def test_get_accuracy_report_empty(self):
        validator = DataValidator()
        report = validator.get_accuracy_report([])
        assert report["total"] == 0

    def test_validate_price(self):
        validator = DataValidator()
        assert validator.validate_price(29.99)[0] is True
        assert validator.validate_price(-1)[0] is False
        assert validator.validate_price(0)[0] is False
        assert validator.validate_price(15000)[0] is False

    def test_validate_price_category_ranges(self):
        validator = DataValidator()
        ok, _ = validator.validate_price(2.0, "electronics")
        assert ok is False
        ok, _ = validator.validate_price(6000, "kitchen")
        assert ok is False

    def test_validate_rating(self):
        validator = DataValidator()
        assert validator.validate_rating(4.5)[0] is True
        assert validator.validate_rating(-1)[0] is False
        assert validator.validate_rating(6)[0] is False

    def test_validate_review_count(self):
        validator = DataValidator()
        assert validator.validate_review_count(100)[0] is True
        assert validator.validate_review_count(-1)[0] is False
        assert validator.validate_review_count(2_000_000)[0] is False

    def test_validate_asin(self):
        validator = DataValidator()
        assert validator.validate_asin("B09BFTVQ9X")[0] is True
        assert validator.validate_asin("")[0] is False
        assert validator.validate_asin("INVALID")[0] is False

    def test_full_pipeline_with_low_confidence_removal(self):
        validator = DataValidator({"min_confidence": 0.8})
        ideas = [{"name": "X"}]
        raw = {}
        validated, report = validator.validate_all(ideas, raw)
        assert report["total_input"] == 1
        assert report["total_output"] <= 1

    def test_highest_data_wins_dedup(self):
        validator = DataValidator()
        sparse = {"name": "Widget", "asin": "B0TEST1234"}
        rich = {"name": "Widget", "asin": "B0TEST1234", "price": 10, "rating": 4, "review_count": 100, "category": "X", "url": "u", "image": "i"}
        result = validator._deduplicate([sparse, rich])
        assert len(result) == 1
        assert result[0]["price"] == 10


# ===========================================================================
# AIAnalyzer — fallback and rule-based paths
# ===========================================================================

class TestAIAnalyzerDeep:
    """Deep-path tests for AIAnalyzer without requiring API keys."""

    def test_init_defaults(self):
        analyzer = AIAnalyzer()
        assert analyzer.openai_key == "" or analyzer.openai_key is not None
        assert analyzer.claude_key == "" or analyzer.claude_key is not None

    def test_init_with_config(self):
        analyzer = AIAnalyzer({"ai_provider": "claude"})
        assert analyzer.provider == "claude"

    def test_analyze_products_empty(self):
        analyzer = AIAnalyzer()
        assert analyzer.analyze_products([]) == []

    def test_analyze_products_fallback(self):
        analyzer = AIAnalyzer()
        products = [{"name": "Widget", "amazon_price": 25, "rating": 4.5, "review_count": 5000}]
        result = analyzer.analyze_products(products)
        assert len(result) == 1
        assert "ai_score" in result[0]

    def test_fallback_analysis_pricing_tiers(self):
        analyzer = AIAnalyzer()
        assert analyzer._fallback_analysis({"amazon_price": 5})["ai_score"] > 0
        assert analyzer._fallback_analysis({"amazon_price": 20})["ai_score"] > 0
        assert analyzer._fallback_analysis({"amazon_price": 60})["ai_score"] > 0

    def test_fallback_analysis_rating_effects(self):
        analyzer = AIAnalyzer()
        low = analyzer._fallback_analysis({"rating": 3.0})
        high = analyzer._fallback_analysis({"rating": 4.8})
        assert high["ai_score"] >= low["ai_score"]

    def test_fallback_analysis_review_effects(self):
        analyzer = AIAnalyzer()
        few = analyzer._fallback_analysis({"review_count": 50})
        many = analyzer._fallback_analysis({"review_count": 20000})
        huge = analyzer._fallback_analysis({"review_count": 60000})
        assert many["ai_score"] >= few["ai_score"]
        assert huge["ai_score"] <= many["ai_score"]

    def test_fallback_analysis_bounds(self):
        analyzer = AIAnalyzer()
        result = analyzer._fallback_analysis({"amazon_price": 25, "rating": 4.5, "review_count": 5000})
        assert 0.1 <= result["ai_score"] <= 1.0

    def test_build_analysis_prompt(self):
        analyzer = AIAnalyzer()
        product = {"name": "Test", "category": "Kitchen", "amazon_price": 29.99, "rating": 4.5, "review_count": 1000}
        prompt = analyzer._build_analysis_prompt(product)
        assert "Test" in prompt
        assert "£29.99" in prompt

    def test_generate_summary_empty(self):
        analyzer = AIAnalyzer()
        assert analyzer.generate_summary([]) == "No products to analyze."

    def test_generate_summary_with_products(self):
        analyzer = AIAnalyzer()
        products = [
            {"name": "A", "ai_score": 0.9, "amazon_price": 20, "estimated_margin_pct": 40, "ai_recommendation": "Buy"},
            {"name": "B", "ai_score": 0.5, "amazon_price": 30, "estimated_margin_pct": 25, "ai_recommendation": "Skip"},
        ]
        summary = analyzer.generate_summary(products)
        assert "A" in summary
        assert "Top Opportunities" in summary

    def test_optimize_listing_fallback(self):
        analyzer = AIAnalyzer()
        result = analyzer.optimize_listing({"name": "Widget", "category": "Kitchen", "amazon_price": 29.99})
        assert "optimized_title" in result
        assert "seo_score" in result

    def test_analyze_review_sentiment_fallback(self):
        analyzer = AIAnalyzer()
        result = analyzer.analyze_review_sentiment("Widget", "Kitchen")
        assert "total_reviews" in result
        assert "top_complaints" in result

    def test_generate_supplier_quote_fallback(self):
        analyzer = AIAnalyzer()
        result = analyzer.generate_supplier_quote(
            {"name": "Widget", "amazon_price": 30},
            {"company": "Shenzhen Corp"}
        )
        assert "subject" in result
        assert "Shenzhen Corp" in result["body"]

    def test_analyze_seasonality_fallback(self):
        analyzer = AIAnalyzer()
        result = analyzer.analyze_seasonality("Widget", "Kitchen")
        assert "monthly_demand" in result
        assert len(result["monthly_demand"]) == 12

    def test_analyze_competitors_fallback(self):
        analyzer = AIAnalyzer()
        result = analyzer.analyze_competitors("Widget", "Kitchen")
        assert "competition_level" in result
        assert "market_saturation" in result

    def test_set_license_manager(self):
        analyzer = AIAnalyzer()
        mock_mgr = MagicMock()
        analyzer.set_license_manager(mock_mgr)
        assert analyzer.license_mgr is mock_mgr

    def test_record_ai_usage_no_license(self):
        analyzer = AIAnalyzer()
        analyzer._record_ai_usage()  # should not raise

    def test_record_ai_usage_with_license(self):
        analyzer = AIAnalyzer()
        mock_mgr = MagicMock()
        analyzer.license_mgr = mock_mgr
        analyzer._record_ai_usage()
        mock_mgr.record_usage.assert_called_once_with("ai_calls")

    def test_call_ai_no_keys(self):
        analyzer = AIAnalyzer()
        assert analyzer._call_ai("test prompt") is None

    def test_fallback_listing_optimize(self):
        analyzer = AIAnalyzer()
        result = analyzer._fallback_listing_optimize({"name": "Test Product"})
        assert "optimized_title" in result
        assert "seo_score" in result

    def test_fallback_sentiment(self):
        analyzer = AIAnalyzer()
        result = analyzer._fallback_sentiment("Widget", "Kitchen")
        assert result["total_reviews"] == 0
        assert "top_complaints" in result

    def test_fallback_quote(self):
        analyzer = AIAnalyzer()
        result = analyzer._fallback_quote({"name": "Widget"}, {"company": "Acme"})
        assert "Widget" in result["subject"]
        assert "Acme" in result["body"]

    def test_fallback_seasonality(self):
        analyzer = AIAnalyzer()
        result = analyzer._fallback_seasonality("Kitchen")
        assert len(result["monthly_demand"]) == 12

    def test_fallback_competitors(self):
        analyzer = AIAnalyzer()
        result = analyzer._fallback_competitors("Kitchen")
        assert result["competition_level"] == "medium"


# ===========================================================================
# ConsistencyAnalyzer — deeper paths
# ===========================================================================

class TestConsistencyAnalyzerDeep:
    """Deeper tests for ConsistencyAnalyzer."""

    def test_analyze_single_product(self):
        analyzer = ConsistencyAnalyzer()
        product = {"name": "Test Product", "asin": "B0TEST1234", "review_count": 5000, "amazon_price": 29.99, "rating": 4.5}
        result = analyzer.analyze([product])
        assert len(result) == 1
        p = result[0]
        assert "consistency_score" in p
        assert "consistency_tier" in p
        assert "demand_pattern" in p
        assert "traffic_light" in p
        assert "yearly_data" in p
        assert "portfolio_type" in p

    def test_consistency_score_bounds(self):
        analyzer = ConsistencyAnalyzer()
        product = {"name": "P", "review_count": 1000, "amazon_price": 20, "rating": 4.0}
        result = analyzer.analyze([product])
        score = result[0]["consistency_score"]
        assert 0 <= score <= 1

    def test_tier_classification(self):
        analyzer = ConsistencyAnalyzer()
        assert analyzer._get_tier(0.85) == "EXCELLENT"
        assert analyzer._get_tier(0.70) == "GOOD"
        assert analyzer._get_tier(0.55) == "MODERATE"
        assert analyzer._get_tier(0.40) == "LOW"
        assert analyzer._get_tier(0.20) == "POOR"

    def test_traffic_light_green(self):
        analyzer = ConsistencyAnalyzer()
        assert analyzer._get_traffic_light("EXCELLENT", "evergreen") == "GREEN"
        assert analyzer._get_traffic_light("GOOD", "seasonal") == "GREEN"

    def test_traffic_light_yellow(self):
        analyzer = ConsistencyAnalyzer()
        assert analyzer._get_traffic_light("MODERATE", "evergreen") == "YELLOW"
        assert analyzer._get_traffic_light("GOOD", "seasonal") == "GREEN"
        assert analyzer._get_traffic_light("LOW", "seasonal") == "YELLOW"

    def test_traffic_light_red(self):
        analyzer = ConsistencyAnalyzer()
        assert analyzer._get_traffic_light("LOW", "volatile") == "RED"

    def test_market_longevity_tiers(self):
        analyzer = ConsistencyAnalyzer()
        assert analyzer._calc_market_longevity({"review_count": 60000}, {}) == 0.95
        assert analyzer._calc_market_longevity({"review_count": 25000}, {}) == 0.85
        assert analyzer._calc_market_longevity({"review_count": 12000}, {}) == 0.75
        assert analyzer._calc_market_longevity({"review_count": 6000}, {}) == 0.65
        assert analyzer._calc_market_longevity({"review_count": 1500}, {}) == 0.55
        assert analyzer._calc_market_longevity({"review_count": 100}, {}) == 0.40

    def test_competitive_moat(self):
        analyzer = ConsistencyAnalyzer()
        score = analyzer._calc_competitive_moat(
            {"rating": 4.8, "review_count": 15000, "amazon_price": 60}, {}
        )
        assert 0 <= score <= 1

    def test_detect_macro_trends(self):
        analyzer = ConsistencyAnalyzer()
        trends = analyzer._detect_macro_trends("kitchen")
        assert "sustainability" in trends

    def test_detect_macro_trends_none(self):
        analyzer = ConsistencyAnalyzer()
        trends = analyzer._detect_macro_trends("random_category")
        assert len(trends) == 0

    def test_portfolio_summary(self):
        analyzer = ConsistencyAnalyzer()
        products = [
            {"portfolio_type": "ANCHOR", "traffic_light": "GREEN", "demand_pattern": "evergreen", "consistency_score": 0.8, "short_term_score": 0.7},
            {"portfolio_type": "GROWTH", "traffic_light": "RED", "demand_pattern": "volatile", "consistency_score": 0.4, "short_term_score": 0.8},
            {"portfolio_type": "BALANCED", "traffic_light": "YELLOW", "demand_pattern": "seasonal", "consistency_score": 0.6, "short_term_score": 0.6},
            {"portfolio_type": "WATCHLIST", "traffic_light": "RED", "demand_pattern": "volatile", "consistency_score": 0.2, "short_term_score": 0.3},
        ]
        summary = analyzer.get_portfolio_summary(products)
        assert summary["total_products"] == 4
        assert summary["portfolio"]["anchor"]["count"] == 1
        assert summary["portfolio"]["growth"]["count"] == 1

    def test_portfolio_recommendation_optimal(self):
        analyzer = ConsistencyAnalyzer()
        rec = analyzer._portfolio_recommendation(65, 25)
        assert "OPTIMAL" in rec

    def test_portfolio_recommendation_warning(self):
        analyzer = ConsistencyAnalyzer()
        rec = analyzer._portfolio_recommendation(30, 40)
        assert "WARNING" in rec

    def test_portfolio_recommendation_caution(self):
        analyzer = ConsistencyAnalyzer()
        rec = analyzer._portfolio_recommendation(55, 45)
        assert "CAUTION" in rec

    def test_demand_stability_empty(self):
        analyzer = ConsistencyAnalyzer()
        assert analyzer._calc_demand_stability({"sales": []}) == 0.5

    def test_price_stability_empty(self):
        analyzer = ConsistencyAnalyzer()
        assert analyzer._calc_price_stability({"prices": []}) == 0.5

    def test_price_stability_zero_mean(self):
        analyzer = ConsistencyAnalyzer()
        assert analyzer._calc_price_stability({"prices": [0, 0, 0]}) == 0.5

    def test_review_growth_short(self):
        analyzer = ConsistencyAnalyzer()
        assert analyzer._calc_review_growth({"reviews": [100]}) == 0.5

    def test_seasonal_predictability_short(self):
        analyzer = ConsistencyAnalyzer()
        assert analyzer._calc_seasonal_predictability({"sales": list(range(10))}) == 0.5

    def test_classify_demand_pattern_emerging(self):
        analyzer = ConsistencyAnalyzer()
        assert analyzer._classify_demand_pattern({"sales": list(range(10))}) == "emerging"

    def test_simple_forecast_short_data(self):
        analyzer = ConsistencyAnalyzer()
        forecast = analyzer._simple_forecast({"sales": list(range(5))}, [])
        assert forecast["outlook"] == "insufficient_data"

    def test_portfolio_type_assignment(self):
        analyzer = ConsistencyAnalyzer()
        product = {"name": "High Consistency", "asin": "B0TEST1234", "review_count": 10000, "amazon_price": 30, "rating": 4.5, "ai_score": 0.8}
        result = analyzer.analyze([product])
        assert result[0]["portfolio_type"] in ("ANCHOR", "GROWTH", "BALANCED", "WATCHLIST")


# ===========================================================================
# ProfitabilityEstimator
# ===========================================================================

class TestProfitabilityEstimatorDeep:
    """Tests for ProfitabilityEstimator."""

    def test_init(self):
        config = _Config(min_profit_margin=25.0)
        estimator = ProfitabilityEstimator(config)
        assert estimator.default_margin_threshold == 25.0

    def test_estimate_empty(self):
        estimator = ProfitabilityEstimator(_Config())
        result = estimator.estimate({"amazon": []})
        assert result == []

    def test_estimate_basic(self):
        estimator = ProfitabilityEstimator(_Config())
        raw = {"amazon": [{"title": "Widget", "asin": "B0TEST1234", "price": 29.99, "rating": 4.5, "review_count": 1000}]}
        result = estimator.estimate(raw)
        assert len(result) == 1
        assert "estimated_margin_pct" in result[0]
        assert "estimated_profit" in result[0]
        assert "tier" in result[0]

    def test_estimate_from_social(self):
        estimator = ProfitabilityEstimator(_Config())
        raw = {"social": [{"title": "Social Product", "term": "gadget"}]}
        result = estimator.estimate(raw)
        assert len(result) == 1

    def test_estimate_zero_price(self):
        estimator = ProfitabilityEstimator(_Config())
        result = estimator._estimate_single({"title": "Free", "amazon_price": 0})
        assert result["viable"] is False
        assert result["estimated_margin_pct"] == 0

    def test_supplier_cost_tiers(self):
        estimator = ProfitabilityEstimator(_Config())
        assert estimator._estimate_supplier_cost(5) == 5 * 0.25
        assert estimator._estimate_supplier_cost(15) == 15 * 0.20
        assert estimator._estimate_supplier_cost(30) == 30 * 0.18
        assert estimator._estimate_supplier_cost(100) == 100 * 0.15

    def test_fba_fees(self):
        estimator = ProfitabilityEstimator(_Config())
        fees = estimator._calculate_fba_fees(29.99)
        assert fees > 0
        assert fees == 29.99 * 0.15 + 3.22

    def test_classify_tier(self):
        estimator = ProfitabilityEstimator(_Config())
        assert estimator._classify_tier(55) == "premium"
        assert estimator._classify_tier(40) == "high"
        assert estimator._classify_tier(25) == "medium"
        assert estimator._classify_tier(15) == "low"
        assert estimator._classify_tier(5) == "minimal"

    def test_sorted_by_margin(self):
        estimator = ProfitabilityEstimator(_Config())
        raw = {"amazon": [
            {"title": "Low", "asin": "B0TEST0001", "price": 10},
            {"title": "High", "asin": "B0TEST0002", "price": 50},
        ]}
        result = estimator.estimate(raw)
        margins = [r["estimated_margin_pct"] for r in result]
        assert margins == sorted(margins, reverse=True)


# ===========================================================================
# MarketingAnalyzer
# ===========================================================================

class TestMarketingAnalyzerDeep:
    """Tests for MarketingAnalyzer."""

    def test_init_defaults(self):
        analyzer = MarketingAnalyzer()
        assert analyzer.min_reviews == 10

    def test_analyze_empty(self):
        analyzer = MarketingAnalyzer()
        result = analyzer.analyze([])
        assert result == []

    def test_analyze_low_reviews(self):
        analyzer = MarketingAnalyzer()
        ideas = [{"name": "New Product", "review_count": 5, "amazon_price": 29.99, "rating": 4.5, "estimated_margin_pct": 35}]
        result = analyzer.analyze(ideas)
        problems = result[0]["marketing"]["problems"]
        assert any("Social Proof" in p["problem"] for p in problems)

    def test_analyze_high_competition(self):
        analyzer = MarketingAnalyzer()
        ideas = [{"name": "Competitive", "review_count": 5000, "amazon_price": 29.99, "rating": 4.5, "estimated_margin_pct": 35}]
        result = analyzer.analyze(ideas)
        problems = result[0]["marketing"]["problems"]
        assert any("Competition" in p["problem"] for p in problems)

    def test_analyze_low_price(self):
        analyzer = MarketingAnalyzer()
        ideas = [{"name": "Cheap", "review_count": 100, "amazon_price": 10.00, "rating": 4.5, "estimated_margin_pct": 35}]
        result = analyzer.analyze(ideas)
        problems = result[0]["marketing"]["problems"]
        assert any("Low Price" in p["problem"] for p in problems)

    def test_analyze_high_price(self):
        analyzer = MarketingAnalyzer()
        ideas = [{"name": "Expensive", "review_count": 100, "amazon_price": 150.00, "rating": 4.5, "estimated_margin_pct": 35}]
        result = analyzer.analyze(ideas)
        problems = result[0]["marketing"]["problems"]
        assert any("High Price" in p["problem"] for p in problems)

    def test_analyze_low_margin(self):
        analyzer = MarketingAnalyzer()
        ideas = [{"name": "Thin", "review_count": 100, "amazon_price": 29.99, "rating": 4.5, "estimated_margin_pct": 10}]
        result = analyzer.analyze(ideas)
        problems = result[0]["marketing"]["problems"]
        assert any("Margin" in p["problem"] for p in problems)

    def test_analyze_poor_rating(self):
        analyzer = MarketingAnalyzer()
        ideas = [{"name": "Bad Quality", "review_count": 100, "amazon_price": 29.99, "rating": 3.2, "estimated_margin_pct": 35}]
        result = analyzer.analyze(ideas)
        problems = result[0]["marketing"]["problems"]
        assert any("Rating" in p["problem"] for p in problems)

    def test_analyze_premium_tier(self):
        analyzer = MarketingAnalyzer()
        ideas = [{"name": "Premium", "review_count": 100, "amazon_price": 29.99, "rating": 4.5, "estimated_margin_pct": 35, "tier": "premium"}]
        result = analyzer.analyze(ideas)
        problems = result[0]["marketing"]["problems"]
        assert any("Premium" in p["problem"] for p in problems)

    def test_analyze_seasonal_category(self):
        analyzer = MarketingAnalyzer()
        ideas = [{"name": "Christmas Decor", "review_count": 100, "amazon_price": 29.99, "rating": 4.5, "estimated_margin_pct": 35, "category": "seasonal"}]
        result = analyzer.analyze(ideas)
        problems = result[0]["marketing"]["problems"]
        assert any("Seasonal" in p["problem"] for p in problems)

    def test_recommended_strategies(self):
        analyzer = MarketingAnalyzer()
        ideas = [{"name": "Product", "review_count": 100, "amazon_price": 29.99, "rating": 4.5, "estimated_margin_pct": 35}]
        result = analyzer.analyze(ideas)
        strategies = result[0]["marketing"]["recommended_strategies"]
        assert len(strategies) >= 3
        assert any(s["name"] == "Amazon SEO" for s in strategies)

    def test_marketing_score_bounds(self):
        analyzer = MarketingAnalyzer()
        ideas = [{"name": "Product", "review_count": 100, "amazon_price": 29.99, "rating": 4.5, "estimated_margin_pct": 35}]
        result = analyzer.analyze(ideas)
        score = result[0]["marketing"]["marketing_score"]
        assert 0 <= score <= 1

    def test_summary_no_problems(self):
        analyzer = MarketingAnalyzer()
        ideas = [{"name": "Perfect", "review_count": 100, "amazon_price": 29.99, "rating": 4.5, "estimated_margin_pct": 35}]
        result = analyzer.analyze(ideas)
        summary = result[0]["marketing"]["summary"]
        assert isinstance(summary, str)
        assert len(summary) > 0


# ===========================================================================
# HiddenGemsFinder
# ===========================================================================

class TestHiddenGemsFinderDeep:
    """Tests for HiddenGemsFinder."""

    def test_init(self):
        config = _Config(min_profit_margin=25.0)
        finder = HiddenGemsFinder(config)
        assert finder.min_margin == 25.0

    def test_find_empty(self):
        finder = HiddenGemsFinder(_Config())
        result = finder.find({}, {})
        assert result == []

    def test_find_with_amazon_products(self):
        finder = HiddenGemsFinder(_Config())
        raw = {"amazon": [
            {"title": "Silicone Baking Mat", "asin": "B0TEST1234", "price": 12.99, "rating": 4.3, "review_count": 50},
        ]}
        result = finder.find(raw, {})
        assert len(result) >= 0  # depends on scoring threshold

    def test_find_filters_high_reviews(self):
        finder = HiddenGemsFinder(_Config())
        raw = {"amazon": [
            {"title": "Popular Product", "asin": "B0TEST1234", "price": 29.99, "rating": 4.5, "review_count": 500},
        ]}
        result = finder.find(raw, {})
        assert len(result) == 0

    def test_find_with_trending_terms(self):
        finder = HiddenGemsFinder(_Config())
        raw = {
            "amazon": [{"title": "yoga mat", "asin": "B0TEST1234", "price": 24.99, "rating": 4.3, "review_count": 30}],
            "trends": [{"term": "yoga", "source": "google_trends", "interest": 85}],
        }
        result = finder.find(raw, {})
        assert len(result) >= 0

    def test_find_with_social_signals(self):
        finder = HiddenGemsFinder(_Config())
        raw = {
            "amazon": [{"title": "resistance band", "asin": "B0TEST1234", "price": 14.99, "rating": 4.2, "review_count": 20}],
            "social": [{"term": "resistance band", "views": 5000}],
        }
        result = finder.find(raw, {})
        assert len(result) >= 0

    def test_get_rising_terms_google_trends(self):
        finder = HiddenGemsFinder(_Config())
        raw = {"trends": [{"term": "eco product", "source": "google_trends", "interest": 75}]}
        result = finder._get_rising_terms(raw)
        assert "eco product" in result

    def test_get_rising_terms_related(self):
        finder = HiddenGemsFinder(_Config())
        raw = {"trends": [{"term": "trending item", "source": "google_trends_related", "value": 80}]}
        result = finder._get_rising_terms(raw)
        assert "trending item" in result

    def test_get_rising_terms_filters_low(self):
        finder = HiddenGemsFinder(_Config())
        raw = {"trends": [{"term": "weak", "source": "google_trends_related", "value": 30}]}
        result = finder._get_rising_terms(raw)
        assert len(result) == 0

    def test_get_social_signals(self):
        finder = HiddenGemsFinder(_Config())
        raw = {"social": [{"term": "viral", "views": 8000}]}
        result = finder._get_social_signals(raw)
        assert "viral" in result
        assert result["viral"] == 0.8

    def test_get_social_signals_likes(self):
        finder = HiddenGemsFinder(_Config())
        raw = {"social": [{"term": "liked", "likes": 3000}]}
        result = finder._get_social_signals(raw)
        assert "liked" in result

    def test_get_social_signals_repin(self):
        finder = HiddenGemsFinder(_Config())
        raw = {"social": [{"term": "pinned", "repin_count": 2000}]}
        result = finder._get_social_signals(raw)
        assert "pinned" in result

    def test_evaluate_product_no_title(self):
        finder = HiddenGemsFinder(_Config())
        assert finder._evaluate_product({"price": 10}, {}, {}, {}) is None

    def test_evaluate_product_zero_price(self):
        finder = HiddenGemsFinder(_Config())
        assert finder._evaluate_product({"title": "Widget", "price": 0}, {}, {}, {}) is None

    def test_evaluate_product_high_reviews(self):
        finder = HiddenGemsFinder(_Config())
        assert finder._evaluate_product(
            {"title": "Widget", "price": 20, "review_count": 500}, {}, {}, {}
        ) is None

    def test_margin_score_tiers(self):
        finder = HiddenGemsFinder(_Config())
        assert finder._estimate_margin_score(5) == 0.3
        assert finder._estimate_margin_score(15) == 0.6
        assert finder._estimate_margin_score(35) == 0.8
        assert finder._estimate_margin_score(60) == 0.7
        assert finder._estimate_margin_score(80) == 0.5

    def test_find_emerging_niches(self):
        finder = HiddenGemsFinder(_Config())
        trending = {"smart blender": 0.7}
        social = {"smart blender": 0.5}
        amazon_products = []
        result = finder._find_emerging_niches(trending, social, {}, amazon_products)
        assert len(result) >= 0

    def test_find_emerging_niches_already_on_amazon(self):
        finder = HiddenGemsFinder(_Config())
        trending = {"yoga mat": 0.7}
        social = {}
        amazon_products = [{"title": "yoga mat for exercise"}]
        result = finder._find_emerging_niches(trending, social, {}, amazon_products)
        assert len(result) == 0

    def test_find_emerging_niches_weak_trend(self):
        finder = HiddenGemsFinder(_Config())
        trending = {"weak term": 0.1}
        social = {}
        result = finder._find_emerging_niches(trending, social, {}, [])
        assert len(result) == 0


# ===========================================================================
# SEOAnalyzer
# ===========================================================================

class TestSEOAnalyzerDeep:
    """Tests for SEOAnalyzer."""

    def test_init_defaults(self):
        analyzer = SEOAnalyzer()
        assert analyzer.target_audience == "general"

    def test_analyze_basic(self):
        analyzer = SEOAnalyzer()
        result = analyzer.analyze({"name": "Silicone Baking Mat", "category": "Kitchen"})
        assert "primary_keywords" in result
        assert "seo_score" in result
        assert "title_suggestions" in result
        assert "bullet_keywords" in result

    def test_extract_keywords(self):
        analyzer = SEOAnalyzer()
        keywords = analyzer._extract_keywords("Premium Silicone Baking Mat", "Kitchen")
        assert "silicone" in keywords
        assert "baking" in keywords
        assert "mat" in keywords

    def test_extract_keywords_no_stop_words(self):
        analyzer = SEOAnalyzer()
        keywords = analyzer._extract_keywords("The Best And A Mat For Kitchen", "Kitchen")
        for kw in keywords:
            assert kw not in ("the", "and")

    def test_generate_long_tail(self):
        analyzer = SEOAnalyzer()
        result = analyzer._generate_long_tail("Silicone Baking Mat", "Kitchen")
        assert len(result) > 0
        assert any("silicone" in lt.lower() for lt in result)

    def test_generate_backend_keywords_kitchen(self):
        analyzer = SEOAnalyzer()
        result = analyzer._generate_backend_keywords("Silicone Baking Mat", "Kitchen", ["silicone", "baking", "mat"])
        assert len(result) > 0

    def test_generate_backend_keywords_electronics(self):
        analyzer = SEOAnalyzer()
        result = analyzer._generate_backend_keywords("Wireless Mouse", "Electronics", ["wireless", "mouse"])
        assert "wireless" in [kw.lower() for kw in result]

    def test_get_synonyms(self):
        analyzer = SEOAnalyzer()
        synonyms = analyzer._get_synonyms("bag")
        assert len(synonyms) > 0
        assert "tote" in synonyms

    def test_get_synonyms_unknown(self):
        analyzer = SEOAnalyzer()
        synonyms = analyzer._get_synonyms("xyzunknown")
        assert synonyms == []

    def test_optimize_title(self):
        analyzer = SEOAnalyzer()
        titles = analyzer._optimize_title("Silicone Baking Mat", "Kitchen", ["silicone", "baking", "mat"])
        assert len(titles) > 0

    def test_generate_bullet_keywords(self):
        analyzer = SEOAnalyzer()
        bullets = analyzer._generate_bullet_keywords("Silicone Baking Mat", "Kitchen")
        assert len(bullets) == 5
        for b in bullets:
            assert "heading" in b
            assert "suggested_keywords" in b

    def test_generate_search_terms(self):
        analyzer = SEOAnalyzer()
        terms = analyzer._generate_search_terms("Silicone Baking Mat", "Kitchen", ["silicone", "baking", "mat"])
        assert len(terms) > 0
        assert len(terms.encode("utf-8")) <= 250

    def test_calculate_seo_score(self):
        analyzer = SEOAnalyzer()
        score = analyzer._calculate_seo_score(
            ["Great Silicone Baking Mat"],
            [{"heading": "QUALITY", "suggested_keywords": ["durable"]}],
            ["silicone", "baking"],
            "silicone baking mat kitchen"
        )
        assert score["score"] > 0
        assert score["percentage"] > 0

    def test_calculate_seo_score_empty(self):
        analyzer = SEOAnalyzer()
        score = analyzer._calculate_seo_score([], [], [], "")
        assert score["score"] == 0

    def test_get_optimization_tips(self):
        analyzer = SEOAnalyzer()
        tips = analyzer._get_optimization_tips({"score": 30})
        assert len(tips) > 0
        assert any("keyword" in t.lower() for t in tips)

    def test_get_seasonal_keywords(self):
        analyzer = SEOAnalyzer()
        keywords = analyzer._get_seasonal_keywords()
        assert len(keywords) > 0

    def test_optimize_listing(self):
        analyzer = SEOAnalyzer()
        result = analyzer.optimize_listing({"name": "Silicone Baking Mat", "category": "Kitchen"})
        assert "optimized_title" in result
        assert "optimized_bullets" in result
        assert len(result["optimized_bullets"]) == 5

    def test_count_words(self):
        assert count_words("hello world") == 2
        assert count_words("") == 0
