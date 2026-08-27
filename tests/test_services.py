"""Tests for the services module."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from services.analysis_service import AnalysisService, calculate_priority
from services.collection_service import CollectionService, SAMPLE_CATALOG
from services.export_service import ExportService


# ─── AnalysisService Tests ──────────────────────────────────


class TestCalculatePriority:
    """Tests for the calculate_priority helper."""

    def test_critical_top_rank(self):
        result = calculate_priority({}, 1)
        assert result["tier"] == "CRITICAL"
        assert result["action"] == "Source now"

    def test_critical_high_score_high_margin(self):
        idea = {"ai_score": 0.85, "estimated_margin_pct": 45}
        result = calculate_priority(idea, 30)
        assert result["tier"] == "CRITICAL"

    def test_high_mid_rank(self):
        result = calculate_priority({}, 15)
        assert result["tier"] == "HIGH"
        assert result["action"] == "Research"

    def test_high_good_score(self):
        idea = {"ai_score": 0.75, "estimated_margin_pct": 38}
        result = calculate_priority(idea, 30)
        assert result["tier"] == "HIGH"

    def test_medium_rank(self):
        result = calculate_priority({}, 40)
        assert result["tier"] == "MEDIUM"
        assert result["action"] == "Watchlist"

    def test_low_rank(self):
        result = calculate_priority({}, 60)
        assert result["tier"] == "LOW"
        assert result["action"] == "Monitor"

    def test_minimal_rank(self):
        result = calculate_priority({}, 80)
        assert result["tier"] == "MINIMAL"
        assert result["action"] == "Track"

    def test_returns_rank(self):
        result = calculate_priority({}, 5)
        assert result["rank"] == 5


class TestAnalysisService:
    """Tests for AnalysisService."""

    @pytest.fixture
    def service(self):
        config = {"ai": {"enabled": False}}
        return AnalysisService(config)

    def test_analyze_empty_products(self, service):
        result = service.analyze([], {})
        assert result == []

    @patch("services.analysis_service.ProfitabilityEstimator")
    def test_analyze_calls_profitability(self, mock_est, service):
        mock_est.return_value.estimate.return_value = [{"name": "Test"}]
        raw_data = {"amazon": [{"name": "Test"}]}

        with patch("services.analysis_service.ProductValidator") as mock_val, \
             patch("services.analysis_service.MarketingAnalyzer") as mock_mkt, \
             patch("services.analysis_service.ConsistencyAnalyzer") as mock_cons, \
             patch("services.analysis_service.ForecastingEngine") as mock_frc:
            mock_val.return_value.validate.return_value = [{"name": "Test"}]
            mock_mkt.return_value.analyze.return_value = [{"name": "Test"}]
            mock_cons.return_value.analyze.return_value = [{"name": "Test"}]
            mock_frc.return_value.forecast_products.return_value = [{"name": "Test"}]
            service.ai_analyzer.analyze_products = MagicMock(return_value=[{"name": "Test"}])

            result = service.analyze(
                products=[{"name": "Test"}],
                raw_data=raw_data,
                status_callback=MagicMock(),
            )

            mock_est.return_value.estimate.assert_called_once()
            assert len(result) <= 100


# ─── CollectionService Tests ─────────────────────────────────


class TestCollectionService:
    """Tests for CollectionService."""

    @pytest.fixture
    def service(self):
        config = {}
        return CollectionService(config)

    def test_get_sample_products(self, service):
        products = service.get_sample_products(["kitchen"])
        assert len(products) > 0
        assert products[0]["source"] == "sample"
        assert "asin" in products[0]

    def test_get_sample_products_multiple_categories(self, service):
        products = service.get_sample_products(["kitchen", "electronics"])
        assert len(products) >= 10

    def test_get_sample_products_unknown_category_uses_kitchen(self, service):
        products = service.get_sample_products(["unknown_category"])
        assert len(products) > 0

    def test_sample_products_have_required_fields(self, service):
        products = service.get_sample_products(["fitness"])
        for p in products:
            assert "title" in p
            assert "price" in p
            assert "rating" in p
            assert "asin" in p
            assert "url" in p

    def test_sample_catalog_has_categories(self):
        assert "kitchen" in SAMPLE_CATALOG
        assert "electronics" in SAMPLE_CATALOG
        assert "beauty" in SAMPLE_CATALOG
        assert "fitness" in SAMPLE_CATALOG

    @patch("services.collection_service.AmazonCollector")
    def test_collect_cycle_returns_list(self, mock_amz, service):
        mock_amz.return_value.collect.return_value = [
            {"asin": "B001", "title": "Test", "price": 10.0}
        ]
        result = service.collect_cycle(
            categories=["kitchen"],
            keywords=["test"],
            sources=["Amazon"],
        )
        assert isinstance(result, list)

    def test_seen_asins_tracked(self, service):
        service.seen_asins.add("B001")
        products = service.get_sample_products(["kitchen"])
        unique = [p for p in products if p["asin"] not in service.seen_asins]
        assert all(p["asin"] != "B001" for p in unique)


# ─── ExportService Tests ─────────────────────────────────────


class TestExportService:
    """Tests for ExportService."""

    @pytest.fixture
    def service(self):
        return ExportService()

    @pytest.fixture
    def sample_products(self):
        return [
            {"name": "Product A", "asin": "B001", "price": 10.0},
            {"name": "Product B", "asin": "B002", "price": 20.0},
        ]

    def test_export_json(self, service, sample_products, tmp_path):
        path = str(tmp_path / "test_export.json")
        ok, msg = service.export_json(sample_products, path)
        assert ok is True
        assert os.path.exists(path)

        with open(path, "r") as f:
            data = json.load(f)
        assert data["count"] == 2
        assert len(data["products"]) == 2

    def test_export_json_empty(self, service, tmp_path):
        path = str(tmp_path / "empty.json")
        ok, msg = service.export_json([], path)
        assert ok is True

        with open(path, "r") as f:
            data = json.load(f)
        assert data["count"] == 0

    def test_export_json_bad_path(self, service, sample_products):
        ok, msg = service.export_json(sample_products, "/nonexistent/dir/file.json")
        assert ok is False

    def test_save_and_load_products(self, service, tmp_path):
        path = str(tmp_path / "products.json")
        products = [{"name": "A"}]
        gems = [{"name": "B"}]
        cats = ["kitchen"]
        kws = ["trending"]

        result = service.save_products(products, gems, cats, kws, cycle=3, path=path)
        assert result is True

        loaded = service.load_products(path)
        assert loaded is not None
        assert loaded["ideas"] == products
        assert loaded["hidden_gems"] == gems
        assert loaded["categories"] == cats
        assert loaded["keywords"] == kws
        assert loaded["cycle"] == 3

    def test_load_products_nonexistent(self, service):
        result = service.load_products("/nonexistent/path.json")
        assert result is None

    def test_get_export_formats(self, service):
        formats = service.get_export_formats()
        assert len(formats) == 3
        keys = [f["key"] for f in formats]
        assert "excel" in keys
        assert "pdf" in keys
        assert "json" in keys

    def test_export_formats_have_required_fields(self, service):
        for fmt in service.get_export_formats():
            assert "key" in fmt
            assert "label" in fmt
            assert "extension" in fmt

    def test_export_json_special_characters(self, service, tmp_path):
        products = [{"name": "Ünïcödé Product", "desc": "Line1\nLine2"}]
        path = str(tmp_path / "unicode.json")
        ok, msg = service.export_json(products, path)
        assert ok is True
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["products"][0]["name"] == "Ünïcödé Product"

    def test_export_json_datetime_serialization(self, service, tmp_path):
        from datetime import datetime
        products = [{"name": "A", "created": datetime(2025, 1, 1)}]
        path = str(tmp_path / "dt.json")
        ok, msg = service.export_json(products, path)
        assert ok is True

    def test_export_excel_failure(self, service, sample_products, tmp_path):
        path = str(tmp_path / "bad.xlsx")
        with patch("utils.export_engine.ExcelExporter") as mock_exporter:
            mock_exporter.return_value.export_products.side_effect = Exception("write error")
            ok, msg = service.export_excel(sample_products, path)
        assert ok is False
        assert "write error" in msg

    def test_export_pdf_failure(self, service, sample_products, tmp_path):
        path = str(tmp_path / "bad.pdf")
        with patch("utils.export_engine.PDFExporter") as mock_exporter:
            mock_exporter.return_value.export_report.side_effect = Exception("write error")
            ok, msg = service.export_pdf(sample_products, path)
        assert ok is False
        assert "write error" in msg

    def test_save_products_bad_path(self, service):
        result = service.save_products([], [], [], [], 0, "/nonexistent/dir/save.json")
        assert result is False

    def test_load_products_corrupted(self, service, tmp_path):
        path = str(tmp_path / "corrupt.json")
        with open(path, "w") as f:
            f.write("{invalid json")
        result = service.load_products(path)
        assert result is None
