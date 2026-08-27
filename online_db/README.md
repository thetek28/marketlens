# online_db — PostgreSQL Database Module

PostgreSQL adapter for MarketLens cloud deployment. Provides the same `DatabaseManager` interface as the SQLite version.

## Quick Start

```bash
pip install -r requirements.txt
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | localhost | PostgreSQL host |
| `DB_PORT` | 5432 | PostgreSQL port |
| `DB_NAME` | marketlens | Database name |
| `DB_USER` | marketlens | Database user |
| `DB_PASSWORD` | (required) | Database password |
| `DB_SSL_MODE` | prefer | SSL mode: disable, allow, prefer, require |
| `DB_POOL_MIN` | 2 | Min pool connections |
| `DB_POOL_MAX` | 10 | Max pool connections |
| `DB_POOL_TIMEOUT` | 30 | Connection timeout (seconds) |
| `DB_POOL_RETRIES` | 3 | Retry attempts |

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Module exports |
| `config.py` | DatabaseConfig dataclass, DSN builders, validation |
| `manager.py` | OnlineDatabaseManager — full PostgreSQL implementation |
| `migrations/001_init.sql` | Schema: 14 tables + 21 indexes |
| `requirements.txt` | psycopg2-binary |

## Usage

```python
from online_db import OnlineDatabaseManager, DatabaseConfig

config = DatabaseConfig()
db = OnlineDatabaseManager(config)

# Same API as SQLite DatabaseManager
products = db.get_all_products_from_db()
stats = db.get_stats()
```

## Schema (14 Tables)

- `users`, `products`, `product_ideas`, `hidden_gems`
- `suppliers`, `products_suppliers`
- `listing_versions`, `keywords`
- `price_history`, `inventory`, `comments`, `tasks`
- `subscriptions`

Indexes on: ASIN, user_id, category, tier, created_at, version_id, and more.

## Deployment

Use with `online_backend/docker-compose.yml` for full stack (PostgreSQL + Redis + FastAPI).
