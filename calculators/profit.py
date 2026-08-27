"""Profit calculator with FBA fees and pricing suggestions."""

from typing import Any, Dict, List, Optional

# Amazon referral fees by category (percentage)
REFERRAL_FEES = {
    "amazon_device_accessories": 15,
    "automotive": 12,
    "baby": 15,
    "beauty": 15,
    "beauty_appliances": 15,
    "books": 15,
    "camera_photo": 8,
    "cell_phone_cases": 17,
    "clothing_accessories": 17,
    "computers": 8,
    "electronics": 8,
    "furniture": 15,
    "grocery": 15,
    "health_household": 15,
    "home_garden": 15,
    "industrial": 12,
    "jewelry": 20,
    "kitchen": 15,
    "luggage": 15,
    "magazines": 15,
    "musical_instruments": 15,
    "office_products": 15,
    "outdoors": 15,
    "pet_supplies": 15,
    "shoes": 15,
    "software": 15,
    "sports": 15,
    "tools_hardware": 15,
    "toys_games": 15,
    "video_games": 15,
    "watches": 15,
    "default": 15,
}


class ProfitCalculator:
    """Calculates profit, margins, ROI, and suggested pricing."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            config = {}
        self.default_referral_fee = config.get("referral_fee_percent", 15)
        self.default_fba_base = config.get("fba_base_fee", 3.22)
        self.default_target_margin = config.get("target_margin", 30)

    def calculate(
        self,
        supplier_cost: float,
        selling_price: float,
        category: str = "default",
        weight_oz: float = 16,
        dimensions: Optional[Dict[str, float]] = None,
        shipping_cost: float = 0,
        customs_duty_percent: float = 0,
        packaging_cost: float = 0,
        monthly_fixed_costs: float = 0,
    ) -> Dict[str, Any]:
        """Calculate full profit breakdown for a product."""
        referral_percent = REFERRAL_FEES.get(category.lower(), self.default_referral_fee)
        referral_fee = selling_price * (referral_percent / 100)

        fba_fee = self._calculate_fba_fee(weight_oz, dimensions)

        landed_cost = supplier_cost + shipping_cost + packaging_cost
        landed_cost += supplier_cost * (customs_duty_percent / 100)

        total_fees = fba_fee + referral_fee
        total_cost = landed_cost + total_fees
        profit = selling_price - total_cost
        margin = (profit / selling_price * 100) if selling_price > 0 else 0

        total_investment = supplier_cost + shipping_cost + packaging_cost
        roi = (profit / total_investment * 100) if total_investment > 0 else 0

        break_even = 0
        if profit > 0:
            break_even = int(monthly_fixed_costs / profit) if monthly_fixed_costs > 0 else 1

        return {
            "supplier_cost": round(supplier_cost, 2),
            "shipping_cost": round(shipping_cost, 2),
            "customs_duty": round(supplier_cost * (customs_duty_percent / 100), 2),
            "packaging_cost": round(packaging_cost, 2),
            "landed_cost": round(landed_cost, 2),
            "fba_fee": round(fba_fee, 2),
            "referral_fee": round(referral_fee, 2),
            "referral_percent": referral_percent,
            "total_fees": round(total_fees, 2),
            "total_cost": round(total_cost, 2),
            "selling_price": round(selling_price, 2),
            "profit_per_unit": round(profit, 2),
            "margin_percent": round(margin, 2),
            "roi_percent": round(roi, 2),
            "break_even_units": break_even,
        }

    def _calculate_fba_fee(self, weight_oz: float, dimensions: Optional[Dict[str, float]] = None) -> float:
        """Calculate FBA fulfillment fee based on weight and size."""
        if dimensions is None:
            dimensions = {}

        length = dimensions.get("length", 10)
        width = dimensions.get("width", 8)
        height = dimensions.get("height", 4)

        longest_side = max(length, width, height)
        median_side = sorted([length, width, height])[1]
        shortest_side = min(length, width, height)
        girth = median_side + shortest_side

        if longest_side <= 15 and weight_oz <= 16:
            return 3.22
        elif longest_side <= 18 and weight_oz <= 32:
            return 4.75
        elif longest_side <= 24 and weight_oz <= 96:
            return 6.50
        elif longest_side <= 60 and girth <= 130:
            if weight_oz <= 128:
                return 8.26
            elif weight_oz <= 256:
                return 9.75
            elif weight_oz <= 512:
                return 13.50
            elif weight_oz <= 1024:
                return 19.00
            else:
                base = 19.00
                extra_pounds = (weight_oz - 1024) / 16
                return base + (extra_pounds * 0.40)
        else:
            return 40.00 + (weight_oz / 16 * 0.40)

    def suggest_price(
        self,
        supplier_cost: float,
        category: str = "default",
        target_margin: Optional[float] = None,
        shipping_cost: float = 0,
        packaging_cost: float = 0,
        customs_duty_percent: float = 0,
        competitor_prices: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """Calculate suggested pricing based on costs and market."""
        if target_margin is None:
            target_margin = self.default_target_margin

        landed_cost = supplier_cost + shipping_cost + packaging_cost
        landed_cost += supplier_cost * (customs_duty_percent / 100)

        referral_percent = REFERRAL_FEES.get(category.lower(), self.default_referral_fee)
        min_price = landed_cost / (1 - (referral_percent / 100) - 0.15)
        min_price = min_price / (1 - target_margin / 100)

        suggested = min_price * 1.15

        if competitor_prices:
            avg_competitor = sum(competitor_prices) / len(competitor_prices)
            min_competitor = min(competitor_prices)
            max_competitor = max(competitor_prices)

            if suggested < min_competitor * 0.9:
                suggested = min_competitor * 0.95
            elif suggested > max_competitor * 1.1:
                suggested = max_competitor * 0.95

            optimal = (suggested + avg_competitor) / 2
        else:
            avg_competitor = 0
            min_competitor = 0
            max_competitor = 0
            optimal = suggested

        profit_at_suggested = self.calculate(
            supplier_cost=supplier_cost,
            selling_price=suggested,
            category=category,
            shipping_cost=shipping_cost,
            customs_duty_percent=customs_duty_percent,
            packaging_cost=packaging_cost,
        )

        return {
            "min_price": round(min_price, 2),
            "suggested_price": round(suggested, 2),
            "optimal_price": round(optimal, 2),
            "max_price": round(max_competitor * 1.1 if competitor_prices else suggested * 1.3, 2),
            "market_avg": round(avg_competitor, 2),
            "market_min": round(min_competitor, 2),
            "market_max": round(max_competitor, 2),
            "profit_at_suggested": profit_at_suggested["profit_per_unit"],
            "margin_at_suggested": profit_at_suggested["margin_percent"],
            "target_margin": target_margin,
        }

    def compare_suppliers(
        self,
        suppliers: List[Dict[str, Any]],
        selling_price: float,
        category: str = "default",
    ) -> List[Dict[str, Any]]:
        """Compare suppliers and calculate profit for each."""
        results = []
        for supplier in suppliers:
            calc = self.calculate(
                supplier_cost=supplier.get("unit_cost", 0),
                selling_price=selling_price,
                category=category,
                shipping_cost=supplier.get("shipping_cost", 0),
            )
            calc["supplier_name"] = supplier.get("supplier_name", "Unknown")
            calc["supplier_id"] = supplier.get("supplier_id", 0)
            calc["moq"] = supplier.get("min_order", 1)
            results.append(calc)

        results.sort(key=lambda x: x["profit_per_unit"], reverse=True)
        return results

    def calculate_monthly_projection(
        self,
        profit_per_unit: float,
        units_per_day: int,
        startup_costs: float = 0,
        monthly_fixed_costs: float = 0,
        months: int = 12,
    ) -> Dict[str, Any]:
        """Project monthly profits over a period."""
        projections = []
        cumulative_profit = -startup_costs

        for month in range(1, months + 1):
            monthly_units = units_per_day * 30
            monthly_revenue = monthly_units * profit_per_unit
            monthly_profit = monthly_revenue - monthly_fixed_costs
            cumulative_profit += monthly_profit

            projections.append({
                "month": month,
                "units": monthly_units,
                "revenue": round(monthly_revenue, 2),
                "profit": round(monthly_profit, 2),
                "cumulative_profit": round(cumulative_profit, 2),
            })

        total_revenue = sum(p["revenue"] for p in projections)
        total_profit = sum(p["profit"] for p in projections)
        total_units = sum(p["units"] for p in projections)

        return {
            "projections": projections,
            "summary": {
                "total_units": total_units,
                "total_revenue": round(total_revenue, 2),
                "total_profit": round(total_profit, 2),
                "average_monthly_profit": round(total_profit / months, 2),
                "months_to_break_even": self._months_to_break_even(
                    startup_costs, monthly_fixed_costs, units_per_day, profit_per_unit
                ),
            },
        }

    def _months_to_break_even(
        self,
        startup_costs: float,
        monthly_fixed_costs: float,
        units_per_day: int,
        profit_per_unit: float,
    ) -> int:
        """Calculate months to break even."""
        if profit_per_unit <= 0:
            return -1

        monthly_profit = (units_per_day * 30 * profit_per_unit) - monthly_fixed_costs
        if monthly_profit <= 0:
            return -1

        months = startup_costs / monthly_profit
        return int(months) + 1


def get_referral_fee_percent(category: str) -> float:
    """Get referral fee percentage for a category."""
    return REFERRAL_FEES.get(category.lower(), REFERRAL_FEES["default"])


def calculate_fba_fee(weight_oz: float = 16, dimensions: Optional[Dict[str, float]] = None) -> float:
    """Standalone FBA fee calculator."""
    calc = ProfitCalculator()
    return calc._calculate_fba_fee(weight_oz, dimensions)
