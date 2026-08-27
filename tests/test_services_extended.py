"""Extended tests for services — deeper path coverage."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from services.analysis_service import AnalysisService, calculate_priority
from services.collection_service import CollectionService


# ─── AnalysisService deeper paths ─────────────────────────────


class TestAnalysisServiceDeep:
    """Deeper tests for AnalysisService."""

    @pytest.fixture
    def service(self):
        config = {"ai": {"enabled": False}}
        return AnalysisService(config)

    def test_analyze_profitability_failure_continues(self, service):
        with patch("services.analysis_service.ProfitabilityEstimator") as mock:
            mock.return_value.estimate.side_effect = Exception("boom")
            result = service.analyze(
                products=[{"name": "P"}],
                raw_data={},
                status_callback=MagicMock(),
            )
            assert isinstance(result, list)

    def test_analyze_validation_failure_continues(self, service):
        with patch("services.analysis_service.ProfitabilityEstimator"), \
             patch("services.analysis_service.ProductValidator") as mock:
            mock.return_value.validate.side_effect = Exception("boom")
            result = service.analyze(products=[{"name": "P"}], raw_data={})
            assert isinstance(result, list)

    def test_analyze_marketing_failure_continues(self, service):
        with patch("services.analysis_service.ProfitabilityEstimator"), \
             patch("services.analysis_service.ProductValidator"), \
             patch("services.analysis_service.MarketingAnalyzer") as mock:
            mock.return_value.analyze.side_effect = Exception("boom")
            result = service.analyze(products=[{"name": "P"}], raw_data={})
            assert isinstance(result, list)

    def test_analyze_ai_failure_continues(self, service):
        service.ai_analyzer.analyze_products = MagicMock(side_effect=Exception("boom"))
        with patch("services.analysis_service.ProfitabilityEstimator"), \
             patch("services.analysis_service.ProductValidator"), \
             patch("services.analysis_service.MarketingAnalyzer"):
            result = service.analyze(products=[{"name": "P"}], raw_data={})
            assert isinstance(result, list)

    def test_analyze_consistency_failure_continues(self, service):
        with patch("services.analysis_service.ProfitabilityEstimator"), \
             patch("services.analysis_service.ProductValidator"), \
             patch("services.analysis_service.MarketingAnalyzer"), \
             patch("services.analysis_service.ConsistencyAnalyzer") as mock:
            mock.return_value.analyze.side_effect = Exception("boom")
            result = service.analyze(products=[{"name": "P"}], raw_data={})
            assert isinstance(result, list)

    def test_analyze_forecast_failure_continues(self, service):
        ideas = [{"name": "P"}]
        with patch("services.analysis_service.ProfitabilityEstimator") as mock_est, \
             patch("services.analysis_service.ProductValidator") as mock_val, \
             patch("services.analysis_service.MarketingAnalyzer"), \
             patch("services.analysis_service.ConsistencyAnalyzer") as mock_cons, \
             patch("services.analysis_service.ForecastingEngine") as mock_frc:
            mock_est.return_value.estimate.return_value = ideas
            mock_val.return_value.validate.return_value = ideas
            mock_cons.return_value.analyze.return_value = ideas
            mock_frc.return_value.forecast_products.side_effect = Exception("boom")
            service.ai_analyzer.analyze_products = MagicMock(return_value=ideas)
            result = service.analyze(products=ideas, raw_data={"amazon": []})
            assert isinstance(result, list)

    def test_analyze_supplier_sourcing_failure_continues(self, service):
        ideas = [{"name": "P"}]
        with patch("services.analysis_service.ProfitabilityEstimator") as mock_est, \
             patch("services.analysis_service.ProductValidator") as mock_val, \
             patch("services.analysis_service.MarketingAnalyzer"), \
             patch("services.analysis_service.ConsistencyAnalyzer"), \
             patch("services.analysis_service.ForecastingEngine") as mock_frc, \
             patch("database.suppliers_db.match_suppliers_to_products", side_effect=Exception("boom")):
            mock_est.return_value.estimate.return_value = ideas
            mock_val.return_value.validate.return_value = ideas
            mock_frc.return_value.forecast_products.return_value = ideas
            service.ai_analyzer.analyze_products = MagicMock(return_value=ideas)
            result = service.analyze(products=ideas, raw_data={"amazon": []})
            assert isinstance(result, list)

    def test_analyze_adds_priority_and_url(self, service):
        ideas = [{"name": "Test"}]
        with patch("services.analysis_service.ProfitabilityEstimator") as mock_est, \
             patch("services.analysis_service.ProductValidator") as mock_val, \
             patch("services.analysis_service.MarketingAnalyzer"), \
             patch("services.analysis_service.ConsistencyAnalyzer"), \
             patch("services.analysis_service.ForecastingEngine") as mock_frc:
            mock_est.return_value.estimate.return_value = ideas
            mock_val.return_value.validate.return_value = ideas
            mock_frc.return_value.forecast_products.return_value = ideas
            service.ai_analyzer.analyze_products = MagicMock(return_value=ideas)
            result = service.analyze(products=ideas, raw_data={"amazon": []})
            assert len(result) == 1
            assert "priority_rank" in result[0]
            assert "priority" in result[0]
            assert "url" in result[0]

    def test_analyze_truncates_to_100(self, service):
        many_products = [{"name": f"P{i}"} for i in range(150)]
        with patch("services.analysis_service.ProfitabilityEstimator") as mock_est, \
             patch("services.analysis_service.ProductValidator") as mock_val, \
             patch("services.analysis_service.MarketingAnalyzer"), \
             patch("services.analysis_service.ConsistencyAnalyzer"), \
             patch("services.analysis_service.ForecastingEngine") as mock_frc:
            mock_est.return_value.estimate.return_value = many_products
            mock_val.return_value.validate.return_value = many_products
            mock_frc.return_value.forecast_products.return_value = many_products
            service.ai_analyzer.analyze_products = MagicMock(return_value=many_products)
            result = service.analyze(products=many_products, raw_data={"amazon": []})
            assert len(result) == 100

    def test_source_suppliers_import_error(self, service):
        with patch("builtins.__import__", side_effect=ImportError("no module")):
            result = service._source_suppliers([{"name": "P"}])
            assert len(result) == 1

    def test_source_suppliers_calls_callback(self, service):
        mock_cb = MagicMock()
        ideas = [{"name": f"P{i}", "category": "kitchen"} for i in range(15)]
        mock_scraper = MagicMock()
        mock_scraper.search_suppliers.return_value = []
        mock_module = MagicMock()
        mock_module.AlibabaScraper.return_value = mock_scraper
        mock_module.get_supplier_pricing.return_value = None
        with patch.dict("sys.modules", {"data_collectors.alibaba_scraper": mock_module}):
            service._source_suppliers(ideas, status_callback=mock_cb)
            mock_cb.assert_called()


# ─── CollectionService deeper paths ───────────────────────────


class TestCollectionServiceDeep:
    """Deeper tests for CollectionService."""

    @pytest.fixture
    def service(self):
        return CollectionService({})

    def test_collect_cycle_fallback_to_samples(self, service):
        with patch("services.collection_service.AmazonCollector") as mock_amz, \
             patch("services.collection_service.GoogleTrendsCollector") as mock_gt, \
             patch("services.collection_service.SocialMediaCollector") as mock_sm:
            mock_amz.return_value.collect.return_value = []
            mock_gt.return_value.collect.return_value = []
            mock_sm.return_value.collect.return_value = []
            result = service.collect_cycle(
                categories=["kitchen"], keywords=["test"], sources=["Amazon", "Google Trends", "Social Media"]
            )
            assert len(result) > 0

    def test_collect_cycle_deduplication(self, service):
        with patch("services.collection_service.AmazonCollector") as mock_amz, \
             patch("services.collection_service.GoogleTrendsCollector") as mock_gt, \
             patch("services.collection_service.SocialMediaCollector") as mock_sm:
            product = {"asin": "B0TEST1234", "title": "Widget", "price": 10}
            mock_amz.return_value.collect.return_value = [product]
            mock_gt.return_value.collect.return_value = [product]
            mock_sm.return_value.collect.return_value = []
            result = service.collect_cycle(
                categories=["kitchen"], keywords=["test"], sources=["Amazon", "Google Trends", "Social Media"]
            )
            asins = [p["asin"] for p in result]
            assert len(asins) == len(set(asins))

    def test_collect_cycle_skips_invalid_products(self, service):
        with patch("services.collection_service.AmazonCollector") as mock_amz:
            mock_amz.return_value.collect.return_value = [{"no_asin": True}]
            result = service.collect_cycle(
                categories=["kitchen"], keywords=["test"], sources=["Amazon"]
            )
            for p in result:
                assert "asin" in p
                assert p["source"] == "sample"

    def test_collect_cycle_exception_handling(self, service):
        with patch("services.collection_service.AmazonCollector") as mock_amz:
            mock_amz.return_value.collect.side_effect = Exception("network error")
            result = service.collect_cycle(
                categories=["kitchen"], keywords=["test"], sources=["Amazon"]
            )
            assert isinstance(result, list)

    def test_collect_with_timeout_fast_return(self, service):
        def fast_func():
            return [{"fast": True}]
        result = service._collect_with_timeout(fast_func, timeout_sec=5)
        assert len(result) == 1

    def test_collect_with_timeout_slow_function(self, service):
        def slow_func():
            import time
            time.sleep(30)
            return [{"slow": True}]
        result = service._collect_with_timeout(slow_func, timeout_sec=0.01)
        assert isinstance(result, list)

    def test_collect_with_timeout_exception(self, service):
        def exploding_func():
            raise RuntimeError("boom")
        result = service._collect_with_timeout(exploding_func)
        assert result == []

    def test_seen_asins_filter(self, service):
        service.seen_asins.add("B0TEST1234")
        with patch("services.collection_service.AmazonCollector") as mock_amz:
            mock_amz.return_value.collect.return_value = [
                {"asin": "B0TEST1234", "title": "Old"},
                {"asin": "B0TEST5678", "title": "New"},
            ]
            result = service.collect_cycle(
                categories=["kitchen"], keywords=["test"], sources=["Amazon"]
            )
            asins = [p["asin"] for p in result]
            assert "B0TEST1234" not in asins

    def test_callbacks_called(self, service):
        mock_status = MagicMock()
        mock_progress = MagicMock()
        with patch("services.collection_service.AmazonCollector") as mock_amz:
            mock_amz.return_value.collect.return_value = []
            service.collect_cycle(
                categories=["kitchen"], keywords=["test"], sources=["Amazon"],
                status_callback=mock_status, progress_callback=mock_progress,
            )
            assert mock_status.call_count > 0
            mock_progress.assert_called()
