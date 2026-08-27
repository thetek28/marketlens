"""Tests for database.manager module."""

import json
import os
from pathlib import Path

import pytest

from database.manager import DatabaseManager


class TestDatabaseManagerInit:
    """Test DatabaseManager initialization."""

    def test_creates_database(self, tmp_data_dir: Path):
        db_path = str(tmp_data_dir / "test.db")
        db = DatabaseManager(db_path)
        assert os.path.exists(db_path)

    def test_creates_tables(self, tmp_data_dir: Path):
        db_path = str(tmp_data_dir / "test.db")
        db = DatabaseManager(db_path)

        # Verify tables exist by querying them
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            assert "suppliers" in tables
            assert "products" in tables
            assert "product_pricing" in tables


class TestSuppliers:
    """Test supplier CRUD operations."""

    def test_add_supplier(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        supplier = {
            "name": "Test Supplier",
            "location": "Shenzhen, China",
            "country": "China",
            "contact_email": "test@supplier.com",
            "rating": 4.5,
        }

        supplier_id = db.add_supplier(supplier)
        assert supplier_id > 0

    def test_get_supplier(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        supplier = {"name": "Test Supplier", "rating": 4.5}
        supplier_id = db.add_supplier(supplier)

        retrieved = db.get_supplier(supplier_id)
        assert retrieved is not None
        assert retrieved["name"] == "Test Supplier"
        assert retrieved["rating"] == 4.5

    def test_get_all_suppliers(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        db.add_supplier({"name": "Supplier A"})
        db.add_supplier({"name": "Supplier B"})

        suppliers = db.get_all_suppliers()
        assert len(suppliers) == 2

    def test_update_supplier(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        supplier_id = db.add_supplier({"name": "Original"})

        db.update_supplier(supplier_id, {"name": "Updated"})
        retrieved = db.get_supplier(supplier_id)
        assert retrieved["name"] == "Updated"

    def test_delete_supplier(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        supplier_id = db.add_supplier({"name": "To Delete"})

        db.delete_supplier(supplier_id)
        assert db.get_supplier(supplier_id) is None


class TestProducts:
    """Test product operations."""

    def test_batch_upsert_products(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        products = [
            {"asin": "B000001", "name": "Product 1", "category": "Kitchen"},
            {"asin": "B000002", "name": "Product 2", "category": "Electronics"},
        ]

        db.batch_upsert_products(products)
        count = db.get_products_count()
        assert count == 2

    def test_upsert_updates_existing(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        products = [{"asin": "B000001", "name": "Original"}]
        db.batch_upsert_products(products)

        products = [{"asin": "B000001", "name": "Updated"}]
        db.batch_upsert_products(products)

        count = db.get_products_count()
        assert count == 1


class TestPricing:
    """Test pricing operations."""

    def test_save_pricing(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        pricing = {
            "asin": "B000001",
            "product_name": "Test Product",
            "supplier_cost": 8.50,
            "selling_price": 29.99,
            "profit_per_unit": 10.00,
            "margin_percent": 33.3,
        }

        pricing_id = db.save_pricing(pricing)
        assert pricing_id > 0

    def test_get_pricing(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        pricing = {"asin": "B000001", "supplier_cost": 8.50}
        db.save_pricing(pricing)

        retrieved = db.get_pricing("B000001")
        assert retrieved is not None
        assert retrieved["supplier_cost"] == 8.50

    def test_get_all_pricing(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        db.save_pricing({"asin": "B000001", "supplier_cost": 8.50})
        db.save_pricing({"asin": "B000002", "supplier_cost": 12.00})

        all_pricing = db.get_all_pricing()
        assert len(all_pricing) == 2


class TestPriceHistory:
    """Test price history operations."""

    def test_record_price(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        db.record_price("B000001", "Test Product", "amazon", 29.99)

        history = db.get_price_history("B000001")
        assert len(history) == 1
        assert history[0]["price"] == 29.99

    def test_price_history_limit(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        for i in range(5):
            db.record_price("B000001", "Test Product", "amazon", 29.99 + i)

        history = db.get_price_history("B000001", limit=3)
        assert len(history) == 3


class TestReviewSentiment:
    """Test review sentiment operations."""

    def test_save_and_get_sentiment(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        sentiment = {
            "total_reviews": 100,
            "positive_pct": 75.0,
            "negative_pct": 15.0,
            "neutral_pct": 10.0,
            "top_complaints": ["Quality issues"],
            "top_praises": ["Great value"],
            "summary": "Mostly positive reviews",
        }

        db.save_review_sentiment("B000001", "Test Product", sentiment)
        retrieved = db.get_review_sentiment("B000001")

        assert retrieved is not None
        assert retrieved["positive_pct"] == 75.0
        assert "Quality issues" in retrieved["top_complaints"]


class TestInventory:
    """Test inventory operations."""

    def test_save_inventory(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        inventory = {
            "current_stock": 100,
            "reorder_point": 20,
            "monthly_velocity": 50,
        }

        db.save_inventory("B000001", "Test Product", inventory)
        items = db.get_inventory("B000001")

        assert len(items) == 1
        assert items[0]["current_stock"] == 100

    def test_upsert_inventory(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        db.save_inventory("B000001", "Test Product", {"current_stock": 100})
        db.save_inventory("B000001", "Test Product", {"current_stock": 50})

        items = db.get_inventory("B000001")
        assert len(items) == 1
        assert items[0]["current_stock"] == 50


class TestComments:
    """Test product comments."""

    def test_add_comment(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        db.add_comment("B000001", "User1", "Great product!")

        comments = db.get_comments("B000001")
        assert len(comments) == 1
        assert comments[0]["comment"] == "Great product!"


class TestTasks:
    """Test product tasks."""

    def test_add_task(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        db.add_task("B000001", "Test Product", "Order samples", priority="high")

        tasks = db.get_tasks("B000001")
        assert len(tasks) == 1
        assert tasks[0]["task"] == "Order samples"
        assert tasks[0]["status"] == "todo"

    def test_update_task_status(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        db.add_task("B000001", "Test Product", "Order samples")

        tasks = db.get_tasks("B000001")
        task_id = tasks[0]["id"]

        db.update_task_status(task_id, "done")
        tasks = db.get_tasks("B000001")
        assert tasks[0]["status"] == "done"

    def test_delete_task(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        db.add_task("B000001", "Test Product", "Order samples")

        tasks = db.get_tasks("B000001")
        task_id = tasks[0]["id"]

        db.delete_task(task_id)
        tasks = db.get_tasks("B000001")
        assert len(tasks) == 0


class TestCSVImportExport:
    """Test CSV import/export."""

    def test_export_and_import_suppliers(self, tmp_data_dir: Path):
        db = DatabaseManager(str(tmp_data_dir / "test.db"))
        db.add_supplier({"name": "Exported Supplier", "rating": 4.5})

        csv_path = str(tmp_data_dir / "suppliers.csv")
        exported = db.export_suppliers_to_csv(csv_path)
        assert exported == 1

        # Import into new database
        db2 = DatabaseManager(str(tmp_data_dir / "test2.db"))
        imported = db2.import_suppliers_from_csv(csv_path)
        assert imported == 1

        suppliers = db2.get_all_suppliers()
        assert suppliers[0]["name"] == "Exported Supplier"
