"""Comprehensive tests for suppliers_db and key_store modules."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from database.suppliers_db import (
    SUPPLIER_DATABASE,
    _fallback_supplier_match,
    get_all_suppliers,
    get_random_supplier,
    get_supplier_with_pricing,
    get_suppliers_for_category,
    match_suppliers_to_products,
)
from security.key_store import (
    HAS_CRYPTOGRAPHY,
    KeyStore,
    _derive_key,
    _get_machine_seed,
)


# ────────────────────────────────────────────────────────────────────
# suppliers_db tests
# ────────────────────────────────────────────────────────────────────


class TestGetSuppliersForCategory:
    def test_exact_match(self):
        result = get_suppliers_for_category("kitchen")
        assert result is SUPPLIER_DATABASE["kitchen"]
        assert len(result) == 4

    def test_partial_match(self):
        result = get_suppliers_for_category("my kitchen stuff")
        assert result is SUPPLIER_DATABASE["kitchen"]

    def test_no_match_returns_default(self):
        result = get_suppliers_for_category("nonexistent_xyz")
        assert result is SUPPLIER_DATABASE["default"]

    def test_empty_string_returns_default(self):
        result = get_suppliers_for_category("")
        assert result is SUPPLIER_DATABASE["default"]

    def test_case_insensitive(self):
        result = get_suppliers_for_category("KITCHEN")
        assert result is SUPPLIER_DATABASE["kitchen"]

    def test_known_category_electronics(self):
        result = get_suppliers_for_category("electronics")
        assert result is SUPPLIER_DATABASE["electronics"]
        assert result[0]["name"] == "Shenzhen AIB Electronics"

    def test_all_named_categories_covered(self):
        for category in SUPPLIER_DATABASE:
            if category == "default":
                continue
            result = get_suppliers_for_category(category)
            assert len(result) > 0, f"Category {category} returned empty"


class TestGetRandomSupplier:
    def test_returns_supplier(self):
        supplier = get_random_supplier("kitchen")
        assert supplier is not None
        assert "name" in supplier
        assert "email" in supplier

    def test_known_category(self):
        for _ in range(20):
            supplier = get_random_supplier("electronics")
            assert supplier["name"] in [
                s["name"] for s in SUPPLIER_DATABASE["electronics"]
            ]

    def test_returns_from_default_for_unknown(self):
        supplier = get_random_supplier("nonexistent_xyz")
        assert supplier["name"] in [
            s["name"] for s in SUPPLIER_DATABASE["default"]
        ]


class TestGetAllSuppliers:
    def test_count_greater_than_zero(self):
        suppliers = get_all_suppliers()
        assert len(suppliers) > 0

    def test_all_have_source_category(self):
        suppliers = get_all_suppliers()
        for s in suppliers:
            assert "source_category" in s
            assert s["source_category"] != "default"

    def test_default_excluded(self):
        suppliers = get_all_suppliers()
        for s in suppliers:
            assert s["source_category"] != "default"

    def test_does_not_mutate_original(self):
        original_default = SUPPLIER_DATABASE["default"].copy()
        get_all_suppliers()
        assert SUPPLIER_DATABASE["default"] == original_default

    def test_total_count_matches_database(self):
        expected = sum(
            len(sups)
            for cat, sups in SUPPLIER_DATABASE.items()
            if cat != "default"
        )
        assert len(get_all_suppliers()) == expected


class TestMatchSuppliersToProducts:
    def test_use_alibaba_false(self):
        products = [
            {"name": "Spoon", "category": "kitchen"},
            {"name": "USB Cable", "category": "electronics"},
        ]
        result = match_suppliers_to_products(products, use_alibaba=False)
        assert len(result) == 2
        for p in result:
            assert "supplier_name" in p
            assert "supplier_company" in p
            assert "supplier_email" in p
            assert p["supplier_price_source"] == "database"

    def test_alibaba_import_fails(self):
        products = [{"name": "Widget", "category": "kitchen"}]
        with patch(
            "builtins.__import__",
            side_effect=ImportError("no module"),
        ):
            result = match_suppliers_to_products(products, use_alibaba=True)
        assert result[0]["supplier_price_source"] == "database"

    def test_alibaba_returns_none_falls_back(self):
        mock_get = MagicMock(return_value=None)
        mock_module = MagicMock()
        mock_module.get_supplier_pricing = mock_get
        with patch(
            "builtins.__import__",
            side_effect=lambda name, *a, **kw: mock_module
            if name == "data_collectors.alibaba_scraper"
            else __import__(name, *a),
        ):
            products = [{"name": "Widget", "category": "kitchen"}]
            result = match_suppliers_to_products(products, use_alibaba=True)
        assert result[0]["supplier_price_source"] == "database"

    def test_alibaba_raises_exception_falls_back(self):
        mock_get = MagicMock(side_effect=RuntimeError("api error"))
        mock_module = MagicMock()
        mock_module.get_supplier_pricing = mock_get
        with patch(
            "builtins.__import__",
            side_effect=lambda name, *a, **kw: mock_module
            if name == "data_collectors.alibaba_scraper"
            else __import__(name, *a),
        ):
            products = [{"name": "Widget", "category": "kitchen"}]
            result = match_suppliers_to_products(products, use_alibaba=True)
        assert result[0]["supplier_price_source"] == "database"

    def test_empty_products(self):
        result = match_suppliers_to_products([], use_alibaba=False)
        assert result == []


class TestFallbackSupplierMatch:
    def test_all_fields_assigned(self):
        product = {"category": "kitchen", "name": "Whisk"}
        _fallback_supplier_match(product)
        required = [
            "supplier_name",
            "supplier_company",
            "supplier_email",
            "supplier_phone",
            "supplier_whatsapp",
            "supplier_website",
            "supplier_moq",
            "supplier_lead_time",
            "supplier_payment",
            "supplier_rating",
            "supplier_price_source",
        ]
        for field in required:
            assert field in product, f"Missing field: {field}"
        assert product["supplier_price_source"] == "database"

    def test_unknown_category_uses_default(self):
        product = {"category": "zzz_unknown"}
        _fallback_supplier_match(product)
        assert product["supplier_name"] in [
            s["name"] for s in SUPPLIER_DATABASE["default"]
        ]

    def test_missing_category_uses_default(self):
        product = {"name": "Something"}
        _fallback_supplier_match(product)
        assert "supplier_name" in product

    def test_multiple_calls_consistent(self):
        product = {"category": "kitchen"}
        _fallback_supplier_match(product)
        name1 = product["supplier_name"]
        product2 = {"category": "kitchen"}
        _fallback_supplier_match(product2)
        assert product2["supplier_name"] in [
            s["name"] for s in SUPPLIER_DATABASE["kitchen"]
        ]


class TestGetSupplierWithPricing:
    def test_alibaba_import_fails(self):
        with patch(
            "builtins.__import__",
            side_effect=ImportError("no module"),
        ):
            result = get_supplier_with_pricing("Widget", "kitchen", 29.99)
        assert "supplier_name" in result
        assert "supplier_price" in result
        assert result["supplier_price_source"] == "estimated"
        assert result["supplier_price"] > 0

    def test_alibaba_returns_data(self):
        alibaba_result = {
            "supplier_name": "Alibaba Supplier",
            "supplier_price": 5.0,
        }
        mock_get = MagicMock(return_value=alibaba_result)
        mock_module = MagicMock()
        mock_module.get_supplier_pricing = mock_get
        with patch(
            "builtins.__import__",
            side_effect=lambda name, *a, **kw: mock_module
            if name == "data_collectors.alibaba_scraper"
            else __import__(name, *a),
        ):
            result = get_supplier_with_pricing("Widget", "kitchen", 29.99)
        assert result["supplier_name"] == "Alibaba Supplier"

    def test_alibaba_returns_none_falls_back(self):
        mock_get = MagicMock(return_value=None)
        mock_module = MagicMock()
        mock_module.get_supplier_pricing = mock_get
        with patch(
            "builtins.__import__",
            side_effect=lambda name, *a, **kw: mock_module
            if name == "data_collectors.alibaba_scraper"
            else __import__(name, *a),
        ):
            result = get_supplier_with_pricing("Widget", "kitchen", 29.99)
        assert "supplier_name" in result
        assert result["supplier_price_source"] == "estimated"

    def test_alibaba_raises_exception_falls_back(self):
        mock_get = MagicMock(side_effect=RuntimeError("fail"))
        mock_module = MagicMock()
        mock_module.get_supplier_pricing = mock_get
        with patch(
            "builtins.__import__",
            side_effect=lambda name, *a, **kw: mock_module
            if name == "data_collectors.alibaba_scraper"
            else __import__(name, *a),
        ):
            result = get_supplier_with_pricing("Widget", "kitchen", 29.99)
        assert "supplier_price" in result
        assert 0 < result["supplier_price"] < 29.99

    def test_unknown_category_uses_default_ratio(self):
        with patch(
            "builtins.__import__",
            side_effect=ImportError("no module"),
        ):
            result = get_supplier_with_pricing("Thing", "zzz_unknown", 100.0)
        assert "supplier_price" in result
        assert 0 < result["supplier_price"] < 100.0

    def test_empty_category_returns_empty_dict(self):
        with patch(
            "builtins.__import__",
            side_effect=ImportError("no module"),
        ):
            with patch(
                "database.suppliers_db.get_suppliers_for_category",
                return_value=[],
            ):
                result = get_supplier_with_pricing("Thing", "", 50.0)
        assert result == {}

    def test_pricing_within_ratio_bounds(self):
        with patch(
            "builtins.__import__",
            side_effect=ImportError("no module"),
        ):
            for _ in range(50):
                result = get_supplier_with_pricing("Widget", "kitchen", 100.0)
                assert 10.0 <= result["supplier_price"] <= 22.0


# ────────────────────────────────────────────────────────────────────
# key_store tests
# ────────────────────────────────────────────────────────────────────


class TestMachineSeed:
    def test_returns_bytes(self):
        seed = _get_machine_seed()
        assert isinstance(seed, bytes)
        assert len(seed) == 32

    def test_deterministic(self):
        assert _get_machine_seed() == _get_machine_seed()


class TestDeriveKey:
    def test_returns_base64_key(self):
        import base64

        key = _derive_key()
        assert isinstance(key, bytes)
        decoded = base64.urlsafe_b64decode(key)
        assert len(decoded) == 32

    def test_deterministic(self):
        assert _derive_key() == _derive_key()


class TestKeyStoreInit:
    def test_creates_data_dir(self, tmp_path):
        store = KeyStore(str(tmp_path))
        assert os.path.isdir(store.data_dir)

    def test_custom_data_dir(self, tmp_path):
        custom = str(tmp_path / "custom_keys")
        store = KeyStore(custom)
        assert store.data_dir == custom

    def test_default_data_dir(self):
        store = KeyStore()
        assert os.path.isdir(store.data_dir)

    def test_internal_file_paths(self, tmp_path):
        store = KeyStore(str(tmp_path))
        assert store._keys_file == os.path.join(str(tmp_path), "keys.enc")
        assert store._legacy_file == os.path.join(
            str(tmp_path), "api_keys.json"
        )


class TestKeyStoreSaveAndLoad:
    def test_save_and_load_roundtrip(self, tmp_path):
        store = KeyStore(str(tmp_path))
        keys = {"openai": "sk-abc123", "claude": "sk-ant-xyz"}
        assert store.save(keys) is True
        loaded = store.load()
        assert loaded == keys

    def test_empty_values_filtered(self, tmp_path):
        store = KeyStore(str(tmp_path))
        keys = {"openai": "sk-abc", "empty": ""}
        store.save(keys)
        loaded = store.load()
        assert "empty" not in loaded
        assert loaded["openai"] == "sk-abc"

    def test_saved_at_filtered(self, tmp_path):
        store = KeyStore(str(tmp_path))
        keys = {"openai": "sk-abc", "saved_at": "2026-01-01"}
        store.save(keys)
        loaded = store.load()
        assert "saved_at" not in loaded

    def test_load_returns_copy(self, tmp_path):
        store = KeyStore(str(tmp_path))
        store.save({"key": "val"})
        loaded1 = store.load()
        loaded2 = store.load()
        loaded1["extra"] = "hack"
        assert "extra" not in loaded2

    def test_load_empty_store(self, tmp_path):
        store = KeyStore(str(tmp_path))
        assert store.load() == {}


class TestKeyStoreGet:
    def test_existing_key(self, tmp_path):
        store = KeyStore(str(tmp_path))
        store.save({"openai": "sk-abc"})
        assert store.get("openai") == "sk-abc"

    def test_missing_key(self, tmp_path):
        store = KeyStore(str(tmp_path))
        assert store.get("nonexistent") == ""


class TestKeyStoreDelete:
    def test_delete_existing(self, tmp_path):
        store = KeyStore(str(tmp_path))
        store.save({"a": "1", "b": "2"})
        assert store.delete("a") is True
        assert store.get("a") == ""
        assert store.get("b") == "2"

    def test_delete_nonexistent(self, tmp_path):
        store = KeyStore(str(tmp_path))
        assert store.delete("nope") is False


class TestKeyStoreClear:
    def test_clear_removes_file(self, tmp_path):
        store = KeyStore(str(tmp_path))
        store.save({"key": "val"})
        assert store.clear() is True
        assert not os.path.exists(store._keys_file)
        assert store.load() == {}

    def test_clear_no_file(self, tmp_path):
        store = KeyStore(str(tmp_path))
        assert store.clear() is True

    def test_clear_resets_cache(self, tmp_path):
        store = KeyStore(str(tmp_path))
        store.save({"key": "val"})
        store.clear()
        assert store._cache == {}


class TestKeyStoreHasKeys:
    def test_has_keys_true(self, tmp_path):
        store = KeyStore(str(tmp_path))
        store.save({"key": "val"})
        assert store.has_keys() is True

    def test_has_keys_false(self, tmp_path):
        store = KeyStore(str(tmp_path))
        assert store.has_keys() is False


class TestKeyStoreCache:
    def test_cache_populated_on_save(self, tmp_path):
        store = KeyStore(str(tmp_path))
        store.save({"key": "val"})
        assert store._cache == {"key": "val"}

    def test_cache_cleared_on_clear(self, tmp_path):
        store = KeyStore(str(tmp_path))
        store.save({"key": "val"})
        store.clear()
        assert store._cache == {}

    def test_load_returns_cache_if_available(self, tmp_path):
        store = KeyStore(str(tmp_path))
        store.save({"a": "1"})
        store._cache = {"x": "99"}
        assert store.load() == {"x": "99"}


class TestKeyStoreLegacyMigration:
    def test_migrates_legacy_file_with_fernet(self, tmp_path):
        legacy_path = str(tmp_path / "api_keys.json")
        with open(legacy_path, "w") as f:
            json.dump({"openai": "sk-legacy", "claude": "sk-ant-legacy"}, f)
        store = KeyStore(str(tmp_path))
        if store._fernet:
            loaded = store.load()
            assert loaded["openai"] == "sk-legacy"
            assert loaded["claude"] == "sk-ant-legacy"
            assert not os.path.exists(legacy_path)
        else:
            assert os.path.exists(legacy_path)

    def test_migrates_legacy_file_via_mock(self, tmp_path):
        legacy_path = str(tmp_path / "api_keys.json")
        with open(legacy_path, "w") as f:
            json.dump({"openai": "sk-legacy", "claude": "sk-ant-legacy"}, f)

        fake_fernet = MagicMock()
        fake_fernet.encrypt = MagicMock(
            side_effect=lambda data: b"encrypted:" + data
        )
        fake_fernet.decrypt = MagicMock(
            side_effect=lambda data: data.split(b"encrypted:", 1)[1]
        )
        store = KeyStore(str(tmp_path))
        store._fernet = fake_fernet
        store._migrate_legacy()

        loaded = store.load()
        assert loaded["openai"] == "sk-legacy"
        assert loaded["claude"] == "sk-ant-legacy"

    def test_no_legacy_file_no_crash(self, tmp_path):
        store = KeyStore(str(tmp_path))
        assert store.load() == {}

    def test_legacy_without_key_values_not_migrated(self, tmp_path):
        legacy_path = str(tmp_path / "api_keys.json")
        with open(legacy_path, "w") as f:
            json.dump({"random_key": "value"}, f)
        store = KeyStore(str(tmp_path))
        assert os.path.exists(legacy_path)

    def test_legacy_corrupt_json_ignored(self, tmp_path):
        legacy_path = str(tmp_path / "api_keys.json")
        with open(legacy_path, "w") as f:
            f.write("{invalid json!!")
        store = KeyStore(str(tmp_path))
        assert store.load() == {}

    def test_legacy_migration_exception_handled(self, tmp_path):
        legacy_path = str(tmp_path / "api_keys.json")
        with open(legacy_path, "w") as f:
            json.dump({"openai": "sk-legacy"}, f)

        fake_fernet = MagicMock()
        fake_fernet.encrypt.side_effect = RuntimeError("disk full")
        with patch.object(KeyStore, "_init_encryption"):
            store = KeyStore(str(tmp_path))
        store._fernet = fake_fernet
        store._migrate_legacy()

        assert store.load() == {}


class TestFallbackMode:
    def test_save_fallback(self, tmp_path):
        with patch("security.key_store.HAS_CRYPTOGRAPHY", False):
            store = KeyStore(str(tmp_path))
            store._fernet = None
            result = store.save({"openai": "sk-test"})
            assert result is True
            loaded = store.load()
            assert loaded["openai"] == "sk-test"

    def test_load_fallback_no_file(self, tmp_path):
        with patch("security.key_store.HAS_CRYPTOGRAPHY", False):
            store = KeyStore(str(tmp_path))
            store._fernet = None
            assert store.load() == {}

    def test_load_fallback_corrupt_file(self, tmp_path):
        enc_file = str(tmp_path / "keys.enc")
        with open(enc_file, "w") as f:
            f.write("not-valid-b85!!!")
        with patch("security.key_store.HAS_CRYPTOGRAPHY", False):
            store = KeyStore(str(tmp_path))
            store._fernet = None
            assert store.load() == {}

    def test_save_fallback_filters_empty_values(self, tmp_path):
        with patch("security.key_store.HAS_CRYPTOGRAPHY", False):
            store = KeyStore(str(tmp_path))
            store._fernet = None
            store.save({"a": "val", "b": ""})
            loaded = store.load()
            assert "b" not in loaded


class TestKeyStorePersistence:
    def test_keys_persist_across_instances(self, tmp_path):
        store1 = KeyStore(str(tmp_path))
        store1.save({"openai": "sk-persist"})
        store2 = KeyStore(str(tmp_path))
        assert store2.get("openai") == "sk-persist"

    def test_overwrite_keys(self, tmp_path):
        store = KeyStore(str(tmp_path))
        store.save({"key": "old"})
        store.save({"key": "new"})
        assert store.get("key") == "new"
