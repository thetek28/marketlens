"""Backend configuration for cloud deployment."""

import os
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class BackendConfig:
    """Cloud backend configuration."""

    # App
    app_name: str = "MarketLens Cloud"
    version: str = "3.0.0"
    debug: bool = os.environ.get("DEBUG", "false").lower() == "true"

    # Server
    host: str = os.environ.get("HOST", "0.0.0.0")
    port: int = int(os.environ.get("PORT", "8000"))
    workers: int = int(os.environ.get("WORKERS", "4"))

    # CORS
    cors_origins: List[str] = None

    # Auth
    jwt_secret: str = os.environ.get("MLENS_JWT_SECRET", "")
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # Database
    db_host: str = os.environ.get("DB_HOST", "localhost")
    db_port: int = int(os.environ.get("DB_PORT", "5432"))
    db_name: str = os.environ.get("DB_NAME", "marketlens")
    db_user: str = os.environ.get("DB_USER", "marketlens")
    db_password: str = os.environ.get("DB_PASSWORD", "")
    db_ssl_mode: str = os.environ.get("DB_SSL_MODE", "prefer")

    # Redis
    redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # Rate Limiting
    rate_limit_per_minute: int = int(os.environ.get("RATE_LIMIT", "60"))

    # AI
    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")

    def __post_init__(self):
        if self.cors_origins is None:
            self.cors_origins = [
                "http://localhost:3000",
                "http://localhost:8000",
                "http://127.0.0.1:8000",
                "https://*.vercel.app",
                "https://*.netlify.app",
                "https://*.railway.app",
                "https://*.onrender.com",
                "https://marketlens-backend-v72p.onrender.com",
            ]

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    def validate(self):
        errors = []
        if not self.jwt_secret:
            errors.append("MLENS_JWT_SECRET is required")
        if not self.db_host:
            errors.append("DB_HOST is required")
        if not self.db_name:
            errors.append("DB_NAME is required")
        if errors:
            raise ValueError(f"Config errors: {'; '.join(errors)}")
