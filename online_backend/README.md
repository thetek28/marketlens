# online_backend — Cloud FastAPI Backend

Cloud-ready FastAPI backend for MarketLens using PostgreSQL. Designed for Docker deployment with connection pooling and Redis caching.

## Quick Start

```bash
# Copy environment template
cp .env.example .env
# Edit .env with your credentials

# Start with Docker Compose
docker-compose up -d
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | localhost | PostgreSQL host |
| `DB_PORT` | 5432 | PostgreSQL port |
| `DB_NAME` | marketlens | Database name |
| `DB_USER` | marketlens | Database user |
| `DB_PASSWORD` | (required) | Database password |
| `REDIS_URL` | redis://localhost:6379/0 | Redis URL |
| `MLENS_JWT_SECRET` | (required) | JWT signing secret |
| `PORT` | 8000 | Server port |
| `WORKERS` | 4 | Uvicorn workers |
| `DEBUG` | false | Debug mode |

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Module exports |
| `app.py` | FastAPI application with all endpoints |
| `config.py` | BackendConfig dataclass |
| `Dockerfile` | Python 3.12 slim container |
| `docker-compose.yml` | Full stack: PostgreSQL + Redis + Backend |
| `requirements.txt` | FastAPI + auth dependencies |
| `.env.example` | Environment variable template |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login |
| GET | `/api/auth/me` | Get current user |
| GET | `/api/products/all` | List all products |
| GET | `/api/products/top20` | Top 20 products |
| GET | `/api/products/{asin}` | Get product by ASIN |
| GET | `/api/suppliers` | List suppliers |
| POST | `/api/suppliers` | Add supplier |
| DELETE | `/api/suppliers/{id}` | Delete supplier |
| GET | `/api/listing/{asin}` | Get listing data |
| POST | `/api/listing/{asin}/save` | Save listing version |
| GET | `/api/listing/{asin}/versions` | Get listing versions |
| GET | `/api/database/stats` | Database statistics |
| GET | `/api/price-history/{asin}` | Price history |
| POST | `/api/price-history/{asin}/record` | Record price |
| GET | `/api/inventory/{asin}` | Get inventory |
| POST | `/api/inventory/{asin}` | Save inventory |
| GET | `/api/notes/{asin}` | Get notes |
| POST | `/api/notes/{asin}` | Save note |
| GET | `/api/team/tasks/{asin}` | Get tasks |
| POST | `/api/team/tasks/{asin}` | Add task |
| GET | `/api/config` | Get config |
| GET | `/api/backend/info` | Backend info |

## Deployment

### Docker (Recommended)

```bash
docker-compose up -d
```

### Manual

```bash
pip install -r requirements.txt
python -m online_backend.app
```

### Cloud Platforms

- **Railway**: Connect PostgreSQL addon, set env vars
- **Render**: Create PostgreSQL service, deploy backend
- **Fly.io**: Use `fly launch` with `fly secrets set`
- **AWS ECS**: Use RDS for PostgreSQL, ECS for backend
- **Google Cloud Run**: Use Cloud SQL, deploy as service
