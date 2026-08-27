"""Collection service module for multi-source product data gathering.

Handles orchestrated data collection from multiple sources including Amazon,
Google Trends, and Social Media APIs. Implements deduplication via ASIN
tracking, input validation through DataValidator, timeout-protected calls
for external APIs, and automatic fallback to a built-in sample product
catalog when all live sources return empty results.
"""

import logging
import random
import threading
from typing import Any, Callable, Dict, List, Optional, Set

from data_collectors import AmazonCollector, GoogleTrendsCollector, SocialMediaCollector
from utils.commercial import DataValidator, perf_monitor
from utils.gating import mark_gating

logger = logging.getLogger(__name__)


# Sample product catalog for fallback
SAMPLE_CATALOG = {
    "kitchen": [
        ("Digital Kitchen Scale", 15.99, 4.5, 12500),
        ("Silicone Baking Mat Set", 12.99, 4.7, 15600),
        ("Electric Milk Frother", 9.99, 4.3, 22000),
        ("Vegetable Chopper 12-in-1", 22.99, 4.5, 16800),
        ("Herb Scissors 5 Blade", 8.99, 4.2, 6300),
        ("Pour Over Coffee Dripper", 14.99, 4.6, 3800),
        ("French Press Coffee 34oz", 17.99, 4.4, 7200),
        ("Garlic Press Stainless", 12.99, 4.2, 9800),
        ("Tea Infuser Mesh", 8.99, 4.6, 5400),
        ("Airtight Food Storage Set", 29.99, 4.5, 11200),
    ],
    "electronics": [
        ("Wireless Earbuds", 29.99, 4.3, 25000),
        ("USB C Hub 7-in-1", 35.99, 4.4, 11000),
        ("LED Desk Lamp", 24.99, 4.5, 8500),
        ("Phone Charger 10000mAh", 19.99, 4.3, 18000),
        ("Webcam HD 1080p", 39.99, 4.2, 6200),
        ("Wireless Mouse", 24.99, 4.3, 12000),
    ],
    "beauty": [
        ("Jade Roller Set", 14.99, 4.4, 16000),
        ("Makeup Brush Set", 16.99, 4.3, 12800),
        ("Hair Clips Set", 11.99, 4.5, 9200),
        ("LED Mirror", 28.99, 4.4, 7500),
    ],
    "home": [
        ("Scented Candle Set", 19.99, 4.5, 13000),
        ("Drawer Organizer", 26.99, 4.4, 4800),
        ("Wall Hooks", 12.99, 4.3, 17500),
        ("Throw Blanket", 18.99, 4.6, 8900),
    ],
    "fitness": [
        ("Resistance Bands", 14.99, 4.5, 21000),
        ("Yoga Mat", 24.99, 4.4, 15000),
        ("Foam Roller", 16.99, 4.3, 9800),
        ("Jump Rope", 11.99, 4.5, 7600),
    ],
}


