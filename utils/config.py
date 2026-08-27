"""Configuration management."""

import os
import sys
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv

if getattr(sys, 'frozen', False):
    _CFG_BASE = os.path.dirname(os.path.dirname(sys.executable))
else:
    _CFG_BASE = str(Path(__file__).resolve().parent.parent)


class Config:
    """Central configuration loaded from env + YAML."""

    DEFAULTS = {
        "min_profit_margin": 30.0,
        "max_competition": 50,
        "min_demand_score": 0.3,
        "min_review_count": 10,
        "output_dir": os.environ.get("MLENS_OUTPUT_DIR", os.path.join(_CFG_BASE, "output")),
        "log_level": os.environ.get("MLENS_LOG_LEVEL", "INFO"),
        "data_sources": {
            "google_trends": True,
            "amazon": True,
            "social_media": True,
        },
        "categories": [],
        "keywords": [],
    }

    def __init__(self, config_path: Optional[str] = None):
        load_dotenv()

        import copy
        self._config = copy.deepcopy(self.DEFAULTS)

        if config_path is None:
            default_yaml = os.path.join(_CFG_BASE, "config.yaml")
            if os.path.exists(default_yaml):
                config_path = default_yaml

        if config_path and Path(config_path).exists():
            self._load_yaml(config_path)

        self._apply_env_overrides()

    def _load_yaml(self, path: str):
        """Load configuration from YAML file."""
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f) or {}
            self._deep_update(self._config, data)
        except Exception as e:
            print(f"Warning: Could not load config from {path}: {e}")

    def _apply_env_overrides(self):
        """Override config values from environment variables."""
        env_map = {
            "API_MIN_PROFIT_MARGIN": ("min_profit_margin", float),
            "API_MAX_COMPETITION": ("max_competition", int),
            "API_LOG_LEVEL": ("log_level", str),
            "API_OUTPUT_DIR": ("output_dir", str),
        }

        for env_var, (key, cast_fn) in env_map.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    self._config[key] = cast_fn(value)
                except (ValueError, TypeError):
                    pass

    def _deep_update(self, base: dict, update: dict):
        """Recursively update nested dict."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_update(base[key], value)
            else:
                base[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value with optional default."""
        keys = key.split(".")
        value: Any = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return self._config.get(name)

    def __repr__(self) -> str:
        return f"Config({self._config})"
