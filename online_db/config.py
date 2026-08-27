"""Database configuration for online/cloud deployment."""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DatabaseConfig:
    """PostgreSQL database configuration for cloud deployment."""

    # Connection
    host: str = os.environ.get("DB_HOST", "localhost")
    port: int = int(os.environ.get("DB_PORT", "5432"))
    database: str = os.environ.get("DB_NAME", "marketlens")
    user: str = os.environ.get("DB_USER", "marketlens")
    password: str = os.environ.get("DB_PASSWORD", "")

    # Connection pool
    min_connections: int = int(os.environ.get("DB_MIN_CONNECTIONS", "2"))
    max_connections: int = int(os.environ.get("DB_MAX_CONNECTIONS", "20"))
    connection_timeout: int = int(os.environ.get("DB_TIMEOUT", "30"))

    # SSL
    ssl_mode: str = os.environ.get("DB_SSL_MODE", "prefer")
    ssl_ca: Optional[str] = os.environ.get("DB_SSL_CA")
    ssl_cert: Optional[str] = os.environ.get("DB_SSL_CERT")
    ssl_key: Optional[str] = os.environ.get("DB_SSL_KEY")

    # Redis (for caching/sessions)
    redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    @property
    def dsn(self) -> str:
        """Build PostgreSQL DSN from components."""
        parts = [
            f"host={self.host}",
            f"port={self.port}",
            f"dbname={self.database}",
            f"user={self.user}",
        ]
        if self.password:
            parts.append(f"password={self.password}")
        return " ".join(parts)

    @property
    def async_dsn(self) -> str:
        """Build async PostgreSQL DSN (postgresql://)."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @property
    def sqlalchemy_url(self) -> str:
        """Build SQLAlchemy async URL."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @property
    def sqlalchemy_sync_url(self) -> str:
        """Build SQLAlchemy sync URL."""
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    def validate(self):
        """Validate configuration."""
        errors = []
        if not self.host:
            errors.append("DB_HOST is required")
        if not self.database:
            errors.append("DB_NAME is required")
        if not self.user:
            errors.append("DB_USER is required")
        if self.port < 1 or self.port > 65535:
            errors.append(f"DB_PORT must be 1-65535, got {self.port}")
        if errors:
            raise ValueError(f"Database config errors: {'; '.join(errors)}")

    @classmethod
    def from_url(cls, url: str) -> "DatabaseConfig":
        """Parse a PostgreSQL URL into config components.

        Format: postgresql://user:pass@host:port/dbname?sslmode=prefer
        """
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        return cls(
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            database=parsed.path.lstrip("/") or "marketlens",
            user=parsed.username or "",
            password=parsed.password or "",
            ssl_mode=params.get("sslmode", ["prefer"])[0],
        )
