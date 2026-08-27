"""Centralized path resolution for MarketLens.

All data/output paths are resolved from environment variables with sensible
defaults, eliminating hardcoded Windows paths throughout the codebase.

Environment variables:
    MLENS_DATA_DIR    – Base data directory (default: ./data)
    MLENS_OUTPUT_DIR  – Base output directory (default: ./output)
"""

import os
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)


def _default_data_dir() -> str:
    env = os.environ.get("MLENS_DATA_DIR")
    if env:
        return env
    return os.path.join(_project_root, "data")


def _default_output_dir() -> str:
    env = os.environ.get("MLENS_OUTPUT_DIR")
    if env:
        return env
    return os.path.join(_project_root, "output")


DATA_DIR = _default_data_dir()
OUTPUT_DIR = _default_output_dir()
DB_PATH = os.path.join(DATA_DIR, "marketlens.db")
CHARTS_DIR = os.path.join(OUTPUT_DIR, "charts")
EXPORTS_DIR = OUTPUT_DIR
KEYS_DIR = DATA_DIR
LICENSE_DIR = DATA_DIR
USERS_FILE = os.path.join(DATA_DIR, "users.json")
PRODUCTS_FILE = os.path.join(DATA_DIR, "products.json")
NOTES_FILE = os.path.join(DATA_DIR, "product_notes.json")
SEEN_ASINS_FILE = os.path.join(DATA_DIR, "seen_asins.json")
EXCLUDED_FILE = os.path.join(DATA_DIR, "excluded_products.json")


def ensure_dirs():
    """Create all required directories at startup."""
    for d in (DATA_DIR, OUTPUT_DIR, CHARTS_DIR):
        os.makedirs(d, exist_ok=True)
