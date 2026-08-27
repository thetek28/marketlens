"""Tests for analyzer modules."""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from analyzers.clustering import KeywordClustering
from analyzers.seasonality import SeasonalityDetector
from analyzers.forecasting import ForecastingEngine
from analyzers.data_validator import DataValidator
from analyzers.consistency import ConsistencyAnalyzer


# ---------------------------------------------------------------------------
# ClusteringAnalyzer (KeywordClustering)
# ---------------------------------------------------------------------------

class TestClusteringAnalyzer:
    """Tests for KeywordClustering."""

    def test_init(self):
        config = {"some_key": "value"}
        analyzer = KeywordClustering(config)
        assert analyzer.config == config
        assert analyzer.vectorizer is not None

    def test_cluster_products_empty(self):
        analyzer = KeywordClustering({})
        result = analyzer.fit({})
        assert result == {"clusters": [], "n_clusters": 0}

    @patch("analyzers.clustering.KMeans")
    @patch("analyzers.clustering.silhouette_score", return_value=0.5)
    def test_cluster_products_basic(self, mock_silhouette, mock_kmeans):
        mock_kmeans_instance = MagicMock()
        mock_kmeans_instance.fit_predict.return_value = np.array([0, 0, 1, 1])
        mock_kmeans_instance.cluster_centers_ = np.array([[0.1, 0.9], [0.8, 0.2]])
        mock_kmeans.return_value = mock_kmeans_instance

        raw_data = {
            "trends": [
                {"term": "wireless headphones"},
                {"term": "bluetooth earbuds"},
                {"term": "organic dog food"},
                {"term": "natural pet treats"},
            ]
        }
        analyzer = KeywordClustering({})
        result = analyzer.fit(raw_data)

        assert "clusters" in result
        assert "n_clusters" in result
        assert result["n_clusters"] >= 1
        assert len(result["clusters"]) >= 1
        assert "terms" in result
        assert len(result["terms"]) == 4

    @patch("analyzers.clustering.KMeans")
    @patch("analyzers.clustering.silhouette_score", return_value=0.5)
    def test_cluster_products_single_category(self, mock_silhouette, mock_kmeans):
        mock_kmeans_instance = MagicMock()
        mock_kmeans_instance.fit_predict.return_value = np.array([0, 0, 0])
        mock_kmeans_instance.cluster_centers_ = np.array([[0.5, 0.5]])
        mock_kmeans.return_value = mock_kmeans_instance

        raw_data = {
            "trends": [
                {"term": "wireless headphones"},
                {"term": "bluetooth earbuds"},
                {"term": "noise cancelling headphones"},
            ]
        }
        analyzer = KeywordClustering({})
        result = analyzer.fit(raw_data)

        assert result["n_clusters"] >= 1
        assert len(result["terms"]) == 3


# ---------------------------------------------------------------------------
# SeasonalityDetector
# ---------------------------------------------------------------------------

class TestSeasonalityDetector:
    """Tests for SeasonalityDetector."""

    def test_init(self):
        config = {"some_key": "value"}
        detector = SeasonalityDetector(config)
        assert detector.config == config

    def test_detect_empty(self):
        detector = SeasonalityDetector({})
        result = detector.analyze({})
        assert result["seasonal_products"] == []
        assert result["evergreen_products"] == []
        assert result["peak_months"] == {}
        assert result["upcoming_opportunities"] == []

    def test_detect_basic(self):
        raw_data = {
            "trends": [
                {"term": "christmas decorations", "date": "2024-12-01", "interest": 90},
                {"term": "christmas decorations", "date": "2024-11-01", "interest": 70},
                {"term": "christmas decorations", "date": "2024-10-01", "interest": 40},
                {"term": "christmas decorations", "date": "2024-09-01", "interest": 20},
                {"term": "christmas decorations", "date": "2024-08-01", "interest": 10},
                {"term": "christmas decorations", "date": "2024-07-01", "interest": 10},
                {"term": "christmas decorations", "date": "2024-06-01", "interest": 10},
                {"term": "christmas decorations", "date": "2024-05-01", "interest": 10},
                {"term": "christmas decorations", "date": "2024-04-01", "interest": 10},
                {"term": "christmas decorations", "date": "2024-03-01", "interest": 10},
                {"term": "christmas decorations", "date": "2024-02-01", "interest": 10},
                {"term": "christmas decorations", "date": "2024-01-01", "interest": 15},
            ]
        }
        detector = SeasonalityDetector({})
        result = detector.analyze(raw_data)

        assert "seasonal_products" in result
        assert "evergreen_products" in result
        assert isinstance(result["peak_months"], dict)
        assert isinstance(result["upcoming_opportunities"], list)

        all_products = result["seasonal_products"] + result["evergreen_products"]
        assert len(all_products) == 1
        assert all_products[0]["term"] == "christmas decorations"


# ---------------------------------------------------------------------------
# ForecastingEngine
# ---------------------------------------------------------------------------

