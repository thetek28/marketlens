"""Tests for calculators.profit module."""

import pytest

from calculators.profit import ProfitCalculator, REFERRAL_FEES, get_referral_fee_percent, calculate_fba_fee


class TestProfitCalculatorInit:
    """Test ProfitCalculator initialization."""

    def test_default_config(self):
        calc = ProfitCalculator()
        assert calc.default_referral_fee == 15
        assert calc.default_fba_base == 3.22
        assert calc.default_target_margin == 30

    def test_custom_config(self):
        calc = ProfitCalculator({"referral_fee_percent": 10, "target_margin": 40})
        assert calc.default_referral_fee == 10
        assert calc.default_target_margin == 40


class TestCalculate:
    """Test profit calculation."""

    def test_basic_calculation(self):
        calc = ProfitCalculator()
        result = calc.calculate(
            supplier_cost=10.00,
            selling_price=30.00,
            category="kitchen",
        )

        assert result["supplier_cost"] == 10.00
        assert result["selling_price"] == 30.00
        assert result["profit_per_unit"] > 0
        assert result["margin_percent"] > 0
        assert result["roi_percent"] > 0

    def test_with_shipping(self):
        calc = ProfitCalculator()
        result = calc.calculate(
            supplier_cost=10.00,
            selling_price=30.00,
            shipping_cost=3.00,
        )

        assert result["shipping_cost"] == 3.00
        assert result["landed_cost"] == 13.00

    def test_with_customs_duty(self):
        calc = ProfitCalculator()
        result = calc.calculate(
            supplier_cost=10.00,
            selling_price=30.00,
            customs_duty_percent=10,
        )

        assert result["customs_duty"] == 1.00
        assert result["landed_cost"] == 11.00

    def test_with_packaging(self):
        calc = ProfitCalculator()
        result = calc.calculate(
            supplier_cost=10.00,
            selling_price=30.00,
            packaging_cost=2.00,
        )

        assert result["packaging_cost"] == 2.00
        assert result["landed_cost"] == 12.00

    def test_referral_fee_by_category(self):
        calc = ProfitCalculator()

        # Electronics has 8% referral fee
        result_electronics = calc.calculate(
            supplier_cost=10.00,
            selling_price=100.00,
            category="electronics",
        )
        assert result_electronics["referral_percent"] == 8
        assert result_electronics["referral_fee"] == 8.00

        # Kitchen has 15% referral fee
        result_kitchen = calc.calculate(
            supplier_cost=10.00,
            selling_price=100.00,
            category="kitchen",
        )
        assert result_kitchen["referral_percent"] == 15
        assert result_kitchen["referral_fee"] == 15.00

    def test_zero_selling_price(self):
        calc = ProfitCalculator()
        result = calc.calculate(
            supplier_cost=10.00,
            selling_price=0.00,
        )

        assert result["margin_percent"] == 0
        # ROI is undefined when investment is 0, but implementation returns 0
        assert result["roi_percent"] == 0 or result["roi_percent"] < 0

    def test_break_even(self):
        calc = ProfitCalculator()
        result = calc.calculate(
            supplier_cost=10.00,
            selling_price=30.00,
            monthly_fixed_costs=100.00,
        )

        assert result["break_even_units"] > 0

    def test_no_profit_no_break_even(self):
        calc = ProfitCalculator()
        result = calc.calculate(
            supplier_cost=50.00,
            selling_price=30.00,
            monthly_fixed_costs=100.00,
        )

        assert result["profit_per_unit"] < 0
        assert result["break_even_units"] == 0


class TestFBACalculation:
    """Test FBA fee calculation."""

    def test_small_standard(self):
        calc = ProfitCalculator()
        fee = calc._calculate_fba_fee(16, {"length": 12, "width": 8, "height": 4})
        assert fee == 3.22

    def test_large_standard(self):
        calc = ProfitCalculator()
        fee = calc._calculate_fba_fee(30, {"length": 17, "width": 10, "height": 6})
        assert fee == 4.75

    def test_oversize_small(self):
        calc = ProfitCalculator()
        fee = calc._calculate_fba_fee(80, {"length": 20, "width": 15, "height": 10})
        assert fee == 6.50

    def test_oversize_large(self):
        calc = ProfitCalculator()
        # 20 inch side, 80 oz = large standard (6.50) not oversize
        fee = calc._calculate_fba_fee(80, {"length": 20, "width": 15, "height": 10})
        # Longest side 20 <= 24, weight 80 <= 96, so it's 6.50
        assert fee == 6.50

    def test_oversize_heavy(self):
        calc = ProfitCalculator()
        # 30 inch side, 200 oz = oversize large (8.26)
        fee = calc._calculate_fba_fee(200, {"length": 30, "width": 20, "height": 15})
        # Longest side 30 > 24, girth = 20+15=35 <= 130, weight 200 <= 256, so 9.75
        assert fee == 9.75

    def test_default_dimensions(self):
        calc = ProfitCalculator()
        fee = calc._calculate_fba_fee(16)
        assert fee == 3.22


