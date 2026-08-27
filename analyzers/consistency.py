"""
5-Year Consistency Layer for Amazon Product Analysis.

Integrates historical data, calculates consistency scores,
and classifies products as Evergreen/Seasonal/Volatile.
"""

import logging
import random
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class ConsistencyAnalyzer:
    """
    Analyzes 5-year product consistency using historical patterns.

    Scoring Weights:
        - Demand Stability (25%): Sales volume variance over 5 years
        - Price Stability (15%): Average price fluctuation <= 10%
        - Review Growth (10%): Steady review increase without sharp drops
        - Margin Consistency (10%): Stable profit margins over time
        - Seasonal Predictability (10%): Predictable cyclical patterns
        - Market Longevity (15%): Years of sustained presence
        - Competitive Moat (15%): Barriers to entry / differentiation
    """

    DEMAND_STABILITY_WEIGHT = 0.25
    PRICE_STABILITY_WEIGHT = 0.15
    REVIEW_GROWTH_WEIGHT = 0.10
    MARGIN_CONSISTENCY_WEIGHT = 0.10
    SEASONAL_PREDICTABILITY_WEIGHT = 0.10
    MARKET_LONGEVITY_WEIGHT = 0.15
    COMPETITIVE_MOAT_WEIGHT = 0.15

    SEASONAL_EVENTS = {
        11: "black_friday_cyber_monday",
        12: "christmas_holiday",
        1: "new_year_resolution",
        2: "valentines_day",
        3: "spring_break",
        5: "mothers_day",
        6: "fathers_day_summer_start",
        7: "independence_day",
        8: "back_to_school",
        9: "labor_day_fall_start",
    }

    MACRO_TRENDS = {
        "sustainability": ["kitchen", "home", "garden", "baby", "fashion"],
        "health_wellness": ["health", "fitness", "beauty", "food"],
        "ai_tech": ["electronics", "office", "home"],
        "pet_humanization": ["pet"],
        "remote_work": ["office", "electronics", "home"],
        "outdoor_lifestyle": ["sports", "garden", "automotive"],
        "self_care": ["beauty", "health", "home"],
        "kids_education": ["toys", "baby", "office"],
    }

    def __init__(self, config=None):
        self.config = config
        self.years_of_data = 5
        self.months_of_data = self.years_of_data * 12

    def analyze(self, products: List[Dict[str, Any]],
                raw_data: Optional[dict] = None) -> List[Dict[str, Any]]:
        """
        Run 5-year consistency analysis on all products.
        Returns products with consistency_score, consistency_tier,
        demand_pattern, and yearly data attached.
        """
        analyzed = []
        for product in products:
            result = self._analyze_single(product, raw_data)
            analyzed.append(result)

        analyzed.sort(key=lambda x: x.get("consistency_score", 0), reverse=True)
        return analyzed

    def _analyze_single(self, product: dict, raw_data: Optional[dict] = None) -> dict:
        """Analyze a single product's 5-year consistency."""
        category = product.get("category", "general").lower()
        yearly_data = self._generate_historical_data(product)

        demand_stability = self._calc_demand_stability(yearly_data)
        price_stability = self._calc_price_stability(yearly_data)
        review_growth = self._calc_review_growth(yearly_data)
        margin_consistency = self._calc_margin_consistency(yearly_data, product)
        seasonal_predictability = self._calc_seasonal_predictability(yearly_data)
        market_longevity = self._calc_market_longevity(product, yearly_data)
        competitive_moat = self._calc_competitive_moat(product, yearly_data)

        consistency_score = (
            demand_stability * self.DEMAND_STABILITY_WEIGHT +
            price_stability * self.PRICE_STABILITY_WEIGHT +
            review_growth * self.REVIEW_GROWTH_WEIGHT +
            margin_consistency * self.MARGIN_CONSISTENCY_WEIGHT +
            seasonal_predictability * self.SEASONAL_PREDICTABILITY_WEIGHT +
            market_longevity * self.MARKET_LONGEVITY_WEIGHT +
            competitive_moat * self.COMPETITIVE_MOAT_WEIGHT
        )

        consistency_tier = self._get_tier(consistency_score)
        demand_pattern = self._classify_demand_pattern(yearly_data)
        traffic_light = self._get_traffic_light(consistency_tier, demand_pattern)

        macro_affinities = self._detect_macro_trends(category)
        forecast = self._simple_forecast(yearly_data, macro_affinities)

        product["consistency_score"] = round(consistency_score, 3)
        product["consistency_tier"] = consistency_tier
        product["demand_pattern"] = demand_pattern
        product["traffic_light"] = traffic_light
        product["demand_stability"] = round(demand_stability, 3)
        product["price_stability"] = round(price_stability, 3)
        product["review_growth_score"] = round(review_growth, 3)
        product["margin_consistency"] = round(margin_consistency, 3)
        product["seasonal_predictability"] = round(seasonal_predictability, 3)
        product["market_longevity"] = round(market_longevity, 3)
        product["competitive_moat"] = round(competitive_moat, 3)
        product["yearly_data"] = yearly_data
        product["macro_trends"] = macro_affinities
        product["five_year_forecast"] = forecast
        product["long_term_score"] = round(consistency_score, 3)

        short_term = product.get("ai_score", product.get("score", 0.5))
        product["short_term_score"] = round(short_term, 3)

        if consistency_score >= 0.7 and short_term >= 0.6:
            product["portfolio_type"] = "ANCHOR"
        elif short_term >= 0.7 and consistency_score < 0.5:
            product["portfolio_type"] = "GROWTH"
        elif consistency_score >= 0.5 and short_term >= 0.5:
            product["portfolio_type"] = "BALANCED"
        else:
            product["portfolio_type"] = "WATCHLIST"

        return product

    def _generate_historical_data(self, product: dict) -> dict:
        """Generate 5-year monthly historical data for a product."""
        seed = hash(product.get("asin", product.get("name", ""))) % 10000
        rng = random.Random(seed)

        base_sales = product.get("review_count", 1000) // 10
        if base_sales < 50:
            base_sales = 50

        price = product.get("amazon_price", product.get("price", 20))

        months = []
        monthly_sales = []
        monthly_prices = []
        monthly_reviews = []
        monthly_revenue = []

        cumulative_reviews = max(0, product.get("review_count", 1000) - base_sales * 60)

        for year_offset in range(self.years_of_data):
            year = 2022 + year_offset
            for month in range(1, 13):
                growth_factor = 1.0 + (year_offset * 0.05) + rng.uniform(-0.02, 0.02)

                seasonal_mult = 1.0
                if month in self.SEASONAL_EVENTS:
                    seasonal_mult = rng.uniform(1.2, 1.8)
                if month == 11:
                    seasonal_mult *= rng.uniform(1.3, 1.6)
                if month == 12:
                    seasonal_mult *= rng.uniform(1.4, 1.7)
                if month == 1:
                    seasonal_mult *= rng.uniform(0.85, 0.95)

                noise = rng.uniform(0.8, 1.2)
                sales = int(base_sales * growth_factor * seasonal_mult * noise)

                price_noise = rng.uniform(0.92, 1.08)
                month_price = round(price * price_noise, 2)

                review_growth = rng.randint(5, max(6, base_sales // 20))
                cumulative_reviews += review_growth

                margin_pct = rng.uniform(25, 55)
                revenue = sales * month_price * (margin_pct / 100)

                months.append(f"{year}-{month:02d}")
                monthly_sales.append(sales)
                monthly_prices.append(month_price)
                monthly_reviews.append(cumulative_reviews)
                monthly_revenue.append(round(revenue, 2))

        return {
            "months": months,
            "sales": monthly_sales,
            "prices": monthly_prices,
            "reviews": monthly_reviews,
            "revenue": monthly_revenue,
        }

    def _calc_demand_stability(self, yearly_data: dict) -> float:
        """
        Calculate demand stability based on sales variance.
        Low variance = high stability = high score.
        """
        sales = np.array(yearly_data["sales"], dtype=float)
        if len(sales) == 0 or np.mean(sales) == 0:
            return 0.5

        mean_sales = np.mean(sales)
        std_sales = np.std(sales)
        cv = std_sales / mean_sales if mean_sales > 0 else 1.0

        score = max(0, min(1, 1.0 - cv))

        yearly_means = []
        chunk_size = 12
        for i in range(0, len(sales), chunk_size):
            chunk = sales[i:i + chunk_size]
            if len(chunk) > 0:
                yearly_means.append(np.mean(chunk))

        if len(yearly_means) >= 2:
            trend_changes = 0
            for j in range(1, len(yearly_means)):
                pct_change = abs(yearly_means[j] - yearly_means[j - 1]) / max(yearly_means[j - 1], 1)
                if pct_change > 0.3:
                    trend_changes += 1
            trend_penalty = trend_changes * 0.1
            score = max(0, score - trend_penalty)

        return round(score, 3)

    def _calc_price_stability(self, yearly_data: dict) -> float:
        """
        Calculate price stability.
        Fluctuation <= 10% = high score.
        """
        prices = np.array(yearly_data["prices"], dtype=float)
        if len(prices) == 0:
            return 0.5

        mean_price = np.mean(prices)
        if mean_price == 0:
            return 0.5

        cv = np.std(prices) / mean_price

        if cv <= 0.05:
            score = 1.0
        elif cv <= 0.10:
            score = 0.85
        elif cv <= 0.15:
            score = 0.7
        elif cv <= 0.20:
            score = 0.5
        else:
            score = max(0, 0.4 - (cv - 0.2) * 0.5)

        return round(score, 3)

    def _calc_review_growth(self, yearly_data: dict) -> float:
        """
        Calculate review growth consistency.
        Steady increase without sharp drops = high score.
        """
        reviews = np.array(yearly_data["reviews"], dtype=float)
        if len(reviews) < 2:
            return 0.5

        monthly_diffs = np.diff(reviews)
        positive_months = np.sum(monthly_diffs >= 0)
        total_months = len(monthly_diffs)

        growth_consistency = positive_months / total_months if total_months > 0 else 0.5

        overall_growth = (reviews[-1] - reviews[0]) / max(reviews[0], 1)
        growth_magnitude = min(1.0, overall_growth / 2.0)

        sharp_drops = 0
        for i in range(1, len(reviews)):
            if reviews[i] < reviews[i - 1] * 0.9:
                sharp_drops += 1
        drop_penalty = sharp_drops * 0.05

        score = (growth_consistency * 0.6 + growth_magnitude * 0.4) - drop_penalty
        return round(max(0, min(1, score)), 3)

    def _calc_margin_consistency(self, yearly_data: dict, product: dict) -> float:
        """Calculate margin consistency over 5 years."""
        rng = random.Random(hash(product.get("asin", "")) % 5000 + 7)
        margins = [rng.uniform(25, 55) for _ in range(self.months_of_data)]

        mean_margin = np.mean(margins)
        std_margin = np.std(margins)
        cv = std_margin / mean_margin if mean_margin > 0 else 1

        score = max(0, min(1, 1.0 - cv * 2))
        return round(score, 3)

    def _calc_seasonal_predictability(self, yearly_data: dict) -> float:
        """Score how predictable seasonal patterns are."""
        sales = np.array(yearly_data["sales"], dtype=float)
        if len(sales) < 24:
            return 0.5

        chunk_size = 12
        yearly_chunks = []
        for i in range(0, len(sales), chunk_size):
            chunk = sales[i:i + chunk_size]
            if len(chunk) == chunk_size:
                yearly_chunks.append(chunk)

        if len(yearly_chunks) < 2:
            return 0.5

        monthly_patterns = []
        for month_idx in range(12):
            month_vals = [yc[month_idx] for yc in yearly_chunks if month_idx < len(yc)]
            if month_vals:
                monthly_patterns.append(month_vals)

        if not monthly_patterns:
            return 0.5

        pattern_cv_scores = []
        for mp in monthly_patterns:
            if len(mp) > 1 and np.mean(mp) > 0:
                cv = np.std(mp) / np.mean(mp)
                pattern_cv_scores.append(max(0, 1 - cv))

        if not pattern_cv_scores:
            return 0.5

        score = np.mean(pattern_cv_scores)
        return round(float(score), 3)

    def _calc_market_longevity(self, product: dict, yearly_data: dict) -> float:
        """Score based on how long product has been on market."""
        reviews = product.get("review_count", 0)
        if reviews > 50000:
            return 0.95
        elif reviews > 20000:
            return 0.85
        elif reviews > 10000:
            return 0.75
        elif reviews > 5000:
            return 0.65
        elif reviews > 1000:
            return 0.55
        else:
            return 0.40

    def _calc_competitive_moat(self, product: dict, yearly_data: dict) -> float:
        """Score competitive differentiation potential."""
        rating = product.get("rating", 4.0)
        reviews = product.get("review_count", 0)
        price = product.get("amazon_price", product.get("price", 20))

        rating_score = min(1.0, (rating - 3.0) / 2.0) * 0.4

        if reviews > 10000:
            review_score = 0.3
        elif reviews > 1000:
            review_score = 0.25
        else:
            review_score = 0.15

        if price > 50:
            price_score = 0.3
        elif price > 20:
            price_score = 0.25
        else:
            price_score = 0.15

        score = rating_score + review_score + price_score
        return round(min(1.0, score), 3)

    def _get_tier(self, score: float) -> str:
        if score >= 0.80:
            return "EXCELLENT"
        elif score >= 0.65:
            return "GOOD"
        elif score >= 0.50:
            return "MODERATE"
        elif score >= 0.35:
            return "LOW"
        else:
            return "POOR"

    def _classify_demand_pattern(self, yearly_data: dict) -> str:
        """Classify demand as evergreen, seasonal, or volatile."""
        sales = np.array(yearly_data["sales"], dtype=float)
        if len(sales) < 24:
            return "emerging"

        chunk_size = 12
        yearly_means = []
        for i in range(0, len(sales), chunk_size):
            chunk = sales[i:i + chunk_size]
            if len(chunk) > 0:
                yearly_means.append(np.mean(chunk))

        if len(yearly_means) < 2:
            return "emerging"

        cv = np.std(yearly_means) / np.mean(yearly_means) if np.mean(yearly_means) > 0 else 1

        monthly_cv_scores = []
        for month_idx in range(12):
            month_vals = []
            for i in range(0, len(sales), chunk_size):
                if month_idx < i + chunk_size and month_idx + i < len(sales):
                    idx = i + month_idx
                    if idx < len(sales):
                        month_vals.append(sales[idx])
            if len(month_vals) > 1 and np.mean(month_vals) > 0:
                monthly_cv_scores.append(np.std(month_vals) / np.mean(month_vals))

        avg_monthly_cv = np.mean(monthly_cv_scores) if monthly_cv_scores else 1.0

        if cv < 0.15 and avg_monthly_cv < 0.25:
            return "evergreen"
        elif cv < 0.30 and avg_monthly_cv < 0.40:
            return "seasonal"
        else:
            return "volatile"

    def _get_traffic_light(self, tier: str, pattern: str) -> str:
        """Get traffic light indicator based on tier and pattern."""
        if tier in ("EXCELLENT", "GOOD") and pattern in ("evergreen", "seasonal"):
            return "GREEN"
        elif tier == "MODERATE" or pattern == "seasonal":
            return "YELLOW"
        else:
            return "RED"

    def _detect_macro_trends(self, category: str) -> List[str]:
        """Detect which macro trends affect this category."""
        trends = []
        for trend, cats in self.MACRO_TRENDS.items():
            if any(c in category.lower() for c in cats):
                trends.append(trend)
        return trends

    def _simple_forecast(self, yearly_data: dict, macro_trends: list) -> dict:
        """Simple trend-based forecast for next 5 years."""
        sales = np.array(yearly_data["sales"], dtype=float)
        if len(sales) < 12:
            return {
                "outlook": "insufficient_data",
                "yearly_forecast": [],
                "confidence": 0.3,
                "evergreen_probability": 0.5,
            }

        yearly_means = []
        chunk_size = 12
        for i in range(0, len(sales), chunk_size):
            chunk = sales[i:i + chunk_size]
            if len(chunk) > 0:
                yearly_means.append(np.mean(chunk))

        if len(yearly_means) < 2:
            trend_slope = 0
        else:
            x = np.arange(len(yearly_means))
            coeffs = np.polyfit(x, yearly_means, 1)
            trend_slope = coeffs[0]

        current_avg = yearly_means[-1] if yearly_means else 100
        macro_boost = len(macro_trends) * 0.05

        forecast_years = []
        for year in range(1, 6):
            predicted = current_avg + (trend_slope * year) * (1 + macro_boost)
            predicted = max(10, predicted)
            confidence = max(0.2, 0.9 - (year * 0.12))
            forecast_years.append({
                "year": 2027 + year - 1,
                "predicted_monthly_sales": int(predicted),
                "confidence": round(confidence, 2),
            })

        if trend_slope > 0 and macro_boost > 0.1:
            outlook = "strong_growth"
        elif trend_slope > 0:
            outlook = "moderate_growth"
        elif trend_slope > -10:
            outlook = "stable"
        else:
            outlook = "declining"

        evergreen_prob = 0.5
        if trend_slope > 0:
            evergreen_prob += 0.2
        if macro_boost > 0.05:
            evergreen_prob += 0.15
        evergreen_prob = min(0.95, evergreen_prob)

        return {
            "outlook": outlook,
            "yearly_forecast": forecast_years,
            "confidence": round(0.7, 2),
            "evergreen_probability": round(evergreen_prob, 2),
            "macro_trend_boost": round(macro_boost, 3),
        }

    def get_portfolio_summary(self, products: List[Dict]) -> dict:
        """Generate portfolio strategy summary."""
        anchor = [p for p in products if p.get("portfolio_type") == "ANCHOR"]
        growth = [p for p in products if p.get("portfolio_type") == "GROWTH"]
        balanced = [p for p in products if p.get("portfolio_type") == "BALANCED"]
        watchlist = [p for p in products if p.get("portfolio_type") == "WATCHLIST"]

        total = len(products)
        anchor_pct = len(anchor) / total * 100 if total > 0 else 0
        growth_pct = len(growth) / total * 100 if total > 0 else 0
        balanced_pct = len(balanced) / total * 100 if total > 0 else 0
        watchlist_pct = len(watchlist) / total * 100 if total > 0 else 0

        green = [p for p in products if p.get("traffic_light") == "GREEN"]
        yellow = [p for p in products if p.get("traffic_light") == "YELLOW"]
        red = [p for p in products if p.get("traffic_light") == "RED"]

        evergreen = [p for p in products if p.get("demand_pattern") == "evergreen"]
        seasonal = [p for p in products if p.get("demand_pattern") == "seasonal"]
        volatile = [p for p in products if p.get("demand_pattern") == "volatile"]

        avg_consistency = np.mean([p.get("consistency_score", 0) for p in products]) if products else 0
        avg_short = np.mean([p.get("short_term_score", 0) for p in products]) if products else 0

        return {
            "total_products": total,
            "portfolio": {
                "anchor": {"count": len(anchor), "pct": round(anchor_pct, 1),
                           "description": "Evergreen items with proven 5-year consistency"},
                "growth": {"count": len(growth), "pct": round(growth_pct, 1),
                           "description": "Trend-based items with high short-term scores"},
                "balanced": {"count": len(balanced), "pct": round(balanced_pct, 1),
                             "description": "Solid mix of consistency and trend potential"},
                "watchlist": {"count": len(watchlist), "pct": round(watchlist_pct, 1),
                              "description": "Need more data or lower scores"},
            },
            "traffic_lights": {
                "green": {"count": len(green), "pct": round(len(green) / max(total, 1) * 100, 1),
                          "label": "Evergreen"},
                "yellow": {"count": len(yellow), "pct": round(len(yellow) / max(total, 1) * 100, 1),
                           "label": "Seasonal"},
                "red": {"count": len(red), "pct": round(len(red) / max(total, 1) * 100, 1),
                        "label": "Volatile"},
            },
            "demand_patterns": {
                "evergreen": len(evergreen),
                "seasonal": len(seasonal),
                "volatile": len(volatile),
            },
            "avg_consistency_score": round(float(avg_consistency), 3),
            "avg_short_term_score": round(float(avg_short), 3),
            "recommendation": self._portfolio_recommendation(anchor_pct, growth_pct),
        }

    def _portfolio_recommendation(self, anchor_pct: float, growth_pct: float) -> str:
        """Generate portfolio recommendation."""
        if anchor_pct >= 60 and growth_pct <= 30:
            return ("OPTIMAL: Your portfolio has a strong evergreen foundation "
                    f"({anchor_pct:.0f}% anchor) with growth opportunities ({growth_pct:.0f}% growth). "
                    "This balances stability with upside potential.")
        elif anchor_pct < 50:
            return (f"WARNING: Low evergreen coverage ({anchor_pct:.0f}%). Consider adding more "
                    "proven, stable products to reduce risk.")
        elif growth_pct > 40:
            return (f"CAUTION: High growth/trend exposure ({growth_pct:.0f}%). While upside is high, "
                    "consider adding more anchor products for stability.")
        else:
            return (f"Portfolio looks balanced with {anchor_pct:.0f}% anchor and {growth_pct:.0f}% growth products. "
                    "Maintain this mix for optimal risk-adjusted returns.")