class TestForecastingEngine:
    """Tests for ForecastingEngine."""

    def test_init(self):
        engine = ForecastingEngine()
        assert engine.forecast_years == 5

    def test_init_with_config(self):
        engine = ForecastingEngine(config={"key": "value"})
        assert engine.config == {"key": "value"}

    def test_forecast_products_empty(self):
        engine = ForecastingEngine()
        result = engine.forecast_products([])
        assert result == []

    def test_forecast_products_basic(self):
        products = [
            {
                "name": "Test Product",
                "category": "kitchen",
                "review_count": 1000,
                "yearly_data": {
                    "sales": [100] * 24,
                    "prices": [29.99] * 24,
                    "months": [f"2024-{m:02d}" for m in range(1, 13)] + [f"2025-{m:02d}" for m in range(1, 13)],
                },
                "macro_trends": ["sustainability"],
            }
        ]
        engine = ForecastingEngine()
        result = engine.forecast_products(products)

        assert len(result) == 1
        p = result[0]
        assert "forecast" in p
        assert "current_monthly_sales" in p["forecast"]
        assert "yearly_forecast" in p["forecast"]
        assert len(p["forecast"]["yearly_forecast"]) == 5
        assert "cagr" in p["forecast"]
        assert "overall_outlook" in p["forecast"]


# ---------------------------------------------------------------------------
# DataValidator
# ---------------------------------------------------------------------------

class TestDataValidator:
    """Tests for DataValidator."""

    def test_init(self):
        validator = DataValidator()
        assert validator.min_confidence == 0.5
        assert validator.outlier_threshold == 2.0
        assert validator.min_data_points == 3

    def test_init_with_config(self):
        config = {"min_confidence": 0.8, "outlier_threshold": 3.0}
        validator = DataValidator(config)
        assert validator.min_confidence == 0.8
        assert validator.outlier_threshold == 3.0

    def test_validate_products_empty(self):
        validator = DataValidator()
        ideas, report = validator.validate_all([], {"amazon": [], "trends": [], "social": []})
        assert ideas == []
        assert report["total_input"] == 0
        assert report["total_output"] == 0

    def test_validate_products_basic(self):
        ideas = [
            {
                "name": "Valid Product Name",
                "asin": "B09BFTVQ9X",
                "price": 29.99,
                "rating": 4.5,
                "review_count": 1500,
                "category": "kitchen",
                "score": 0.8,
            }
        ]
        raw_data = {"amazon": [], "trends": [], "social": []}

        validator = DataValidator()
        validated, report = validator.validate_all(ideas, raw_data)

        assert report["total_input"] == 1
        assert report["total_output"] >= 0
        assert isinstance(validated, list)


# ---------------------------------------------------------------------------
# ConsistencyAnalyzer
# ---------------------------------------------------------------------------

class TestConsistencyAnalyzer:
    """Tests for ConsistencyAnalyzer."""

    def test_init(self):
        analyzer = ConsistencyAnalyzer()
        assert analyzer.years_of_data == 5
        assert analyzer.months_of_data == 60

    def test_init_with_config(self):
        analyzer = ConsistencyAnalyzer(config={"key": "value"})
        assert analyzer.config == {"key": "value"}

    def test_analyze_empty(self):
        analyzer = ConsistencyAnalyzer()
        result = analyzer.analyze([])
        assert result == []

    def test_get_portfolio_summary_empty(self):
        analyzer = ConsistencyAnalyzer()
        summary = analyzer.get_portfolio_summary([])
        assert summary["total_products"] == 0
        assert summary["portfolio"]["anchor"]["count"] == 0
        assert summary["portfolio"]["growth"]["count"] == 0
        assert summary["portfolio"]["balanced"]["count"] == 0
        assert summary["portfolio"]["watchlist"]["count"] == 0
        assert summary["avg_consistency_score"] == 0


# ---------------------------------------------------------------------------
# SeasonalityDetector — edge cases
# ---------------------------------------------------------------------------

class TestSeasonalityEdgeCases:
    """Edge-case tests for SeasonalityDetector."""

    def test_malformed_records_skipped(self):
        detector = SeasonalityDetector({})
        raw_data = {"trends": [{"no_term": 1}, {"term": "x"}, "bad", 42]}
        result = detector.analyze(raw_data)
        assert isinstance(result, dict)
        assert len(result["seasonal_products"]) + len(result["evergreen_products"]) == 0

    def test_missing_interest_column(self):
        detector = SeasonalityDetector({})
        raw_data = {"trends": [{"term": "x", "date": "2024-01-01"}]}
        result = detector.analyze(raw_data)
        assert len(result["evergreen_products"]) == 1

    def test_constant_interest_not_seasonal(self):
        detector = SeasonalityDetector({})
        records = [{"term": "flat", "date": f"2024-{m:02d}-01", "interest": 50} for m in range(1, 13)]
        raw_data = {"trends": records}
        result = detector.analyze(raw_data)
        assert len(result["evergreen_products"]) == 1

    def test_season_map_all_months(self):
        assert len(SeasonalityDetector.SEASON_MAP) == 12
        for m in range(1, 13):
            assert SeasonalityDetector.SEASON_MAP[m] in ("winter", "spring", "summer", "fall")

    def test_find_peak_months_empty(self):
        detector = SeasonalityDetector({})
        result = detector._find_peak_months([])
        assert result == {}

    def test_compute_trend_single_point(self):
        import pandas as pd
        detector = SeasonalityDetector({})
        df = pd.DataFrame({"date": ["2024-01-01"], "interest": [50]})
        assert detector._compute_trend(df) == "stable"

    def test_compute_trend_rising(self):
        import pandas as pd
        detector = SeasonalityDetector({})
        dates = pd.date_range("2024-01-01", periods=24, freq="MS")
        interests = list(range(10, 34))
        df = pd.DataFrame({"date": dates, "interest": interests})
        assert detector._compute_trend(df) == "rising"

    def test_compute_trend_declining(self):
        import pandas as pd
        detector = SeasonalityDetector({})
        dates = pd.date_range("2024-01-01", periods=24, freq="MS")
        interests = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90,
                     50, 48, 46, 44, 42, 40, 38, 36, 34, 32, 30, 28]
        df = pd.DataFrame({"date": dates, "interest": interests})
        assert detector._compute_trend(df) == "declining"


