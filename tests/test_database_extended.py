"""Extended tests for database.manager — coverage boost to 90%+."""

import json
import os
from pathlib import Path

import pytest

from database.manager import DatabaseManager


class TestSuppliersExtended:
    """Extended supplier tests."""

    def test_get_supplier_not_found(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        assert db.get_supplier(9999) is None

    def test_delete_supplier_cascades_products(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        sid = db.add_supplier({"name": "Supplier"})
        db.add_supplier_product({"supplier_id": sid, "product_name": "Widget", "asin": "B0TEST1234"})
        db.delete_supplier(sid)
        products = db.get_supplier_products(supplier_id=sid)
        assert len(products) == 0

    def test_supplier_products_by_asin(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        sid = db.add_supplier({"name": "Supplier"})
        db.add_supplier_product({"supplier_id": sid, "product_name": "Widget", "asin": "B0TEST1234"})
        products = db.get_supplier_products(asin="B0TEST1234")
        assert len(products) == 1

    def test_supplier_products_all(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        sid = db.add_supplier({"name": "Supplier"})
        db.add_supplier_product({"supplier_id": sid, "product_name": "A", "asin": "B0TEST0001"})
        db.add_supplier_product({"supplier_id": sid, "product_name": "B", "asin": "B0TEST0002"})
        products = db.get_supplier_products()
        assert len(products) == 2

    def test_supplier_product_bulk_prices_json(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        sid = db.add_supplier({"name": "Supplier"})
        db.add_supplier_product({
            "supplier_id": sid, "product_name": "Widget", "asin": "B0TEST1234",
            "bulk_prices": {"100": 5.0, "500": 4.0}
        })
        products = db.get_supplier_products(asin="B0TEST1234")
        assert isinstance(products[0]["bulk_prices"], dict)

    def test_supplier_product_bulk_prices_string(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        sid = db.add_supplier({"name": "Supplier"})
        db.add_supplier_product({
            "supplier_id": sid, "product_name": "Widget", "asin": "B0TEST1234",
            "bulk_prices": "invalid json"
        })
        products = db.get_supplier_products(asin="B0TEST1234")
        assert products[0]["bulk_prices"] == {}


class TestPricingExtended:
    """Extended pricing tests."""

    def test_update_existing_pricing(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        db.save_pricing({"asin": "B0TEST1234", "supplier_cost": 10.0})
        db.save_pricing({"asin": "B0TEST1234", "supplier_cost": 8.0})
        pricing = db.get_pricing("B0TEST1234")
        assert pricing["supplier_cost"] == 8.0

    def test_get_pricing_not_found(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        assert db.get_pricing("NONEXISTENT") is None

    def test_get_all_pricing_empty(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        assert db.get_all_pricing() == []


class TestProductCache:
    """Tests for product cache."""

    def test_cache_and_retrieve(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        db.cache_product("B0TEST1234", {"title": "Widget", "price": 29.99})
        cached = db.get_cached_product("B0TEST1234")
        assert cached is not None
        assert cached["product_data"]["title"] == "Widget"

    def test_cache_expired(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        db.cache_product("B0TEST1234", {"title": "Widget"})
        cached = db.get_cached_product("B0TEST1234", max_age_hours=0)
        assert cached is None

    def test_cache_not_found(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        assert db.get_cached_product("NONEXISTENT") is None


class TestSeasonality:
    """Tests for seasonality data."""

    def test_save_and_get_seasonality(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        data = {"month": 12, "demand_level": "high", "search_volume": 1000}
        db.save_seasonality("B0TEST1234", "Widget", data)
        result = db.get_seasonality("B0TEST1234")
        assert len(result) == 1
        assert result[0]["month"] == 12

    def test_get_seasonality_empty(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        assert db.get_seasonality("NONEXISTENT") == []


class TestCompetitors:
    """Tests for competitor tracking."""

    def test_record_and_get_competitors(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        comp = {"competitor_asin": "B0COMP1234", "competitor_name": "Rival", "competitor_price": 24.99}
        db.record_competitor("B0TEST1234", "Widget", comp)
        competitors = db.get_competitors("B0TEST1234")
        assert len(competitors) == 1
        assert competitors[0]["competitor_price"] == 24.99

    def test_get_competitors_limit(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        for i in range(5):
            db.record_competitor("B0TEST1234", "Widget", {"competitor_name": f"Rival {i}"})
        competitors = db.get_competitors("B0TEST1234", limit=3)
        assert len(competitors) == 3

    def test_get_competitors_empty(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        assert db.get_competitors("NONEXISTENT") == []


class TestInventoryExtended:
    """Extended inventory tests."""

    def test_get_inventory_all(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        db.save_inventory("B0TEST0001", "Product 1", {"current_stock": 100})
        db.save_inventory("B0TEST0002", "Product 2", {"current_stock": 200})
        items = db.get_inventory()
        assert len(items) == 2


class TestTasksExtended:
    """Extended task tests."""

    def test_get_all_tasks(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        db.add_task("B0TEST0001", "P1", "Task A")
        db.add_task("B0TEST0002", "P2", "Task B")
        tasks = db.get_tasks()
        assert len(tasks) == 2

    def test_get_tasks_empty(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        assert db.get_tasks("NONEXISTENT") == []


class TestCSVImportExportExtended:
    """Extended CSV tests."""

    def test_export_empty(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        csv_path = str(tmp_data_dir / "empty.csv")
        exported = db.export_suppliers_to_csv(csv_path)
        assert exported == 0

    def test_import_empty_name_skipped(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        csv_path = str(tmp_data_dir / "test.csv")
        with open(csv_path, "w") as f:
            f.write("name,rating\n,4.5\n")
        imported = db.import_suppliers_from_csv(csv_path)
        assert imported == 0

    def test_import_with_alternate_columns(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        csv_path = str(tmp_data_dir / "test.csv")
        with open(csv_path, "w") as f:
            f.write("supplier_name,country,url,email,phone,moq,lead_time,payment_terms,rating,notes\n")
            f.write("Acme Corp,China,http://acme.com,info@acme.com,+86123,100,14,T/T,4.5,Good\n")
        imported = db.import_suppliers_from_csv(csv_path)
        assert imported == 1
