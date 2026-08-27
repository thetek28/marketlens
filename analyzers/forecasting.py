"""
Time-Series Forecasting Engine for Amazon Products.

Uses simplified Prophet/ARIMA-style forecasting to project
demand curves for the next 5 years.
"""

import logging
import random
from typing import Any, Dict, List

import numpy as np

logger = logging.getLogger(__name__)


class ForecastingEngine:
    """
    Projects product demand over 5 years using time-series models.

    Models:
        - Trend Analysis: Linear/polynomial trend fitting
        - Seasonal Decomposition: Monthly pattern extraction
        - Moving Averages: Short/medium/long-term smoothing
        - Macro Trend Overlay: External factor adjustments
    """

    SEASONAL_PATTERNS = {
        "kitchen": {11: 1.5, 12: 1.6, 1: 0.9, 6: 1.1, 7: 1.0},
        "electronics": {11: 1.4, 12: 1.5, 1: 0.8, 8: 1.2, 9: 1.1},
        "beauty": {11: 1.3, 12: 1.4, 2: 1.2, 5: 1.1},
        "home": {3: 1.2, 4: 1.1, 5: 1.2, 11: 1.3, 12: 1.4},
        "fitness": {1: 1.6, 12: 1.1, 5: 1.2, 6: 1.1, 9: 1.1},
        "pet": {11: 1.2, 12: 1.3, 4: 1.1, 8: 1.1},
        "health": {1: 1.4, 12: 1.2, 4: 1.1, 9: 1.1, 11: 1.1},
        "toys": {11: 1.8, 12: 2.0, 6: 1.1, 8: 1.1},
        "baby": {11: 1.3, 12: 1.3, 5: 1.1, 8: 1.2, 1: 1.1},
        "sports": {4: 1.2, 5: 1.2, 6: 1.3, 7: 1.2, 9: 1.1},
        "automotive": {3: 1.1, 5: 1.1, 11: 1.2, 12: 1.2, 6: 1.1},
        "fashion": {11: 1.3, 12: 1.4, 2: 1.1, 8: 1.1, 9: 1.2},
        "garden": {3: 1.3, 4: 1.4, 5: 1.3, 6: 1.2, 9: 1.1},
        "office": {8: 1.3, 9: 1.2, 1: 1.1, 11: 1.1, 12: 1.1},
        "tools": {5: 1.1, 6: 1.1, 11: 1.3, 12: 1.2, 3: 1.1},
    }

    MACRO_GROWTH_RATES = {
        "sustainability": 0.08,
        "health_wellness": 0.10,
        "ai_tech": 0.15,
        "pet_humanization": 0.12,
        "remote_work": 0.06,
        "outdoor_lifestyle": 0.07,
        "self_care": 0.09,
        "kids_education": 0.05,
    }

    def __init__(self, config=None):
        self.config = config
        self.forecast_years = 5

    def forecast_product(self, product: dict) -> dict:
        """Generate 5-year forecast for a single product."""
        category = product.get("category", "general").lower()
        yearly_data = product.get("yearly_data", {})
        macro_trends = product.get("macro_trends", [])
        consistency_score = product.get("consistency_score", 0.5)

        if not yearly_data or not yearly_data.get("sales"):
            return self._default_forecast(product)

        sales = np.array(yearly_data["sales"], dtype=float)


        trend = self._fit_trend(sales)
        seasonal = self._extract_seasonality(sales, category)

        macro_growth: float = 0
        for trend_name in macro_trends:
            macro_growth += self.MACRO_GROWTH_RATES.get(trend_name, 0)

        yearly_forecast = []

        for year in range(1, self.forecast_years + 1):
            year_sales = []
            for month in range(1, 13):
                trend_component = trend["slope"] * (len(sales) + (year - 1) * 12 + month) + trend["intercept"]
                seasonal_component = seasonal.get(month, 1.0)
                macro_component = 1.0 + (macro_growth * year * 0.3)

                predicted = trend_component * seasonal_component * macro_component
                predicted = max(5, predicted)

                noise = random.uniform(0.95, 1.05)
                predicted *= noise

                year_sales.append(int(predicted))

            avg_monthly = int(np.mean(year_sales))
            total_yearly = sum(year_sales)

            confidence = max(0.25, 0.85 - (year * 0.1))
            if consistency_score > 0.7:
                confidence = min(0.95, confidence + 0.1)

            yearly_forecast.append({
                "year": 2026 + year,
                "monthly_avg": avg_monthly,
                "yearly_total": total_yearly,
                "confidence": round(confidence, 2),
                "monthly_breakdown": year_sales,
            })

        current_monthly = int(sales[-12:].mean()) if len(sales) >= 12 else int(sales.mean())
        final_yearly = float(str(yearly_forecast[-1]["monthly_avg"]))
        cagr = ((final_yearly / max(current_monthly, 1)) ** (1 / self.forecast_years)) - 1

        peak_month = self._find_peak_month(yearly_forecast)
        trough_month = self._find_trough_month(yearly_forecast)

        if cagr > 0.05 and consistency_score > 0.6:
            overall_outlook = "strong_growth"
        elif cagr > 0:
            overall_outlook = "moderate_growth"
        elif cagr > -0.05:
            overall_outlook = "stable"
        else:
            overall_outlook = "declining"

        evergreen_prob = self._calc_evergreen_probability(
            consistency_score, cagr, seasonal, macro_trends)

        product["forecast"] = {
            "current_monthly_sales": current_monthly,
            "yearly_forecast": yearly_forecast,
            "cagr": round(cagr, 4),
            "cagr_pct": round(cagr * 100, 2),
            "overall_outlook": overall_outlook,
            "peak_month": peak_month,
            "trough_month": trough_month,
            "evergreen_probability": evergreen_prob,
            "macro_growth_impact": round(macro_growth, 3),
            "trend_slope": round(trend["slope"], 4),
            "seasonal_strength": round(seasonal.get("_strength", 0), 3),
        }

        return product

    def forecast_products(self, products: List[Dict]) -> List[Dict]:
        """Forecast all products."""
        return [self.forecast_product(p) for p in products]

    def _fit_trend(self, sales: np.ndarray) -> dict:
        """Fit linear trend to sales data."""
        if len(sales) < 2:
            return {"slope": 0, "intercept": sales.mean() if len(sales) > 0 else 100, "r_squared": 0}

        x = np.arange(len(sales))
        coeffs = np.polyfit(x, sales, 1)
        slope = coeffs[0]
        intercept = coeffs[1]

        y_pred = slope * x + intercept
        ss_res = np.sum((sales - y_pred) ** 2)
        ss_tot = np.sum((sales - np.mean(sales)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return {
            "slope": float(slope),
            "intercept": float(intercept),
            "r_squared": float(max(0, r_squared)),
        }

    def _extract_seasonality(self, sales: np.ndarray, category: str) -> dict:
        """Extract monthly seasonal patterns."""
        if len(sales) < 12:
            default = self.SEASONAL_PATTERNS.get(category, {})
            return {m: default.get(m, 1.0) for m in range(1, 13)}

        chunk_size = 12
        monthly_avgs = np.zeros(12)
        count = 0

        for i in range(0, len(sales), chunk_size):
            chunk = sales[i:i + 12]
            if len(chunk) == 12:
                monthly_avgs += chunk
                count += 1

        if count > 0:
            monthly_avgs /= count

        overall_mean = monthly_avgs.mean()
        if overall_mean > 0:
            seasonal_factors = monthly_avgs / overall_mean
        else:
            seasonal_factors = np.ones(12)

        strength = float(np.std(seasonal_factors))

        result: Dict[Any, Any] = {}
        for m in range(12):
            result[m + 1] = round(float(seasonal_factors[m]), 3)
        result["_strength"] = round(strength, 3)

        return result

    def _compute_moving_averages(self, sales: np.ndarray) -> dict:
        """Compute short/medium/long-term moving averages."""
        result = {}

        if len(sales) >= 3:
            result["short_term"] = float(np.mean(sales[-3:]))
        else:
            result["short_term"] = float(np.mean(sales))

        if len(sales) >= 6:
            result["medium_term"] = float(np.mean(sales[-6:]))
        else:
            result["medium_term"] = result["short_term"]

        if len(sales) >= 12:
            result["long_term"] = float(np.mean(sales[-12:]))
        else:
            result["long_term"] = result["medium_term"]

        result["short_vs_long"] = (
            result["short_term"] / result["long_term"]
            if result["long_term"] > 0 else 1.0
        )

        return result

    def _find_peak_month(self, yearly_forecast: list) -> int:
        """Find the peak sales month from forecast."""
        if not yearly_forecast or not yearly_forecast[0].get("monthly_breakdown"):
            return 11

        monthly_totals = [0] * 12
        for year_data in yearly_forecast:
            breakdown = year_data.get("monthly_breakdown", [])
            for m in range(min(12, len(breakdown))):
                monthly_totals[m] += breakdown[m]

        peak_idx = monthly_totals.index(max(monthly_totals))
        return peak_idx + 1

    def _find_trough_month(self, yearly_forecast: list) -> int:
        """Find the lowest sales month from forecast."""
        if not yearly_forecast or not yearly_forecast[0].get("monthly_breakdown"):
            return 1

        monthly_totals = [0] * 12
        for year_data in yearly_forecast:
            breakdown = year_data.get("monthly_breakdown", [])
            for m in range(min(12, len(breakdown))):
                monthly_totals[m] += breakdown[m]

        trough_idx = monthly_totals.index(min(monthly_totals))
        return trough_idx + 1

    def _calc_evergreen_probability(self, consistency: float, cagr: float,
                                     seasonal: dict, macro_trends: list) -> float:
        """Calculate probability of product being evergreen."""
        prob = 0.3

        prob += consistency * 0.3

        if cagr > 0.05:
            prob += 0.15
        elif cagr > 0:
            prob += 0.10
        elif cagr > -0.05:
            prob += 0.05

        seasonal_strength = seasonal.get("_strength", 0)
        if seasonal_strength < 0.15:
            prob += 0.10
        elif seasonal_strength < 0.25:
            prob += 0.05

        prob += len(macro_trends) * 0.03

        return round(min(0.95, max(0.1, prob)), 3)

    def _default_forecast(self, product: dict) -> dict:
        """Default forecast when no historical data exists."""
        reviews = product.get("review_count", 1000)
        est_monthly = max(50, reviews // 20)

        yearly_forecast = []
        for year in range(1, self.forecast_years + 1):
            growth = 1 + (year * 0.05)
            monthly = int(est_monthly * growth * random.uniform(0.9, 1.1))
            yearly_forecast.append({
                "year": 2026 + year,
                "monthly_avg": monthly,
                "yearly_total": monthly * 12,
                "confidence": round(max(0.2, 0.6 - year * 0.08), 2),
                "monthly_breakdown": [monthly] * 12,
            })

        product["forecast"] = {
            "current_monthly_sales": est_monthly,
            "yearly_forecast": yearly_forecast,
            "cagr": 0.05,
            "cagr_pct": 5.0,
            "overall_outlook": "moderate_growth",
            "peak_month": 11,
            "trough_month": 2,
            "evergreen_probability": 0.5,
            "macro_growth_impact": 0.05,
            "trend_slope": 0,
            "seasonal_strength": 0.15,
        }

        return product

    def get_forecast_summary(self, products: List[Dict]) -> dict:
        """Generate summary of all forecasts."""
        if not products:
            return {"total": 0}

        outlooks: Dict[str, int] = {}
        for p in products:
            outlook = p.get("forecast", {}).get("overall_outlook", "unknown")
            outlooks[outlook] = outlooks.get(outlook, 0) + 1

        avg_cagr = np.mean([p.get("forecast", {}).get("cagr", 0) for p in products])
        avg_evergreen = np.mean([p.get("forecast", {}).get("evergreen_probability", 0) for p in products])

        strong_growth = [p for p in products
                         if p.get("forecast", {}).get("overall_outlook") == "strong_growth"]

        return {
            "total": len(products),
            "outlook_distribution": outlooks,
            "avg_cagr": round(float(avg_cagr), 4),
            "avg_cagr_pct": round(float(avg_cagr * 100), 2),
            "avg_evergreen_probability": round(float(avg_evergreen), 3),
            "strong_growth_count": len(strong_growth),
            "top_growth_products": [
                {
                    "name": p.get("name", "Unknown"),
                    "cagr_pct": p.get("forecast", {}).get("cagr_pct", 0),
                    "evergreen_prob": p.get("forecast", {}).get("evergreen_probability", 0),
                }
                for p in sorted(strong_growth,
                                key=lambda x: x.get("forecast", {}).get("cagr", 0),
                                reverse=True)[:10]
            ],
        }
