"""Base classes for the Data Source Abstraction Layer.

Defines the standardized interface every data connector must implement,
along with normalized data models for products, trends, keywords, and suppliers.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class DataSourceStatus(Enum):
    """Connection status of a data source."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    PARTIAL = "partial"


class DataFreshness(Enum):
    """How fresh the data is."""
    LIVE = "live"              # Retrieved within last 5 minutes
    NEAR_REAL_TIME = "near_real_time"  # Retrieved within last hour
    CACHED = "cached"          # Retrieved within last 24 hours
    HISTORICAL = "historical"  # Older than 24 hours
    UNKNOWN = "unknown"


@dataclass
class SourceAttribution:
    """Tracks where data came from and how fresh it is."""
    source: str               # e.g., "Amazon", "Google Trends", "Alibaba"
    source_type: str          # e.g., "marketplace", "trend", "supplier"
    source_url: str = ""      # URL of the source page/API
    retrieved_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    marketplace: str = ""     # e.g., "US", "UK", "DE"
    confidence: str = "verified"  # verified, provider_estimate, calculated, ai_inference, unverified
    data_status: str = "live"     # live, cached, historical, estimated, unavailable

    def freshness(self) -> DataFreshness:
        """Calculate data freshness based on retrieval time."""
        if not self.retrieved_at:
            return DataFreshness.UNKNOWN
        age_seconds = (datetime.now() - self.retrieved_at).total_seconds()
        if age_seconds < 300:       # 5 minutes
            return DataFreshness.LIVE
        elif age_seconds < 3600:    # 1 hour
            return DataFreshness.NEAR_REAL_TIME
        elif age_seconds < 86400:   # 24 hours
            return DataFreshness.CACHED
        else:
            return DataFreshness.HISTORICAL

    def freshness_label(self) -> str:
        """Human-readable freshness label."""
        f = self.freshness()
        labels = {
            DataFreshness.LIVE: "Live",
            DataFreshness.NEAR_REAL_TIME: "Near Real-Time",
            DataFreshness.CACHED: "Cached",
            DataFreshness.HISTORICAL: "Historical",
            DataFreshness.UNKNOWN: "Unknown",
        }
        return labels.get(f, "Unknown")

    def age_text(self) -> str:
        """Human-readable age text."""
        if not self.retrieved_at:
            return "Unknown"
        age = (datetime.now() - self.retrieved_at).total_seconds()
        if age < 60:
            return f"{int(age)}s ago"
        elif age < 3600:
            return f"{int(age/60)}m ago"
        elif age < 86400:
            return f"{int(age/3600)}h ago"
        else:
            return f"{int(age/86400)}d ago"


@dataclass
class NormalizedProduct:
    """Standardized product record from any source."""
    asin: str = ""
    title: str = ""
    brand: str = ""
    category: str = ""
    subcategory: str = ""
    marketplace: str = "US"
    price: float = 0.0
    currency: str = "USD"
    rating: float = 0.0
    review_count: int = 0
    sales_rank: int = 0
    availability: str = "unknown"
    product_url: str = ""
    image_url: str = ""
    source: SourceAttribution = field(default_factory=SourceAttribution)
    seller_info: Dict[str, Any] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)
    specifications: Dict[str, Any] = field(default_factory=dict)
    variants: List[Dict[str, Any]] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "asin": self.asin,
            "title": self.title,
            "brand": self.brand,
            "category": self.category,
            "subcategory": self.subcategory,
            "marketplace": self.marketplace,
            "price": self.price,
            "currency": self.currency,
            "rating": self.rating,
            "review_count": self.review_count,
            "sales_rank": self.sales_rank,
            "availability": self.availability,
            "product_url": self.product_url,
            "image_url": self.image_url,
            "source": self.source.source,
            "source_type": self.source.source_type,
            "source_url": self.source.source_url,
            "retrieved_at": self.source.retrieved_at.isoformat() if self.source.retrieved_at else None,
            "marketplace_code": self.source.marketplace,
            "confidence": self.source.confidence,
            "data_status": self.source.data_status,
            "seller_info": self.seller_info,
            "attributes": self.attributes,
            "specifications": self.specifications,
        }


