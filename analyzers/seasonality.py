"""Seasonality detection for product trends."""

import logging
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd

logger = logging.getLogger(__name__)


class SeasonalityDetector:
    """Detects seasonal demand patterns in product categories."""

    SEASON_MAP = {
        1: "winter", 2: "winter", 3: "spring",
        4: "spring", 5: "spring", 6: "summer",
        7: "summer", 8: "summer", 9: "fall",
        10: "fall", 11: "fall", 12: "winter",
    }

    def __init__(self, config):
        self.config = config

    def analyze(self, raw_data: dict) -> Dict[str, Any]:
        """Analyze seasonality across all data sources."""
        results: Dict[str, Any] = {
            "seasonal_products": [],
            "evergreen_products": [],
            "peak_months": {},
            "upcoming_opportunities": [],
        }

        terms_with_history = self._group_by_term(raw_data)

        for term, records in terms_with_history.items():
            analysis = self._analyze_term(term, records)
            if analysis["is_seasonal"]:
                results["seasonal_products"].append(analysis)
            else:
                results["evergreen_products"].append(analysis)

        results["peak_months"] = self._find_peak_months(results["seasonal_products"])
        results["upcoming_opportunities"] = self._find_upcoming_opportunities(results)

        return results

    def _group_by_term(self, raw_data: dict) -> Dict[str, List[dict]]:
        """Group records by term."""
        grouped: Dict[str, List[dict]] = {}
        for record in raw_data.get("trends", []):
            if isinstance(record, dict) and "term" in record and "date" in record:
                term = record["term"]
                if term not in grouped:
                    grouped[term] = []
                grouped[term].append(record)
        return grouped

    def _analyze_term(self, term: str, records: List[dict]) -> Dict[str, Any]:
        """Analyze seasonality for a single term."""
        df = pd.DataFrame(records)
        if "date" not in df.columns or "interest" not in df.columns:
            return {"term": term, "is_seasonal": False}

        df["date"] = pd.to_datetime(df["date"])
        df["month"] = df["date"].dt.month
        df["interest"] = pd.to_numeric(df["interest"], errors="coerce").fillna(0)

        monthly_avg = df.groupby("month")["interest"].mean()
        if monthly_avg.empty:
            return {"term": term, "is_seasonal": False}

        peak_month = int(monthly_avg.idxmax()) if len(monthly_avg) > 0 else 1
        peak_value = float(monthly_avg.max())
        mean_value = float(monthly_avg.mean())

        if mean_value == 0:
            coefficient_of_variation: float = 0
        else:
            coefficient_of_variation = float(monthly_avg.std() / mean_value)

        is_seasonal = coefficient_of_variation > 0.4 and peak_value > mean_value * 1.5

        trend = self._compute_trend(df)

        return {
            "term": term,
            "is_seasonal": is_seasonal,
            "coefficient_of_variation": round(coefficient_of_variation, 3),
            "peak_month": peak_month,
            "peak_season": self.SEASON_MAP.get(peak_month, "unknown"),
            "peak_value": round(peak_value, 2),
            "mean_value": round(mean_value, 2),
            "monthly_avg": monthly_avg.to_dict(),
            "trend": trend,
        }

    def _compute_trend(self, df: pd.DataFrame) -> str:
        """Compute overall trend direction."""
        if len(df) < 2:
            return "stable"

        df_sorted = df.sort_values("date")
        recent = df_sorted.tail(12)["interest"].mean()
        older = df_sorted.head(12)["interest"].mean()

        if older == 0:
            return "rising" if recent > 0 else "stable"

        change = (recent - older) / older
        if change > 0.2:
            return "rising"
        elif change < -0.2:
            return "declining"
        return "stable"

    def _find_peak_months(self, seasonal_products: List[Dict]) -> Dict[int, List[str]]:
        """Find which products peak in each month."""
        peaks: Dict[int, List[str]] = {}
        for product in seasonal_products:
            month = product.get("peak_month")
            if month:
                if month not in peaks:
                    peaks[month] = []
                peaks[month].append(product["term"])
        return peaks

    def _find_upcoming_opportunities(self, results: Dict) -> List[Dict[str, Any]]:
        """Find products that will peak in the next 1-3 months."""
        current_month = datetime.now().month
        upcoming_months = [(current_month + i - 1) % 12 + 1 for i in range(1, 4)]

        opportunities = []
        for product in results.get("seasonal_products", []):
            if product.get("peak_month") in upcoming_months:
                opportunities.append({
                    "term": product["term"],
                    "peak_month": product["peak_month"],
                    "peak_season": product.get("peak_season"),
                    "trend": product.get("trend"),
                    "priority": "high" if product.get("trend") == "rising" else "medium",
                })

        priority_order = {"high": 0, "medium": 1}
        return sorted(opportunities, key=lambda x: priority_order.get(x["priority"], 2))
