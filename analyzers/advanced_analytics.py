"""MarketLens Advanced Analytics - Comparison, Trends, Category Performance."""

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List


class ProductComparator:
    """Compare products side by side with scoring."""

    def compare(self, products: List[Dict]) -> Dict[str, Any]:
        if len(products) < 2:
            return {"error": "Need at least 2 products"}

        comparison: Dict[str, Any] = {
            "products": [],
            "winner": None,
            "metrics": {},
        }

        for p in products:
            seller = p.get("seller_info", {})
            entry = {
                "name": p.get("name", p.get("title", "Unknown"))[:50],
                "asin": p.get("asin", "N/A"),
                "price": p.get("price", p.get("amazon_price", 0)),
                "rating": p.get("rating", 0),
                "reviews": p.get("review_count", 0),
                "margin": p.get("estimated_margin_pct", 0),
                "ai_score": p.get("ai_score", 0),
                "consistency": p.get("consistency_score", 0),
                "category": p.get("category", "Unknown"),
                "source": p.get("source", "Unknown"),
                "url": p.get("url", ""),
                "seller_name": seller.get("seller_name", "N/A"),
                "seller_rating": seller.get("seller_rating", 0),
                "fulfillment": "FBA" if seller.get("is_fba") else "FBM",
                "brand": seller.get("brand", "N/A"),
                "monthly_sales_est": seller.get("monthly_sales_est", 0),
                "bsr": seller.get("bsr", 0),
                "num_sellers": seller.get("num_sellers", 0),
                "competition": seller.get("competition_level", "N/A"),
                "is_prime": seller.get("is_prime", False),
                "is_amazon_retail": seller.get("is_amazon_retail", False),
            }
            entry["composite_score"] = self._calc_composite(entry)
            comparison["products"].append(entry)

        comparison["products"].sort(key=lambda x: x["composite_score"], reverse=True)
        comparison["winner"] = comparison["products"][0]["name"]

        comparison["metrics"] = {
            "avg_price": sum(p["price"] for p in comparison["products"]) / len(products),
            "avg_rating": sum(p["rating"] for p in comparison["products"]) / len(products),
            "avg_margin": sum(p["margin"] for p in comparison["products"]) / len(products),
            "price_range": [min(p["price"] for p in comparison["products"]),
                           max(p["price"] for p in comparison["products"])],
        }

        return comparison

    def _calc_composite(self, product: Dict) -> float:
        score = 0.0
        score += min(product.get("ai_score", 0) * 30, 30)
        score += min(product.get("margin", 0) / 2, 25)
        score += min(product.get("rating", 0) / 5 * 15, 15)
        reviews = product.get("reviews", 0)
        if reviews > 10000:
            score += 15
        elif reviews > 1000:
            score += 10
        elif reviews > 100:
            score += 5
        score += min(product.get("consistency", 0) * 15, 15)
        return round(score, 1)


class CategoryAnalyzer:
    """Analyze category performance and trends."""

    def analyze(self, products: List[Dict]) -> Dict[str, Any]:
        categories = defaultdict(list)
        for p in products:
            cat = p.get("category", "Unknown")
            categories[cat].append(p)

        analysis: Dict[str, Any] = {
            "total_categories": len(categories),
            "total_products": len(products),
            "categories": {},
            "top_category": None,
            "category_rankings": [],
        }

        cat_stats = []
        for cat, items in categories.items():
            avg_price = sum(i.get("price", i.get("amazon_price", 0)) for i in items) / max(len(items), 1)
            avg_margin = sum(i.get("estimated_margin_pct", 0) for i in items) / max(len(items), 1)
            avg_ai = sum(i.get("ai_score", 0) for i in items) / max(len(items), 1)
            avg_rating = sum(i.get("rating", 0) for i in items) / max(len(items), 1)
            total_reviews = sum(i.get("review_count", 0) for i in items)

            composite = (avg_ai * 30 + avg_margin / 2 * 25 + avg_rating / 5 * 15 + min(len(items) / 10, 1) * 15 + 10)

            stat = {
                "name": cat,
                "product_count": len(items),
                "avg_price": round(avg_price, 2),
                "avg_margin": round(avg_margin, 1),
                "avg_ai_score": round(avg_ai, 2),
                "avg_rating": round(avg_rating, 1),
                "total_reviews": total_reviews,
                "composite_score": round(composite, 1),
                "opportunity": self._classify_opportunity(avg_margin, avg_ai, len(items)),
            }
            cat_stats.append(stat)
            analysis["categories"][cat] = stat

        cat_stats.sort(key=lambda x: x["composite_score"], reverse=True)
        analysis["category_rankings"] = cat_stats
        if cat_stats:
            analysis["top_category"] = cat_stats[0]["name"]

        return analysis

    def _classify_opportunity(self, margin, ai_score, count):
        if margin >= 40 and ai_score >= 0.7:
            return "HIGH OPPORTUNITY"
        elif margin >= 30 and ai_score >= 0.5:
            return "MODERATE"
        elif count < 5:
            return "UNDERSERVED"
        else:
            return "SATURATED"


