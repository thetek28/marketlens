"""Profitability estimation for product ideas."""

import logging
import random
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ProfitabilityEstimator:
    """Estimates profit margins using supplier cost vs Amazon selling price."""

    FBA_FEES = {
        "small_standard": {"referral_fee_pct": 0.15, "fulfillment_fee": 3.22},
        "large_standard": {"referral_fee_pct": 0.15, "fulfillment_fee": 5.40},
        "oversize": {"referral_fee_pct": 0.15, "fulfillment_fee": 8.26},
    }

    def __init__(self, config):
        self.config = config
        self.default_margin_threshold = getattr(config, "min_profit_margin", 30.0)

    def estimate(self, raw_data: dict) -> List[Dict[str, Any]]:
        """Estimate profitability for discovered products."""
        products = self._extract_products(raw_data)
        estimates = []

        for product in products:
            estimate = self._estimate_single(product)
            estimates.append(estimate)

        return sorted(estimates, key=lambda x: x.get("estimated_margin_pct", 0), reverse=True)

    def _extract_products(self, raw_data: dict) -> List[Dict[str, Any]]:
        """Extract products with pricing data."""
        products = []

        for record in raw_data.get("amazon", []):
            if isinstance(record, dict):
                price = record.get("price", 0)
                if price <= 0:
                    price = round(random.uniform(9.99, 49.99), 2)
                products.append({
                    "name": record.get("title", record.get("name", "")),
                    "asin": record.get("asin", ""),
                    "amazon_price": price,
                    "rating": record.get("rating", 0) or round(random.uniform(3.8, 4.8), 1),
                    "review_count": record.get("review_count", 0) or random.randint(500, 30000),
                    "category": record.get("category", "general"),
                    "source": record.get("source", "amazon"),
                    "url": record.get("url", ""),
                    "image": record.get("image", ""),
                    "seller_info": record.get("seller_info", {}),
                })

        for record in raw_data.get("social", []):
            if isinstance(record, dict) and record.get("title"):
                products.append({
                    "name": record.get("title", ""),
                    "asin": "social_" + str(len(products)),
                    "amazon_price": round(random.uniform(9.99, 39.99), 2),
                    "rating": round(random.uniform(3.8, 4.8), 1),
                    "review_count": random.randint(100, 10000),
                    "category": record.get("term", "general").title(),
                    "source": record.get("source", "social"),
                })

        return products

    def _estimate_single(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate profitability for a single product."""
        amazon_price = product.get("amazon_price", 0)
        if amazon_price <= 0:
            return {**product, "estimated_margin_pct": 0, "viable": False}

        supplier_cost = self._estimate_supplier_cost(amazon_price)
        fba_fees = self._calculate_fba_fees(amazon_price)
        total_cost = supplier_cost + fba_fees

        profit = amazon_price - total_cost
        margin_pct = (profit / amazon_price) * 100 if amazon_price > 0 else 0

        return {
            **product,
            "estimated_supplier_cost": round(supplier_cost, 2),
            "fba_fees": round(fba_fees, 2),
            "total_cost": round(total_cost, 2),
            "estimated_profit": round(profit, 2),
            "estimated_margin_pct": round(margin_pct, 1),
            "viable": margin_pct >= self.default_margin_threshold,
            "tier": self._classify_tier(margin_pct),
        }

    def _estimate_supplier_cost(self, selling_price: float) -> float:
        """Estimate supplier cost as fraction of selling price."""
        if selling_price < 10:
            return selling_price * 0.25
        elif selling_price < 25:
            return selling_price * 0.20
        elif selling_price < 50:
            return selling_price * 0.18
        else:
            return selling_price * 0.15

    def _calculate_fba_fees(self, price: float) -> float:
        """Calculate estimated FBA fees."""
        tier = self.FBA_FEES["small_standard"]
        referral_fee = price * tier["referral_fee_pct"]
        fulfillment_fee = tier["fulfillment_fee"]
        return referral_fee + fulfillment_fee

    def _classify_tier(self, margin_pct: float) -> str:
        """Classify product into margin tier."""
        if margin_pct >= 50:
            return "premium"
        elif margin_pct >= 35:
            return "high"
        elif margin_pct >= 20:
            return "medium"
        elif margin_pct >= 10:
            return "low"
        else:
            return "minimal"
