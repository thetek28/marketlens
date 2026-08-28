"""Product Identity Service.

Responsible for:
- Product identity resolution (ASIN-first hierarchy)
- Title normalization
- URL canonicalization
- Fuzzy duplicate detection
- Product merging with audit trail
- Source provenance tracking
"""

import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SCORING_VERSION = "v2.4"

# ─── Title Normalization ────────────────────────────────────

# Words to strip from titles for comparison
STRIP_WORDS = {
    "the", "a", "an", "for", "and", "or", "of", "with", "in", "on", "at", "to",
    "new", "original", "genuine", "authentic", "official", "premium", "pro",
    "plus", "max", "ultra", "super", "mega", "mini", "micro", "nano",
}

# Trademark / special char mappings
CHAR_MAP = {
    "\u2122": "",   # ™
    "\u00ae": "",   # ®
    "\u00a9": "",   # ©
    "\u2019": "'",  # right single quote
    "\u2018": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2026": "...",
}

# Unit normalizations
UNIT_MAP = {
    "watt": "w", "watts": "w", "wattage": "w",
    "inch": "in", "inches": "in",
    "ounce": "oz", "ounces": "oz",
    "pound": "lb", "pounds": "lb",
    "millimeter": "mm", "millimeters": "mm",
    "centimeter": "cm", "centimeters": "cm",
    "kilogram": "kg", "kilograms": "kg",
    "gram": "g", "grams": "g",
    "liter": "l", "liters": "l", "litre": "l", "litres": "l",
    "gallon": "gal", "gallons": "gal",
    "mah": "mah",
    "gb": "gb", "tb": "tb", "mb": "mb",
}

ASIN_PATTERN = re.compile(r'^B[0-9A-Z]{9}$', re.IGNORECASE)
URL_TRACKING_PARAMS = re.compile(r'[?&](ref|tag|utm_\w+|linkCode|creative|camp|ascsub|sp_id|sp_aid|psc|th)=[^&]*')
URL_REMAINING_QMARK = re.compile(r'[?]&')
URL_REMAINING_AMP = re.compile(r'&$')


def normalize_title(title: str) -> str:
    """Normalize a product title for duplicate comparison.

    Steps:
    1. Unicode normalize
    2. Replace trademark/special chars
    3. Lowercase
    4. Remove punctuation (keep alphanumeric, spaces)
    5. Normalize whitespace
    6. Normalize units
    7. Remove filler words
    8. Sort tokens for order-independence
    """
    if not title:
        return ""

    # Unicode normalize
    t = unicodedata.normalize("NFKD", title)

    # Replace special chars
    for old, new in CHAR_MAP.items():
        t = t.replace(old, new)

    # Lowercase
    t = t.lower()

    # Replace hyphens with spaces for comparison
    t = re.sub(r'[-_/\\]', ' ', t)

    # Keep only alphanumeric and spaces
    t = re.sub(r'[^a-z0-9\s]', ' ', t)

    # Normalize whitespace
    t = re.sub(r'\s+', ' ', t).strip()

    # Normalize units
    tokens = t.split()
    normalized_tokens = []
    for tok in tokens:
        if tok in UNIT_MAP:
            normalized_tokens.append(UNIT_MAP[tok])
        elif tok not in STRIP_WORDS:
            normalized_tokens.append(tok)

    # Deduplicate while preserving order
    seen = set()
    result = []
    for tok in normalized_tokens:
        if tok not in seen:
            seen.add(tok)
            result.append(tok)

    return " ".join(sorted(result))  # Sort for order-independence


def normalize_url(url: str) -> str:
    """Canonicalize a product URL by removing tracking parameters."""
    if not url:
        return ""

    url = url.strip()

    # Remove tracking parameters
    url = URL_TRACKING_PARAMS.sub('', url)

    # Clean up dangling ? or &
    url = URL_REMAINING_QMARK.sub('?', url)
    url = URL_REMAINING_AMP.sub('', url)

    # Remove fragment
    url = url.split('#')[0]

    # Ensure trailing slash consistency for paths (not query strings)
    if '?' not in url and not url.endswith('/'):
        url += '/'

    return url.lower()


