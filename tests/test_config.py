"""Tests for utils.config module."""

import os
from pathlib import Path

import pytest
import yaml

from utils.config import Config


class TestConfigInit:
    """Test Config initialization."""

    def test_default_config(self, tmp_data_dir: Path):
        config = Config(str(tmp_data_dir / "nonexistent.yaml"))
        assert config.get("min_profit_margin") == 30.0
        assert config.get("max_competition") == 50

    def test_loads_yaml(self, tmp_data_dir: Path):
        yaml_file = tmp_data_dir / "config.yaml"
        yaml_file.write_text(yaml.dump({
            "min_profit_margin": 25.0,
            "max_competition": 100,
        }))

        config = Config(str(yaml_file))
        assert config.get("min_profit_margin") == 25.0
        assert config.get("max_competition") == 100

    def test_nested_yaml(self, tmp_data_dir: Path):
        yaml_file = tmp_data_dir / "config.yaml"
        yaml_file.write_text(yaml.dump({
            "data_sources": {
                "google_trends": False,
                "amazon": True,
            }
        }))

        config = Config(str(yaml_file))
        assert config.get("data_sources.google_trends") is False
        assert config.get("data_sources.amazon") is True


class TestConfigGet:
    """Test Config.get method."""

    def test_get_existing_key(self):
        config = Config()
        assert config.get("min_profit_margin") == 30.0

    def test_get_with_default(self):
        config = Config()
        assert config.get("nonexistent_key", "default") == "default"

    def test_get_nested_key(self):
        config = Config()
        assert config.get("data_sources.amazon") is True

    def test_get_nonexistent_nested(self):
        config = Config()
        assert config.get("data_sources.nonexistent") is None

    def test_get_deep_nested(self):
        config = Config()
        # Should return None for deep nested non-existent
        assert config.get("a.b.c.d") is None


class TestConfigEnvOverrides:
    """Test environment variable overrides."""

    def test_env_override(self, tmp_data_dir: Path, monkeypatch):
        monkeypatch.setenv("API_MIN_PROFIT_MARGIN", "45.0")
        config = Config()
        assert config.get("min_profit_margin") == 45.0

    def test_env_override_int(self, tmp_data_dir: Path, monkeypatch):
        monkeypatch.setenv("API_MAX_COMPETITION", "100")
        config = Config()
        assert config.get("max_competition") == 100

    def test_env_override_invalid_ignored(self, tmp_data_dir: Path, monkeypatch):
        monkeypatch.setenv("API_MAX_COMPETITION", "not_a_number")
        config = Config()
        # Should keep default
        assert config.get("max_competition") == 50


class TestConfigAttributeAccess:
    """Test Config attribute-style access."""

    def test_attr_access(self):
        config = Config()
        assert config.min_profit_margin == 30.0
        assert config.max_competition == 50

    def test_attr_nonexistent(self):
        config = Config()
        assert config.nonexistent is None

    def test_private_attr_raises(self):
        config = Config()
        with pytest.raises(AttributeError):
            _ = config._private


class TestConfigRepr:
    """Test Config representation."""

    def test_repr(self):
        config = Config()
        r = repr(config)
        assert "Config" in r
        assert "min_profit_margin" in r
