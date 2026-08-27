"""Tests for security.key_store module."""

import json
import os
from pathlib import Path
from typing import Generator

import pytest

from security.key_store import KeyStore, _get_machine_seed, _derive_key


class TestMachineSeed:
    """Test machine-specific seed generation."""

    def test_returns_bytes(self):
        seed = _get_machine_seed()
        assert isinstance(seed, bytes)

    def test_consistent_across_calls(self):
        seed1 = _get_machine_seed()
        seed2 = _get_machine_seed()
        assert seed1 == seed2

    def test_deterministic_per_machine(self):
        seed = _get_machine_seed()
        assert len(seed) == 32  # SHA-256 digest


class TestKeyDerivation:
    """Test Fernet key derivation."""

    def test_returns_bytes(self):
        key = _derive_key()
        assert isinstance(key, bytes)

    def test_valid_fernet_key_length(self):
        key = _derive_key()
        # Fernet keys are 32 bytes base64-encoded = 44 bytes
        assert len(key) == 44

    def test_consistent_across_calls(self):
        key1 = _derive_key()
        key2 = _derive_key()
        assert key1 == key2


class TestKeyStore:
    """Test KeyStore encrypted storage."""

    def test_init_creates_directory(self, tmp_data_dir: Path):
        store = KeyStore(str(tmp_data_dir))
        assert tmp_data_dir.exists()

    def test_save_and_load(self, tmp_data_dir: Path):
        store = KeyStore(str(tmp_data_dir))
        keys = {"openai": "sk-test123", "claude": "sk-ant-test456"}

        assert store.save(keys) is True
        loaded = store.load()

        assert loaded["openai"] == "sk-test123"
        assert loaded["claude"] == "sk-ant-test456"

    def test_get_single_key(self, tmp_data_dir: Path):
        store = KeyStore(str(tmp_data_dir))
        store.save({"openai": "sk-test123"})

        assert store.get("openai") == "sk-test123"
        assert store.get("nonexistent") == ""

    def test_has_keys(self, tmp_data_dir: Path):
        store = KeyStore(str(tmp_data_dir))
        assert store.has_keys() is False

        store.save({"openai": "sk-test123"})
        assert store.has_keys() is True

    def test_delete_key(self, tmp_data_dir: Path):
        store = KeyStore(str(tmp_data_dir))
        store.save({"openai": "sk-test123", "claude": "sk-ant-test456"})

        assert store.delete("openai") is True
        loaded = store.load()
        assert "openai" not in loaded
        assert loaded["claude"] == "sk-ant-test456"

    def test_delete_nonexistent_key(self, tmp_data_dir: Path):
        store = KeyStore(str(tmp_data_dir))
        assert store.delete("nonexistent") is False

    def test_clear(self, tmp_data_dir: Path):
        store = KeyStore(str(tmp_data_dir))
        store.save({"openai": "sk-test123"})

        assert store.clear() is True
        assert store.has_keys() is False

    def test_empty_save(self, tmp_data_dir: Path):
        store = KeyStore(str(tmp_data_dir))
        assert store.save({}) is True

    def test_filters_empty_values(self, tmp_data_dir: Path):
        store = KeyStore(str(tmp_data_dir))
        store.save({"openai": "sk-test123", "claude": "", "empty": ""})

        loaded = store.load()
        assert "openai" in loaded
        assert "claude" not in loaded
        assert "empty" not in loaded

    def test_filters_saved_at_key(self, tmp_data_dir: Path):
        store = KeyStore(str(tmp_data_dir))
        store.save({"openai": "sk-test123", "saved_at": "2024-01-01"})

        loaded = store.load()
        assert "saved_at" not in loaded

    def test_encrypted_file_is_not_json(self, tmp_data_dir: Path):
        store = KeyStore(str(tmp_data_dir))
        store.save({"openai": "sk-test123"})

        keys_file = tmp_data_dir / "keys.enc"
        assert keys_file.exists()

        with open(keys_file, "rb") as f:
            content = f.read()

        # Should not be readable as JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads(content)

    def test_cache_returns_copy(self, tmp_data_dir: Path):
        store = KeyStore(str(tmp_data_dir))
        store.save({"openai": "sk-test123"})

        loaded1 = store.load()
        loaded2 = store.load()

        assert loaded1 == loaded2
        assert loaded1 is not loaded2  # Different dict objects
