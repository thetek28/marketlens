"""Data Validation, Normalization, and Deduplication Pipeline.

Ensures all data entering the database is valid, normalized,
and deduplicated. Rejects malformed records instead of faking values.
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .base import NormalizedProduct, NormalizedTrend, NormalizedKeyword, NormalizedSupplier

logger = logging.getLogger(__name__)

# Valid ASIN pattern: starts with B0 followed by 8 alphanumeric characters
ASIN_PATTERN = re.compile(r'^B0[A-Z0-9]{8}$')

# Supported marketplaces
VALID_MARKETPLACES = {"US", "UK", "DE", "FR", "CA", "JP", "IT", "ES", "AU", "IN"}

# Price sanity bounds (USD)
MIN_PRICE = 0.01
MAX_PRICE = 100000.0

# Rating bounds
MIN_RATING = 0.0
MAX_RATING = 5.0

# Review count bounds
MIN_REVIEWS = 0
MAX_REVIEWS = 10_000_000

# Sales rank bounds (1 = best)
MIN_RANK = 0
MAX_RANK = 10_000_000


class DataValidator:
    """Validates data before it enters the database."""

    def __init__(self, strict: bool = True):
        self.strict = strict
        self._rejected_count = 0
        self._validated_count = 0

    @property
    def stats(self) -> Dict[str, int]:
        return {"validated": self._validated_count, "rejected": self._rejected_count}

    def validate_product(self, product: NormalizedProduct) -> Tuple[bool, List[str]]:
        """Validate a product. Returns (is_valid, list_of_errors)."""
        errors = []

        # ASIN validation
        if product.asin:
            if not ASIN_PATTERN.match(product.asin):
                errors.append(f"Invalid ASIN format: {product.asin}")

        # Title validation
        if not product.title or len(product.title.strip()) < 5:
            errors.append("Title too short or missing")

        # Price validation
        if product.price < MIN_PRICE:
            if self.strict:
                errors.append(f"Price too low: {product.price}")
        elif product.price > MAX_PRICE:
            if self.strict:
                errors.append(f"Price too high: {product.price}")

        # Rating validation
        if product.rating < MIN_RATING or product.rating > MAX_RATING:
            if self.strict:
                errors.append(f"Rating out of range: {product.rating}")

        # Review count validation
        if product.review_count < MIN_REVIEWS or product.review_count > MAX_REVIEWS:
            if self.strict:
                errors.append(f"Review count out of range: {product.review_count}")

        # Sales rank validation
        if product.sales_rank < MIN_RANK or product.sales_rank > MAX_RANK:
            if self.strict:
                errors.append(f"Sales rank out of range: {product.sales_rank}")

        # Marketplace validation
        if product.marketplace and product.marketplace not in VALID_MARKETPLACES:
            errors.append(f"Invalid marketplace: {product.marketplace}")

        # URL validation
        if product.product_url and not product.product_url.startswith(("http://", "https://")):
            errors.append(f"Invalid URL: {product.product_url}")

        is_valid = len(errors) == 0
        if is_valid:
            self._validated_count += 1
        else:
            self._rejected_count += 1
            logger.warning("Product validation failed for %s: %s", product.asin, errors)

        return is_valid, errors

    def validate_trend(self, trend: NormalizedTrend) -> Tuple[bool, List[str]]:
        """Validate a trend record."""
        errors = []

        if not trend.keyword or len(trend.keyword.strip()) < 1:
            errors.append("Keyword missing")

        if trend.interest < 0:
            errors.append(f"Invalid interest value: {trend.interest}")

        is_valid = len(errors) == 0
        if not is_valid:
            self._rejected_count += 1
        else:
            self._validated_count += 1

        return is_valid, errors

    def validate_keyword(self, keyword: NormalizedKeyword) -> Tuple[bool, List[str]]:
        """Validate a keyword record."""
        errors = []

        if not keyword.keyword or len(keyword.keyword.strip()) < 1:
            errors.append("Keyword missing")

        if keyword.search_volume is not None and keyword.search_volume < 0:
            errors.append(f"Invalid search volume: {keyword.search_volume}")

        is_valid = len(errors) == 0
        if not is_valid:
            self._rejected_count += 1
        else:
            self._validated_count += 1

        return is_valid, errors

    def validate_supplier(self, supplier: NormalizedSupplier) -> Tuple[bool, List[str]]:
        """Validate a supplier record."""
        errors = []

        if not supplier.supplier_name or len(supplier.supplier_name.strip()) < 2:
            errors.append("Supplier name too short or missing")

        if supplier.supplier_price < 0:
            errors.append(f"Invalid supplier price: {supplier.supplier_price}")

        if supplier.moq < 0:
            errors.append(f"Invalid MOQ: {supplier.moq}")

        is_valid = len(errors) == 0
        if not is_valid:
            self._rejected_count += 1
        else:
            self._validated_count += 1

        return is_valid, errors


class DataNormalizer:
    """Normalizes data from different sources into common format."""

    CURRENCY_SYMBOLS = {
        "$": "USD", "£": "GBP", "€": "EUR", "¥": "JPY",
        "A$": "AUD", "C$": "CAD", "₹": "INR",
    }

    def normalize_product(self, product: NormalizedProduct) -> NormalizedProduct:
        """Normalize a product record."""
        # Normalize ASIN
        if product.asin:
            product.asin = product.asin.strip().upper()

        # Normalize title
        if product.title:
            product.title = product.title.strip()

        # Normalize brand
        if product.brand:
            product.brand = product.brand.strip()

        # Normalize category
        if product.category:
            product.category = self._normalize_category(product.category)

        # Normalize price
        product.price = round(max(product.price, 0), 2)

        # Normalize rating
        product.rating = round(max(min(product.rating, 5.0), 0.0), 1)

        # Normalize review count
        product.review_count = max(int(product.review_count), 0)

        # Normalize marketplace
        if product.marketplace:
            product.marketplace = product.marketplace.upper()

        # Normalize currency
        if product.currency:
            product.currency = product.currency.upper()

        return product

    def normalize_trend(self, trend: NormalizedTrend) -> NormalizedTrend:
        """Normalize a trend record."""
        if trend.keyword:
            trend.keyword = trend.keyword.strip().lower()

        if trend.trend_direction not in ("rising", "stable", "falling"):
            trend.trend_direction = "stable"

        return trend

    def normalize_keyword(self, keyword: NormalizedKeyword) -> NormalizedKeyword:
        """Normalize a keyword record."""
        if keyword.keyword:
            keyword.keyword = keyword.keyword.strip().lower()

        if keyword.search_volume is not None:
            keyword.search_volume = max(int(keyword.search_volume), 0)

        if keyword.competition is not None:
            keyword.competition = max(min(float(keyword.competition), 1.0), 0.0)

        return keyword

    def _normalize_category(self, category: str) -> str:
        """Normalize category names."""
        category_map = {
            "home & kitchen": "Home & Kitchen",
            "home-garden": "Home & Kitchen",
            "home garden": "Home & Kitchen",
            "electronics": "Electronics",
            "beauty": "Beauty",
            "beauty & personal care": "Beauty",
            "sports & outdoors": "Sports",
            "sports": "Sports",
            "health": "Health",
            "health & household": "Health",
            "toys & games": "Toys",
            "toys": "Toys",
            "office products": "Office",
            "office": "Office",
            "pet supplies": "Pet Supplies",
            "pets": "Pet Supplies",
            "garden": "Garden",
        }
        return category_map.get(category.lower(), category)


class DataDeduplicator:
    """Deduplicates products by ASIN+marketplace."""

    def __init__(self):
        self._seen = {}
        self._duplicate_count = 0

    @property
    def stats(self) -> Dict[str, int]:
        return {"unique": len(self._seen), "duplicates": self._duplicate_count}

    def deduplicate_products(self, products: List[NormalizedProduct]) -> List[NormalizedProduct]:
        """Remove duplicate products. Keep the most recent version."""
        unique = []
        for product in products:
            key = (product.asin, product.marketplace)
            if not product.asin:
                # No ASIN - can't deduplicate, include it
                unique.append(product)
                continue

            if key not in self._seen:
                self._seen[key] = product
                unique.append(product)
            else:
                existing = self._seen[key]
                # Keep the newer one
                if product.source.retrieved_at and existing.source.retrieved_at:
                    if product.source.retrieved_at > existing.source.retrieved_at:
                        self._seen[key] = product
                        # Replace in unique list
                        for i, p in enumerate(unique):
                            if (p.asin, p.marketplace) == key:
                                unique[i] = product
                                break
                self._duplicate_count += 1

        return unique

    def deduplicate_trends(self, trends: List[NormalizedTrend]) -> List[NormalizedTrend]:
        """Remove duplicate trends by keyword."""
        seen = set()
        unique = []
        for trend in trends:
            key = trend.keyword.lower()
            if key not in seen:
                seen.add(key)
                unique.append(trend)
        return unique

    def deduplicate_keywords(self, keywords: List[NormalizedKeyword]) -> List[NormalizedKeyword]:
        """Remove duplicate keywords."""
        seen = set()
        unique = []
        for kw in keywords:
            key = kw.keyword.lower()
            if key not in seen:
                seen.add(key)
                unique.append(kw)
        return unique

    def reset(self):
        """Reset deduplication state."""
        self._seen.clear()
        self._duplicate_count = 0


class DataPipeline:
    """Complete validation, normalization, and deduplication pipeline."""

    def __init__(self, strict_validation: bool = True):
        self.validator = DataValidator(strict=strict_validation)
        self.normalizer = DataNormalizer()
        self.deduplicator = DataDeduplicator()

    def process_products(self, products: List[NormalizedProduct]) -> List[NormalizedProduct]:
        """Run products through the complete pipeline."""
        processed = []
        for product in products:
            # Normalize first
            product = self.normalizer.normalize_product(product)

            # Validate
            is_valid, errors = self.validator.validate_product(product)
            if not is_valid:
                logger.debug("Rejected product %s: %s", product.asin, errors)
                continue

            processed.append(product)

        # Deduplicate
        processed = self.deduplicator.deduplicate_products(processed)
        return processed

    def process_trends(self, trends: List[NormalizedTrend]) -> List[NormalizedTrend]:
        """Run trends through the pipeline."""
        processed = []
        for trend in trends:
            trend = self.normalizer.normalize_trend(trend)
            is_valid, _ = self.validator.validate_trend(trend)
            if is_valid:
                processed.append(trend)
        return self.deduplicator.deduplicate_trends(processed)

    def process_keywords(self, keywords: List[NormalizedKeyword]) -> List[NormalizedKeyword]:
        """Run keywords through the pipeline."""
        processed = []
        for kw in keywords:
            kw = self.normalizer.normalize_keyword(kw)
            is_valid, _ = self.validator.validate_keyword(kw)
            if is_valid:
                processed.append(kw)
        return self.deduplicator.deduplicate_keywords(processed)

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        return {
            "validator": self.validator.stats,
            "deduplicator": self.deduplicator.stats,
        }
