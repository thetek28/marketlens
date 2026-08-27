"""Data Source Abstraction Layer for MarketLens.

Provides a standardized interface for all external data sources.
Every connector implements DataSource and returns NormalizedProduct records.
"""

from .base import (
    DataSource,
    DataSourceStatus,
    DataFreshness,
    DataSourceConfig,
    NormalizedProduct,
    NormalizedTrend,
    NormalizedKeyword,
    NormalizedSupplier,
    SourceAttribution,
)
from .registry import DataSourceRegistry

__all__ = [
    "DataSource",
    "DataSourceStatus",
    "DataFreshness",
    "DataSourceConfig",
    "NormalizedProduct",
    "NormalizedTrend",
    "NormalizedKeyword",
    "NormalizedSupplier",
    "SourceAttribution",
    "DataSourceRegistry",
]