def normalize_asin(asin: str) -> str:
    """Validate and normalize an ASIN."""
    if not asin:
        return ""
    asin = asin.strip().upper()
    if ASIN_PATTERN.match(asin):
        return asin
    return ""


def extract_asins_from_text(text: str) -> List[str]:
    """Extract valid ASINs from free text."""
    if not text:
        return []
    return ASIN_PATTERN.findall(text)


# ─── Fingerprinting ──────────────────────────────────────────


def compute_score_fingerprint(price: float, reviews: int, rating: float,
                               competition_data: dict = None,
                               trend_data: dict = None,
                               supplier_cost: float = None) -> str:
    """Compute a fingerprint for cache invalidation.
    If the fingerprint changes materially, the score should be recalculated."""
    parts = [
        f"p:{round(price, 2)}" if price else "p:none",
        f"r:{reviews}" if reviews else "r:none",
        f"rat:{round(rating, 1)}" if rating else "rat:none",
    ]
    if competition_data:
        parts.append(f"comp:{hashlib.md5(str(sorted(competition_data.items())).encode()).hexdigest()[:8]}")
    if trend_data:
        parts.append(f"trend:{hashlib.md5(str(sorted(trend_data.items())).encode()).hexdigest()[:8]}")
    if supplier_cost is not None:
        parts.append(f"sc:{round(supplier_cost, 2)}")

    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


# ─── Dataclass Models ────────────────────────────────────────


@dataclass
class ProductRecord:
    """Raw product record from a data source."""
    asin: str = ""
    name: str = ""
    brand: str = ""
    model_number: str = ""
    category: str = ""
    marketplace: str = "US"
    price: float = 0.0
    rating: float = 0.0
    review_count: int = 0
    product_url: str = ""
    image_url: str = ""
    canonical_url: str = ""
    upc: str = ""
    ean: str = ""
    gtin: str = ""
    parent_asin: str = ""
    variant_group: str = ""
    source_name: str = ""
    source_type: str = "marketplace"
    seller_info: dict = field(default_factory=dict)
    full_data: dict = field(default_factory=dict)
    normalized_title: str = ""
    marketplace_specific_id: str = ""

    def __post_init__(self):
        if not self.normalized_title and self.name:
            self.normalized_title = normalize_title(self.name)
        if not self.canonical_url and self.product_url:
            self.canonical_url = normalize_url(self.product_url)
        self.asin = normalize_asin(self.asin)


@dataclass
class MatchResult:
    """Result of a duplicate comparison."""
    is_duplicate: bool
    confidence: float
    match_type: str  # "exact", "asin", "fuzzy", "url", "none"
    matched_fields: List[str] = field(default_factory=list)


@dataclass
class MergeRecord:
    """Record of a product merge."""
    canonical_asin: str
    merged_asin: str
    reason: str
    confidence: float
    matched_fields: List[str]
    merged_by: str = "system"


# ─── Identity Resolution ─────────────────────────────────────