class TrendAnalyzer:
    """Analyze product trends and seasonality."""

    def analyze(self, products: List[Dict]) -> Dict[str, Any]:
        trend_data = {
            "price_trends": self._analyze_price_trends(products),
            "rating_distribution": self._analyze_ratings(products),
            "review_velocity": self._analyze_reviews(products),
            "market_gaps": self._find_gaps(products),
        }
        return trend_data

    def _analyze_price_trends(self, products: List[Dict]) -> Dict:
        prices = [p.get("price", p.get("amazon_price", 0)) for p in products if p.get("price", p.get("amazon_price", 0)) > 0]
        if not prices:
            return {"avg": 0, "median": 0, "distribution": {}}

        prices.sort()
        median = prices[len(prices) // 2]
        brackets = {"under_10": 0, "10_to_25": 0, "25_to_50": 0, "50_to_100": 0, "over_100": 0}
        for p in prices:
            if p < 10:
                brackets["under_10"] += 1
            elif p < 25:
                brackets["10_to_25"] += 1
            elif p < 50:
                brackets["25_to_50"] += 1
            elif p < 100:
                brackets["50_to_100"] += 1
            else:
                brackets["over_100"] += 1

        return {
            "avg": round(sum(prices) / len(prices), 2),
            "median": round(median, 2),
            "min": round(min(prices), 2),
            "max": round(max(prices), 2),
            "distribution": brackets,
            "sweet_spot": self._find_price_sweet_spot(products),
        }

    def _find_price_sweet_spot(self, products):
        margin_by_price = defaultdict(list)
        for p in products:
            price = p.get("price", p.get("amazon_price", 0))
            margin = p.get("estimated_margin_pct", 0)
            if price > 0 and margin > 0:
                bracket = "under_10" if price < 10 else "10_to_25" if price < 25 else "25_to_50" if price < 50 else "over_50"
                margin_by_price[bracket].append(margin)

        best_bracket = None
        best_avg = 0
        for bracket, margins in margin_by_price.items():
            avg = sum(margins) / len(margins)
            if avg > best_avg:
                best_avg = avg
                best_bracket = bracket

        return {"bracket": best_bracket, "avg_margin": round(best_avg, 1)}

    def _analyze_ratings(self, products):
        dist = {"5_stars": 0, "4_stars": 0, "3_stars": 0, "below_3": 0}
        for p in products:
            r = p.get("rating", 0)
            if r >= 4.5:
                dist["5_stars"] += 1
            elif r >= 4.0:
                dist["4_stars"] += 1
            elif r >= 3.0:
                dist["3_stars"] += 1
            else:
                dist["below_3"] += 1
        return dist

    def _analyze_reviews(self, products):
        review_tiers = {"new_0_100": 0, "growing_100_1k": 0, "established_1k_10k": 0, "viral_10k_plus": 0}
        for p in products:
            r = p.get("review_count", 0)
            if r < 100:
                review_tiers["new_0_100"] += 1
            elif r < 1000:
                review_tiers["growing_100_1k"] += 1
            elif r < 10000:
                review_tiers["established_1k_10k"] += 1
            else:
                review_tiers["viral_10k_plus"] += 1
        return review_tiers

    def _find_gaps(self, products):
        gaps = []
        categories = defaultdict(list)
        for p in products:
            categories[p.get("category", "Unknown")].append(p)

        for cat, items in categories.items():
            low_review = [i for i in items if i.get("review_count", 0) < 500]
            high_margin = [i for i in items if i.get("estimated_margin_pct", 0) > 40]
            if low_review and high_margin:
                gaps.append({
                    "category": cat,
                    "type": "low_competition_high_margin",
                    "products": len(low_review),
                    "opportunity": "HIGH",
                })

            high_rating_new = [i for i in items if i.get("rating", 0) >= 4.5 and i.get("review_count", 0) < 1000]
            if high_rating_new:
                gaps.append({
                    "category": cat,
                    "type": "rising_products",
                    "products": len(high_rating_new),
                    "opportunity": "MEDIUM",
                })

        return gaps


class ReportGenerator:
    """Generate analysis reports."""

    def generate_summary(self, products: List[Dict], analysis: Dict) -> str:
        report = []
        report.append("=" * 60)
        report.append("MARKETLENS ANALYSIS REPORT")
        report.append("Generated: {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        report.append("=" * 60)
        report.append("")

        report.append("EXECUTIVE SUMMARY")
        report.append("-" * 40)
        report.append(f"Total Products Analyzed: {len(products)}")
        report.append("Categories Covered: {}".format(analysis.get("total_categories", 0)))

        cat_analysis = analysis.get("category_analysis", {})
        if cat_analysis.get("top_category"):
            report.append("Top Category: {}".format(cat_analysis["top_category"]))

        high_ai = len([p for p in products if p.get("ai_score", 0) >= 0.7])
        high_margin = len([p for p in products if p.get("estimated_margin_pct", 0) >= 40])
        report.append(f"High AI Score Products: {high_ai}")
        report.append(f"High Margin Products (40%+): {high_margin}")
        report.append("")

        report.append("TOP 10 PRODUCTS")
        report.append("-" * 40)
        top = sorted(products, key=lambda x: x.get("ai_score", 0), reverse=True)[:10]
        for i, p in enumerate(top, 1):
            seller = p.get("seller_info", {})
            report.append("{}. {} | AI:{:.0%} | Margin:{:.0f}% | £{:.2f}".format(
                i, p.get("name", p.get("title", "N/A"))[:40],
                p.get("ai_score", 0),
                p.get("estimated_margin_pct", 0),
                p.get("price", p.get("amazon_price", 0))
            ))
            report.append("   Seller: {} | {} | {} | Sales: {:,}/mo".format(
                seller.get("seller_name", "N/A"),
                seller.get("fulfillment", "N/A")[:20],
                seller.get("brand", "N/A"),
                seller.get("monthly_sales_est", 0)
            ))
            report.append("   BSR: #{:,} | Sellers: {} | {}".format(
                seller.get("bsr", 0),
                seller.get("num_sellers", 0),
                seller.get("competition_level", "N/A")
            ))
        report.append("")

        report.append("CATEGORY RANKINGS")
        report.append("-" * 40)
        rankings = cat_analysis.get("category_rankings", [])
        for i, cat in enumerate(rankings[:10], 1):
            report.append("{}. {} | {} products | Margin:{:.0f}% | AI:{:.0%} | {}".format(
                i, cat["name"], cat["product_count"],
                cat["avg_margin"], cat["avg_ai_score"], cat["opportunity"]
            ))
        report.append("")

        market_gaps = analysis.get("trend_analysis", {}).get("market_gaps", [])
        if market_gaps:
            report.append("MARKET GAPS IDENTIFIED")
            report.append("-" * 40)
            for gap in market_gaps[:5]:
                report.append("- {} | {} | {} products | {}".format(
                    gap["category"], gap["type"], gap["products"], gap["opportunity"]
                ))

        report.append("")
        report.append("=" * 60)
        report.append("END OF REPORT")
        report.append("=" * 60)

        return "\n".join(report)