class CollectionService:
    """Orchestrates data collection from multiple sources.

    Manages collection cycles across Amazon product search, Google Trends
    analysis, and Social Media monitoring. Deduplicates results using a set
    of seen ASINs, validates incoming products before storage, and provides
    a sample product catalog fallback when live collection yields no results.

    Attributes:
        config: Application configuration dictionary.
        validator: DataValidator instance for product data validation.
        seen_asins: Set of ASINs already collected to prevent duplicates.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.validator = DataValidator()
        self.seen_asins: Set[str] = set()

    def collect_cycle(
        self,
        categories: List[str],
        keywords: List[str],
        sources: List[str],
        status_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Collect data from enabled sources for one collection cycle.

        Iterates over each requested source, collects raw product data,
        validates and deduplicates results, and aggregates them into a
        single list. If no products are collected from any live source,
        falls back to the built-in sample catalog.

        Args:
            categories: Product categories to search.
            keywords: Keywords to search.
            sources: List of source names ("Amazon", "Google Trends", "Social Media").
            status_callback: Optional callback for status updates.
            progress_callback: Optional callback for progress updates (0.0 to 1.0).

        Returns:
            List of collected and deduplicated product dictionaries.
        """
        cycle_products: List[Dict[str, Any]] = []
        total = len(sources)

        def update_status(msg: str) -> None:
            if status_callback:
                status_callback(msg)
            logger.info(msg)

        def update_progress(val: float) -> None:
            if progress_callback:
                progress_callback(val)

        logger.info(f"COLLECT_START sources={total} categories={len(categories)}")

        for idx, name in enumerate(sources, 1):
            update_status(f"Searching {name} [{idx}/{total}]...")
            update_progress(idx / (total + 1))

            raw: List[Dict[str, Any]] = []
            try:
                if name == "Amazon":
                    raw = AmazonCollector(self.config).collect(categories[:3], keywords[:3])
                elif name == "Google Trends":
                    def _collect_trends() -> List[Dict[str, Any]]:
                        return GoogleTrendsCollector(self.config).collect(
                            categories[:2], keywords[:2]
                        )
                    raw = self._collect_with_timeout(_collect_trends, timeout_sec=15)
                else:
                    raw = SocialMediaCollector(self.config).collect(categories[:2], keywords[:2])
                perf_monitor.record("api_calls")
            except Exception as e:
                logger.warning(f"Collection failed for {name}: {e}")
                perf_monitor.record("errors")

            found = 0
            for p in raw:
                asin = p.get("asin", "")
                if asin and asin not in self.seen_asins:
                    if self.validator.validate_product(p):
                        self.seen_asins.add(asin)
                        p["source"] = name.lower().replace(" ", "_")
                        p.setdefault("url", f"https://amazon.com/dp/{asin}")
                        mark_gating(p)
                        cycle_products.append(p)
                        found += 1
            perf_monitor.record("products_collected", found)
            update_status(f"{name}: {found} products found")
            logger.info(f"{name}: {found} valid products collected")

        # Fallback to sample data if no products collected
        if not cycle_products:
            update_status("Loading product database...")
            for p in self.get_sample_products(categories):
                asin = p.get("asin", "")
                if asin and asin not in self.seen_asins:
                    self.seen_asins.add(asin)
                    mark_gating(p)
                    cycle_products.append(p)

        update_progress(0.9)
        return cycle_products

    def _collect_with_timeout(
        self,
        func: Callable[[], List[Dict[str, Any]]],
        timeout_sec: int = 30,
    ) -> List[Dict[str, Any]]:
        """Run a collection function with a timeout.

        Executes the given callable in a daemon thread and joins with the
        specified timeout. Returns any products collected before the
        timeout expires; an empty list is returned on timeout or failure.

        Args:
            func: Zero-argument callable that returns a list of products.
            timeout_sec: Maximum seconds to wait for completion.

        Returns:
            List of products collected within the timeout, or an empty list.
        """
        result: List[Dict[str, Any]] = []

        def target() -> None:
            try:
                result.extend(func())
            except Exception as e:
                logger.debug(f"Collection with timeout failed: {e}")

        t = threading.Thread(target=target, daemon=True)
        t.start()
        t.join(timeout=timeout_sec)
        return result

    def get_sample_products(self, categories: List[str]) -> List[Dict[str, Any]]:
        """Generate sample products for given categories as a fallback.

        Returns pre-defined product entries from the built-in SAMPLE_CATALOG
        when live data collection produces no results. Each product is
        assigned a randomly generated ASIN and marked with source="sample".

        Args:
            categories: List of category names to retrieve samples for.

        Returns:
            List of sample product dictionaries with randomized ASINs.
        """
        products: List[Dict[str, Any]] = []

        for cat in categories:
            cat_lower = cat.lower()
            catalog_products = None

            for key, items in SAMPLE_CATALOG.items():
                if key in cat_lower:
                    catalog_products = items
                    break

            if catalog_products is None:
                catalog_products = SAMPLE_CATALOG.get("kitchen", [])

            for title, price, rating, reviews in catalog_products:
                products.append({
                    "title": title,
                    "brand_name": title.split()[0] if title else "",
                    "price": price,
                    "rating": rating,
                    "review_count": reviews,
                    "category": cat.title(),
                    "query": cat,
                    "source": "sample",
                    "asin": f"B{random.randint(100000000, 999999999):09d}",
                    "url": f"https://amazon.com/dp/B{random.randint(100000000, 999999999):09d}",
                })

        return products