@dataclass
class NormalizedTrend:
    """Standardized trend record."""
    keyword: str = ""
    interest: float = 0.0
    trend_direction: str = "stable"  # rising, stable, falling
    period: str = ""
    related_queries: List[str] = field(default_factory=list)
    rising_queries: List[str] = field(default_factory=list)
    geographic_interest: Dict[str, float] = field(default_factory=dict)
    time_series: List[Dict[str, Any]] = field(default_factory=list)
    source: SourceAttribution = field(default_factory=SourceAttribution)


@dataclass
class NormalizedKeyword:
    """Standardized keyword record."""
    keyword: str = ""
    search_volume: Optional[int] = None
    competition: Optional[float] = None
    relevance: float = 0.0
    trend: str = "stable"
    related_keywords: List[str] = field(default_factory=list)
    long_tail_keywords: List[str] = field(default_factory=list)
    source: SourceAttribution = field(default_factory=SourceAttribution)
    data_type: str = "observed"  # observed, provider_estimate, ai_suggestion


@dataclass
class NormalizedSupplier:
    """Standardized supplier record."""
    supplier_id: str = ""
    supplier_name: str = ""
    company: str = ""
    product: str = ""
    supplier_price: float = 0.0
    moq: int = 0
    lead_time: str = ""
    rating: float = 0.0
    location: str = ""
    contact: Dict[str, str] = field(default_factory=dict)
    product_url: str = ""
    source: SourceAttribution = field(default_factory=SourceAttribution)


@dataclass
class DataSourceConfig:
    """Configuration for a data source."""
    source_id: str = ""
    source_name: str = ""
    enabled: bool = True
    api_key: str = ""
    api_secret: str = ""
    seller_id: str = ""
    marketplace: str = "US"
    rate_limit_per_minute: int = 60
    cache_ttl_seconds: int = 3600
    timeout_seconds: int = 30
    max_retries: int = 3
    extra_config: Dict[str, Any] = field(default_factory=dict)


class DataSource(ABC):
    """Abstract base class for all data source connectors.

    Every connector must implement at least one of:
    - search_products()
    - get_product()
    - get_trends()
    - get_keywords()
    - get_suppliers()
    """

    def __init__(self, config: DataSourceConfig):
        self.config = config
        self._status = DataSourceStatus.DISCONNECTED
        self._last_error: Optional[str] = None
        self._last_sync: Optional[datetime] = None
        self._request_count = 0
        self._error_count = 0
        self._rate_limit_reset: Optional[float] = None

    @property
    def source_id(self) -> str:
        return self.config.source_id

    @property
    def source_name(self) -> str:
        return self.config.source_name

    @property
    def status(self) -> DataSourceStatus:
        return self._status

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def last_sync(self) -> Optional[datetime]:
        return self._last_sync

    @abstractmethod
    def test_connection(self) -> bool:
        """Test if the source is accessible. Returns True if OK."""
        ...

    @abstractmethod
    def search_products(self, query: str, marketplace: str = "US",
                        max_results: int = 20) -> List[NormalizedProduct]:
        """Search for products. Returns empty list if source unavailable."""
        ...

    def get_product(self, asin: str, marketplace: str = "US") -> Optional[NormalizedProduct]:
        """Get a single product by ASIN. Default: not supported."""
        return None

    def get_trends(self, keywords: List[str], marketplace: str = "US") -> List[NormalizedTrend]:
        """Get trend data for keywords. Default: not supported."""
        return []

    def get_keywords(self, query: str, marketplace: str = "US") -> List[NormalizedKeyword]:
        """Get keyword data. Default: not supported."""
        return []

    def get_suppliers(self, product_name: str, category: str = "") -> List[NormalizedSupplier]:
        """Get supplier data. Default: not supported."""
        return []

    def get_health(self) -> Dict[str, Any]:
        """Get health/status information about this source."""
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "status": self._status.value,
            "last_error": self._last_error,
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "rate_limit_per_minute": self.config.rate_limit_per_minute,
        }

    def _record_request(self):
        """Record a successful request."""
        self._request_count += 1
        self._last_sync = datetime.now()

    def _record_error(self, error: str):
        """Record a failed request."""
        self._error_count += 1
        self._last_error = error
        self._status = DataSourceStatus.ERROR

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        now = time.time()
        if self._rate_limit_reset and now < self._rate_limit_reset:
            return False
        return True

    def _set_rate_limit(self, seconds: float):
        """Set rate limit cooldown."""
        self._rate_limit_reset = time.time() + seconds
        self._status = DataSourceStatus.RATE_LIMITED
