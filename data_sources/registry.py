"""Data Source Registry - manages all connected data sources.

Central registry that holds all configured data sources, handles
routing queries to appropriate sources, and manages source health.
"""

import logging
from typing import Any, Dict, List, Optional

from .base import (
    DataSource,
    DataSourceConfig,
    DataSourceStatus,
    NormalizedKeyword,
    NormalizedProduct,
    NormalizedSupplier,
    NormalizedTrend,
)

logger = logging.getLogger(__name__)


class DataSourceRegistry:
    """Central registry for all data source connectors."""

    def __init__(self):
        self._sources: Dict[str, DataSource] = {}
        self._configs: Dict[str, DataSourceConfig] = {}

    def register(self, source: DataSource):
        """Register a data source."""
        self._sources[source.source_id] = source
        logger.info("Registered data source: %s (%s)", source.source_name, source.source_id)

    def unregister(self, source_id: str):
        """Remove a data source."""
        self._sources.pop(source_id, None)

    def get(self, source_id: str) -> Optional[DataSource]:
        """Get a specific source."""
        return self._sources.get(source_id)

    def all(self) -> List[DataSource]:
        """Get all registered sources."""
        return list(self._sources.values())

    def connected(self) -> List[DataSource]:
        """Get all connected sources."""
        return [s for s in self._sources.values() if s.status == DataSourceStatus.CONNECTED]

    def search_products(self, query: str, marketplace: str = "US",
                        max_results: int = 20,
                        sources: Optional[List[str]] = None) -> List[NormalizedProduct]:
        """Search products across all configured sources."""
        all_products = []
        target_sources = self._resolve_sources(sources)

        for source in target_sources:
            try:
                if not source._check_rate_limit():
                    logger.warning("Source %s rate limited, skipping", source.source_id)
                    continue
                products = source.search_products(query, marketplace, max_results)
                all_products.extend(products)
                source._record_request()
                source._status = DataSourceStatus.CONNECTED
            except Exception as e:
                source._record_error(str(e))
                logger.error("Source %s failed: %s", source.source_id, e)

        return self._deduplicate(all_products)

    def get_product(self, asin: str, marketplace: str = "US",
                    sources: Optional[List[str]] = None) -> Optional[NormalizedProduct]:
        """Get a single product from the best available source."""
        target_sources = self._resolve_sources(sources)

        for source in target_sources:
            try:
                product = source.get_product(asin, marketplace)
                if product:
                    source._record_request()
                    return product
            except Exception as e:
                source._record_error(str(e))
                logger.error("Source %s failed for ASIN %s: %s", source.source_id, asin, e)

        return None

    def get_trends(self, keywords: List[str], marketplace: str = "US",
                   sources: Optional[List[str]] = None) -> List[NormalizedTrend]:
        """Get trend data from all configured trend sources."""
        all_trends = []
        target_sources = self._resolve_sources(sources)

        for source in target_sources:
            try:
                trends = source.get_trends(keywords, marketplace)
                all_trends.extend(trends)
                source._record_request()
            except Exception as e:
                source._record_error(str(e))
                logger.error("Source %s trends failed: %s", source.source_id, e)

        return all_trends

    def get_keywords(self, query: str, marketplace: str = "US",
                     sources: Optional[List[str]] = None) -> List[NormalizedKeyword]:
        """Get keyword data from all configured keyword sources."""
        all_keywords = []
        target_sources = self._resolve_sources(sources)

        for source in target_sources:
            try:
                keywords = source.get_keywords(query, marketplace)
                all_keywords.extend(keywords)
                source._record_request()
            except Exception as e:
                source._record_error(str(e))
                logger.error("Source %s keywords failed: %s", source.source_id, e)

        return all_keywords

    def get_suppliers(self, product_name: str, category: str = "",
                      sources: Optional[List[str]] = None) -> List[NormalizedSupplier]:
        """Get supplier data from all configured supplier sources."""
        all_suppliers = []
        target_sources = self._resolve_sources(sources)

        for source in target_sources:
            try:
                suppliers = source.get_suppliers(product_name, category)
                all_suppliers.extend(suppliers)
                source._record_request()
            except Exception as e:
                source._record_error(str(e))
                logger.error("Source %s suppliers failed: %s", source.source_id, e)

        return all_suppliers

    def get_health(self) -> List[Dict[str, Any]]:
        """Get health status of all sources."""
        return [source.get_health() for source in self._sources.values()]

    def get_status_summary(self) -> Dict[str, Any]:
        """Get overall registry status."""
        sources = list(self._sources.values())
        connected = sum(1 for s in sources if s.status == DataSourceStatus.CONNECTED)
        errors = sum(1 for s in sources if s.status == DataSourceStatus.ERROR)
        return {
            "total_sources": len(sources),
            "connected": connected,
            "errors": errors,
            "disconnected": len(sources) - connected - errors,
            "sources": self.get_health(),
        }

    def _resolve_sources(self, source_ids: Optional[List[str]] = None) -> List[DataSource]:
        """Resolve which sources to use."""
        if not source_ids:
            return [s for s in self._sources.values() if s.config.enabled]
        return [self._sources[sid] for sid in source_ids if sid in self._sources]

    def _deduplicate(self, products: List[NormalizedProduct]) -> List[NormalizedProduct]:
        """Remove duplicate products by ASIN+marketplace."""
        seen = set()
        unique = []
        for p in products:
            key = (p.asin, p.marketplace)
            if key not in seen and p.asin:
                seen.add(key)
                unique.append(p)
        return unique


# Global registry instance
registry = DataSourceRegistry()