# ---------------------------------------------------------------------------
# ForecastingEngine — edge cases
# ---------------------------------------------------------------------------

class TestForecastingEdgeCases:
    """Edge-case tests for ForecastingEngine."""

    def test_default_forecast_no_yearly_data(self):
        engine = ForecastingEngine()
        product = {"name": "No Data", "review_count": 200}
        result = engine.forecast_product(product)
        assert "forecast" in result
        assert result["forecast"]["current_monthly_sales"] == 50  # max(50, 200//20)

    def test_default_forecast_low_reviews(self):
        engine = ForecastingEngine()
        product = {"name": "Low Reviews", "review_count": 10}
        result = engine.forecast_product(product)
        assert result["forecast"]["current_monthly_sales"] == 50  # max(50, 10//20)

    def test_default_forecast_zero_reviews(self):
        engine = ForecastingEngine()
        product = {"name": "Zero Reviews", "review_count": 0}
        result = engine.forecast_product(product)
        assert result["forecast"]["current_monthly_sales"] == 50

    def test_forecast_with_short_sales_data(self):
        engine = ForecastingEngine()
        product = {
            "name": "Short Data",
            "category": "fitness",
            "review_count": 500,
            "yearly_data": {"sales": [10, 20, 30]},
        }
        result = engine.forecast_product(product)
        assert "forecast" in result
        assert len(result["forecast"]["yearly_forecast"]) == 5

    def test_forecast_with_macro_trends(self):
        engine = ForecastingEngine()
        product = {
            "name": "Macro Trends",
            "category": "electronics",
            "review_count": 1000,
            "yearly_data": {
                "sales": list(range(100, 124)),
                "prices": [29.99] * 24,
            },
            "macro_trends": ["ai_tech", "sustainability"],
        }
        result = engine.forecast_product(product)
        assert result["forecast"]["macro_growth_impact"] > 0

    def test_forecast_high_consistency_boosts_confidence(self):
        engine = ForecastingEngine()
        product = {
            "name": "Consistent",
            "category": "home",
            "review_count": 2000,
            "yearly_data": {"sales": list(range(200, 260))},
            "consistency_score": 0.9,
        }
        result = engine.forecast_product(product)
        y1_conf = result["forecast"]["yearly_forecast"][0]["confidence"]
        assert y1_conf >= 0.85

    def test_get_forecast_summary_empty(self):
        engine = ForecastingEngine()
        result = engine.get_forecast_summary([])
        assert result == {"total": 0}

    def test_get_forecast_summary_with_products(self):
        engine = ForecastingEngine()
        products = [
            {"name": "A", "forecast": {"cagr": 0.10, "overall_outlook": "strong_growth", "evergreen_probability": 0.8}},
            {"name": "B", "forecast": {"cagr": 0.02, "overall_outlook": "moderate_growth", "evergreen_probability": 0.5}},
        ]
        result = engine.get_forecast_summary(products)
        assert result["total"] == 2
        assert result["strong_growth_count"] == 1
        assert result["avg_cagr"] > 0

    def test_fit_trend_single_point(self):
        engine = ForecastingEngine()
        result = engine._fit_trend(np.array([100.0]))
        assert result["slope"] == 0
        assert result["intercept"] == 100.0

    def test_compute_moving_averages_short(self):
        engine = ForecastingEngine()
        result = engine._compute_moving_averages(np.array([10.0, 20.0]))
        assert "short_term" in result
        assert result["short_term"] == 15.0

    def test_find_peak_month_empty(self):
        engine = ForecastingEngine()
        assert engine._find_peak_month([]) == 11

    def test_find_trough_month_empty(self):
        engine = ForecastingEngine()
        assert engine._find_trough_month([]) == 1

    def test_calc_evergreen_probability_zero(self):
        engine = ForecastingEngine()
        prob = engine._calc_evergreen_probability(0, -0.1, {}, [])
        assert 0.1 <= prob <= 0.95
