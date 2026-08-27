"""Online Database Module - PostgreSQL adapter for cloud deployment."""

from .manager import OnlineDatabaseManager
from .config import DatabaseConfig

__all__ = ["OnlineDatabaseManager", "DatabaseConfig"]
