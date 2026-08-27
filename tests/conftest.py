"""Shared test fixtures for MarketLens."""

import os
import sys
import tempfile
import warnings
import shutil
from pathlib import Path
from typing import Generator

import pytest

# Add project root to path
PROJECT_ROOT = str(Path(__file__).parent.parent)
sys.path.insert(0, PROJECT_ROOT)

# Suppress sqlite3 ResourceWarnings from nested connections in DatabaseManager.
# All connections use `with` statements; Python 3.14's stricter tracking fires
# spurious warnings when an inner connection is opened inside an outer one.
warnings.filterwarnings("ignore", message="unclosed database", category=ResourceWarning)


@pytest.fixture
def tmp_data_dir() -> Generator[Path, None, None]:
    """Create a temporary data directory for tests."""
    tmpdir = Path(tempfile.mkdtemp(prefix="marketlens_test_"))
    yield tmpdir
    # Cleanup with retry for Windows file locking
    import time
    for _ in range(3):
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
            break
        except Exception:
            time.sleep(0.1)


@pytest.fixture
def sample_product() -> dict:
    """Return a sample product dictionary."""
    return {
        "asin": "B0TEST123",
        "name": "Test Product",
        "title": "Test Product Title",
        "category": "Kitchen",
        "amazon_price": 29.99,
        "rating": 4.5,
        "review_count": 1250,
        "ai_score": 0.75,
        "estimated_margin_pct": 35.0,
        "score": 0.72,
        "supplier_cost": 8.50,
        "shipping_cost": 2.00,
    }


@pytest.fixture
def sample_products() -> list:
    """Return a list of sample products."""
    return [
        {
            "asin": "B000001",
            "name": "Product One",
            "category": "Kitchen",
            "amazon_price": 19.99,
            "rating": 4.3,
            "review_count": 5000,
            "ai_score": 0.65,
            "estimated_margin_pct": 30.0,
            "score": 0.60,
        },
        {
            "asin": "B000002",
            "name": "Product Two",
            "category": "Electronics",
            "amazon_price": 49.99,
            "rating": 4.7,
            "review_count": 12000,
            "ai_score": 0.85,
            "estimated_margin_pct": 45.0,
            "score": 0.82,
        },
        {
            "asin": "B000003",
            "name": "Product Three",
            "category": "Beauty",
            "amazon_price": 14.99,
            "rating": 4.1,
            "review_count": 800,
            "ai_score": 0.55,
            "estimated_margin_pct": 25.0,
            "score": 0.48,
        },
    ]


@pytest.fixture
def sample_config() -> dict:
    """Return a sample configuration dictionary."""
    return {
        "min_profit_margin": 30.0,
        "max_competition": 50,
        "min_demand_score": 0.3,
        "min_review_count": 10,
        "output_dir": "output",
        "log_level": "INFO",
        "data_sources": {
            "google_trends": True,
            "amazon": True,
            "social_media": True,
        },
    }