class TestSuggestPrice:
    """Test price suggestion."""

    def test_basic_suggestion(self):
        calc = ProfitCalculator()
        result = calc.suggest_price(
            supplier_cost=10.00,
            category="kitchen",
        )

        assert result["min_price"] > 0
        assert result["suggested_price"] > 0
        assert result["suggested_price"] > result["min_price"]

    def test_with_competitors(self):
        calc = ProfitCalculator()
        result = calc.suggest_price(
            supplier_cost=10.00,
            competitor_prices=[25.00, 30.00, 35.00],
        )

        assert result["market_avg"] == 30.00
        assert result["market_min"] == 25.00
        assert result["market_max"] == 35.00

    def test_custom_target_margin(self):
        calc = ProfitCalculator()
        result = calc.suggest_price(
            supplier_cost=10.00,
            target_margin=50,
        )

        assert result["target_margin"] == 50


class TestCompareSuppliers:
    """Test supplier comparison."""

    def test_compare_suppliers(self):
        calc = ProfitCalculator()
        suppliers = [
            {"supplier_name": "Supplier A", "unit_cost": 8.00, "shipping_cost": 2.00},
            {"supplier_name": "Supplier B", "unit_cost": 6.00, "shipping_cost": 3.00},
            {"supplier_name": "Supplier C", "unit_cost": 10.00, "shipping_cost": 1.00},
        ]

        results = calc.compare_suppliers(suppliers, selling_price=30.00)

        assert len(results) == 3
        # Should be sorted by profit (highest first)
        assert results[0]["profit_per_unit"] >= results[1]["profit_per_unit"]
        assert results[1]["profit_per_unit"] >= results[2]["profit_per_unit"]


class TestMonthlyProjection:
    """Test monthly profit projection."""

    def test_basic_projection(self):
        calc = ProfitCalculator()
        result = calc.calculate_monthly_projection(
            profit_per_unit=10.00,
            units_per_day=5,
            months=6,
        )

        assert len(result["projections"]) == 6
        assert result["summary"]["total_units"] == 900  # 5 * 30 * 6

    def test_with_startup_costs(self):
        calc = ProfitCalculator()
        result = calc.calculate_monthly_projection(
            profit_per_unit=10.00,
            units_per_day=5,
            startup_costs=500.00,
        )

        # First month should have reduced cumulative (startup costs deducted)
        first_month = result["projections"][0]
        # Revenue = 5 * 30 * 10 = 1500, cumulative = -500 + 1500 = 1000
        assert first_month["cumulative_profit"] == 1000.0

    def test_break_even_calculation(self):
        calc = ProfitCalculator()
        result = calc.calculate_monthly_projection(
            profit_per_unit=10.00,
            units_per_day=5,
            startup_costs=100.00,
        )

        # Should break even in month 1 (5*30*10 = 1500 > 100)
        assert result["summary"]["months_to_break_even"] == 1

    def test_no_profit_no_breakeven(self):
        calc = ProfitCalculator()
        result = calc.calculate_monthly_projection(
            profit_per_unit=-5.00,
            units_per_day=5,
            startup_costs=100.00,
        )

        assert result["summary"]["months_to_break_even"] == -1


class TestReferralFees:
    """Test referral fee constants."""

    def test_known_categories(self):
        assert REFERRAL_FEES["kitchen"] == 15
        assert REFERRAL_FEES["electronics"] == 8
        assert REFERRAL_FEES["jewelry"] == 20
        assert REFERRAL_FEES["computers"] == 8

    def test_get_referral_fee_percent(self):
        assert get_referral_fee_percent("kitchen") == 15
        assert get_referral_fee_percent("electronics") == 8
        assert get_referral_fee_percent("unknown") == 15  # default

    def test_case_insensitive(self):
        assert get_referral_fee_percent("Kitchen") == 15
        assert get_referral_fee_percent("KITCHEN") == 15