class ProductIdentityService:
    """Service for product identity resolution, dedup, and merge."""

    def __init__(self, db):
        """
        Args:
            db: UnifiedDB instance
        """
        self.db = db

    def resolve_product(self, record: ProductRecord) -> Optional[str]:
        """Resolve a raw product record to an existing canonical ASIN.

        Priority:
        1. ASIN match
        2. UPC/EAN/GTIN match
        3. Normalized URL match
        4. Fuzzy title + brand match

        Returns the canonical ASIN if matched, None if new product.
        """
        # Level 1: Direct ASIN match
        if record.asin:
            existing = self.db._exec(
                "SELECT asin FROM products WHERE asin = %s",
                (record.asin,), "one"
            )
            if existing:
                return existing["asin"]

        # Level 2: UPC/EAN/GTIN match
        for id_field in ("upc", "ean", "gtin"):
            val = getattr(record, id_field, "")
            if val:
                existing = self.db._exec(
                    f"SELECT asin FROM products WHERE {id_field} = %s AND {id_field} != ''",
                    (val,), "one"
                )
                if existing:
                    return existing["asin"]

        # Level 3: Canonical URL match
        if record.canonical_url:
            existing = self.db._exec(
                "SELECT asin FROM products WHERE canonical_url = %s AND canonical_url != ''",
                (record.canonical_url,), "one"
            )
            if existing:
                return existing["asin"]

        # Level 4: Fuzzy title + brand match (only if brand is available)
        if record.normalized_title and record.brand:
            candidates = self.db._exec(
                "SELECT asin, normalized_title, brand FROM products WHERE brand = %s AND normalized_title != '' LIMIT 50",
                (record.brand,), "all"
            ) or []

            for cand in candidates:
                result = self._compare_products(record, cand)
                if result.is_duplicate and result.confidence >= 0.95:
                    return cand["asin"]

        return None

    def _compare_products(self, record: ProductRecord, candidate: dict) -> MatchResult:
        """Compare two products for duplicate detection."""
        matched_fields = []
        confidence = 0.0

        # ASIN match (highest confidence)
        if record.asin and candidate.get("asin") and record.asin == candidate["asin"]:
            return MatchResult(True, 1.0, "asin", ["asin"])

        # Title match
        cand_title = candidate.get("normalized_title", "")
        if record.normalized_title and cand_title:
            if record.normalized_title == cand_title:
                matched_fields.append("normalized_title")
                confidence += 0.5
            else:
                title_sim = self._title_similarity(record.normalized_title, cand_title)
                if title_sim > 0.85:
                    matched_fields.append(f"title({title_sim:.2f})")
                    confidence += 0.4 * title_sim

        # Brand match
        if record.brand and candidate.get("brand"):
            if record.brand.lower() == candidate["brand"].lower():
                matched_fields.append("brand")
                confidence += 0.2

        # Model match
        if record.model_number and candidate.get("model_number"):
            if record.model_number.lower() == candidate["model_number"].lower():
                matched_fields.append("model")
                confidence += 0.2

        # Determine match type
        if confidence >= 0.95:
            match_type = "exact"
        elif confidence >= 0.7:
            match_type = "fuzzy"
        elif confidence >= 0.5:
            match_type = "possible"
        else:
            match_type = "none"

        return MatchResult(
            is_duplicate=confidence >= 0.85,
            confidence=min(confidence, 1.0),
            match_type=match_type,
            matched_fields=matched_fields
        )

    def _title_similarity(self, title_a: str, title_b: str) -> float:
        """Compute Jaccard similarity between normalized title tokens."""
        if not title_a or not title_b:
            return 0.0

        tokens_a = set(title_a.split())
        tokens_b = set(title_b.split())

        if not tokens_a or not tokens_b:
            return 0.0

        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b

        return len(intersection) / len(union) if union else 0.0

    def batch_deduplicate(self, records: List[ProductRecord]) -> Tuple[List[ProductRecord], List[dict]]:
        """Deduplicate a batch of raw product records.

        Returns:
            (unique_records, merge_logs)
        """
        canonical_map = {}  # normalized_title+brand -> canonical record
        unique_records = []
        merge_logs = []

        for record in records:
            # Try to resolve against existing DB products
            existing_asin = self.resolve_product(record)

            if existing_asin:
                # Update the existing product's latest observation
                self._update_product_observation(existing_asin, record)
                merge_logs.append(MergeRecord(
                    canonical_asin=existing_asin,
                    merged_asin=record.asin or f"TEMP_{record.normalized_title[:20]}",
                    reason="existing_product_match",
                    confidence=1.0,
                    matched_fields=["database_lookup"]
                ))
                continue

            # Try to resolve within this batch
            batch_key = f"{record.normalized_title}|{record.brand}".lower()
            if batch_key in canonical_map:
                # Duplicate within batch
                merge_logs.append(MergeRecord(
                    canonical_asin=canonical_map[batch_key].asin,
                    merged_asin=record.asin,
                    reason="batch_duplicate",
                    confidence=0.9,
                    matched_fields=["normalized_title", "brand"]
                ))
                continue

            # New unique product
            if record.asin:
                canonical_map[batch_key] = record
            unique_records.append(record)

        return unique_records, merge_logs

    def _update_product_observation(self, asin: str, record: ProductRecord):
        """Record a new market observation for an existing product."""
        try:
            self.db._exec(
                """INSERT INTO product_observations (asin, price, rating, review_count, source, marketplace, raw_data)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (asin, record.price or None, record.rating or None,
                 record.review_count or None, record.source_name or "",
                 record.marketplace or "US", json.dumps(record.full_data) if record.full_data else "{}")
            )
            # Update product's current fields and observation count
            self.db._exec(
                """UPDATE products SET
                    amazon_price = COALESCE(NULLIF(%s, 0), amazon_price),
                    rating = COALESCE(NULLIF(%s, 0), rating),
                    review_count = GREATEST(COALESCE(review_count, 0), COALESCE(NULLIF(%s, 0), 0)),
                    last_observed_at = CURRENT_TIMESTAMP,
                    observation_count = observation_count + 1,
                    source_count = (SELECT COUNT(DISTINCT source_name) FROM product_sources WHERE asin = %s) + 1,
                    updated_at = CURRENT_TIMESTAMP
                   WHERE asin = %s""",
                (record.price or 0, record.rating or 0,
                 record.review_count or 0, asin, asin)
            )
            # Record source provenance
            if record.source_name:
                self.db._exec(
                    """INSERT INTO product_sources (asin, source_name, source_type, raw_product_data)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT DO NOTHING""",
                    (asin, record.source_name, record.source_type or "marketplace",
                     json.dumps(record.full_data) if record.full_data else "{}")
                )
        except Exception as e:
            logger.error("Failed to update observation for %s: %s", asin, e)

    def merge_products(self, canonical_asin: str, duplicate_asin: str,
                       reason: str, confidence: float, matched_fields: List[str],
                       merged_by: str = "system") -> bool:
        """Merge a duplicate product into the canonical product.

        Preserves all observations, sources, and creates a merge log entry.
        """
        try:
            # Verify both exist
            canonical = self.db._exec("SELECT asin FROM products WHERE asin = %s", (canonical_asin,), "one")
            duplicate = self.db._exec("SELECT asin FROM products WHERE asin = %s", (duplicate_asin,), "one")

            if not canonical or not duplicate:
                return False

            # Move observations
            self.db._exec(
                "UPDATE product_observations SET asin = %s WHERE asin = %s",
                (canonical_asin, duplicate_asin)
            )

            # Move sources
            self.db._exec(
                "UPDATE product_sources SET asin = %s WHERE asin = %s",
                (canonical_asin, duplicate_asin)
            )

            # Move scoring history
            self.db._exec(
                "UPDATE scoring_history SET asin = %s WHERE asin = %s",
                (canonical_asin, duplicate_asin)
            )

            # Update canonical product with best data from duplicate
            self.db._exec(
                """UPDATE products SET
                    review_count = GREATEST(COALESCE(review_count, 0), (SELECT COALESCE(review_count, 0) FROM products WHERE asin = %s)),
                    source_count = (SELECT COUNT(DISTINCT source_name) FROM product_sources WHERE asin = %s) + 1,
                    observation_count = (SELECT COUNT(*) FROM product_observations WHERE asin = %s),
                    updated_at = CURRENT_TIMESTAMP
                   WHERE asin = %s""",
                (duplicate_asin, canonical_asin, canonical_asin, canonical_asin)
            )

            # Delete the duplicate product record
            self.db._exec("DELETE FROM products WHERE asin = %s", (duplicate_asin,))

            # Log the merge
            self.db._exec(
                """INSERT INTO product_merge_log (canonical_asin, merged_asin, merge_reason, confidence, matched_fields, merged_by)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (canonical_asin, duplicate_asin, reason, confidence,
                 json.dumps(matched_fields), merged_by)
            )

            return True
        except Exception as e:
            logger.error("Failed to merge %s into %s: %s", duplicate_asin, canonical_asin, e)
            return False

    def upsert_product(self, record: ProductRecord) -> str:
        """Upsert a product record, resolving identity first.

        Returns the canonical ASIN.
        """
        existing_asin = self.resolve_product(record)

        if existing_asin:
            # Update existing
            self.db._exec(
                """UPDATE products SET
                    amazon_price = COALESCE(NULLIF(%s, 0), amazon_price),
                    rating = COALESCE(NULLIF(%s, 0), rating),
                    review_count = GREATEST(COALESCE(review_count, 0), COALESCE(NULLIF(%s, 0), 0)),
                    category = COALESCE(NULLIF(%s, ''), category),
                    brand = COALESCE(NULLIF(%s, ''), brand),
                    model_number = COALESCE(NULLIF(%s, ''), model_number),
                    image_url = COALESCE(NULLIF(%s, ''), image_url),
                    product_url = COALESCE(NULLIF(%s, ''), product_url),
                    canonical_url = COALESCE(NULLIF(%s, ''), canonical_url),
                    last_observed_at = CURRENT_TIMESTAMP,
                    observation_count = observation_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                   WHERE asin = %s""",
                (record.price or 0, record.rating or 0, record.review_count or 0,
                 record.category or "", record.brand or "", record.model_number or "",
                 record.image_url or "", record.product_url or "", record.canonical_url or "",
                 existing_asin)
            )
            # Record observation
            self._update_product_observation(existing_asin, record)
            return existing_asin

        # Insert new product
        asin = record.asin or self._generate_temp_asin(record)
        try:
            self.db._exec(
                """INSERT INTO products (asin, name, normalized_title, category, brand, model_number,
                   marketplace, amazon_price, rating, review_count, product_url, canonical_url,
                   image_url, upc, ean, gtin, parent_asin, variant_group,
                   data_quality_score, last_observed_at, observation_count, source_count, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,CURRENT_TIMESTAMP,1,1,CURRENT_TIMESTAMP)
                   ON CONFLICT (asin) DO UPDATE SET
                    amazon_price = COALESCE(NULLIF(EXCLUDED.amazon_price, 0), products.amazon_price),
                    rating = COALESCE(NULLIF(EXCLUDED.rating, 0), products.rating),
                    review_count = GREATEST(COALESCE(products.review_count, 0), COALESCE(EXCLUDED.review_count, 0)),
                    updated_at = CURRENT_TIMESTAMP""",
                (asin, record.name, record.normalized_title, record.category,
                 record.brand, record.model_number, record.marketplace or "US",
                 record.price, record.rating, record.review_count,
                 record.product_url, record.canonical_url, record.image_url,
                 record.upc, record.ean, record.gtin, record.parent_asin, record.variant_group)
            )
            # Record observation
            self._update_product_observation(asin, record)
            # Record source
            if record.source_name:
                self.db._exec(
                    """INSERT INTO product_sources (asin, source_name, source_type, raw_product_data)
                       VALUES (%s, %s, %s, %s)""",
                    (asin, record.source_name, record.source_type or "marketplace",
                     json.dumps(record.full_data) if record.full_data else "{}")
                )
            return asin
        except Exception as e:
            logger.error("Failed to upsert product %s: %s", asin, e)
            return asin

    def _generate_temp_asin(self, record: ProductRecord) -> str:
        """Generate a temporary ASIN for products without one."""
        import string
        import random
        chars = string.ascii_uppercase + string.digits
        while True:
            temp = "B0" + "".join(random.choices(chars, k=8))
            existing = self.db._exec("SELECT asin FROM products WHERE asin = %s", (temp,), "one")
            if not existing:
                return temp

    def get_product_history(self, asin: str, limit: int = 100) -> List[dict]:
        """Get historical observations for a product."""
        return self.db._exec(
            """SELECT price, rating, review_count, bsr_rank, seller_count, in_stock,
                      source, marketplace, recorded_at
               FROM product_observations WHERE asin = %s
               ORDER BY recorded_at DESC LIMIT %s""",
            (asin, limit), "all"
        ) or []

    def get_product_sources(self, asin: str) -> List[dict]:
        """Get source provenance for a product."""
        return self.db._exec(
            """SELECT source_name, source_type, confidence, is_primary, collected_at
               FROM product_sources WHERE asin = %s ORDER BY collected_at DESC""",
            (asin,), "all"
        ) or []

    def get_merge_history(self, asin: str) -> List[dict]:
        """Get merge history for a product (as canonical or merged)."""
        return self.db._exec(
            """SELECT * FROM product_merge_log
               WHERE canonical_asin = %s OR merged_asin = %s
               ORDER BY created_at DESC""",
            (asin, asin), "all"
        ) or []

