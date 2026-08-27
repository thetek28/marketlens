# MarketLens - AI-Powered Amazon Product Research

Commercial-grade desktop application for Amazon product research, analysis, and supplier sourcing.

## Features

- **Multi-Source Data Collection**: Amazon Best Sellers, eBay, Walmart, Alibaba pricing
- **AI Product Scoring**: OpenAI/Claude integration with rule-based fallback
- **Seller Intelligence**: 24 fields per product (seller name, rating, fulfillment, brand, BSR, sales estimates)
- **Supplier Database**: 12 pre-built suppliers across 12 categories with full contact info
- **Profitability Calculator**: FBA fees, landed cost, margin analysis
- **Advanced Analytics**: Category rankings, market gaps, price sweet spots
- **Export Engine**: Excel (4 sheets) and PDF (3 sections) reports
- **Real-Time Collection**: Infinite cycle mode with configurable intervals

## Requirements

- Python 3.10+
- Windows 10/11

## Installation

### From Source
```bash
pip install -r requirements.txt
python run_gui.py
```

### From Installer
Run `MarketLens-Setup.exe` and follow the installation wizard.

## Usage

1. Launch MarketLens from desktop shortcut or Start Menu
2. Click **Start Analysis** to begin product research
3. Review products in the **Products** tab
4. Check supplier matches in the **Suppliers** tab
5. Use **Tools** tab for Compare, Analytics, Batch ASIN lookup
6. Export reports via **Export** button

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+S | Save products |
| Ctrl+E | Export report |
| Ctrl+R / F5 | Start analysis |
| Escape | Stop analysis |

## Building

```bash
py -m PyInstaller MarketLens.spec
```

## Cloud Deployment

MarketLens supports both local SQLite and cloud PostgreSQL backends.

### Quick Start (Docker)

```bash
# 1. Configure environment
cp online_backend/.env.example .env
# Edit .env with your DB credentials and JWT secret

# 2. Start all services
docker-compose -f online_backend/docker-compose.yml up -d

# 3. Access at http://localhost:8000
```

### Backend Options

| Backend | Use Case | Setup |
|---------|----------|-------|
| SQLite (default) | Local development | No config needed |
| PostgreSQL | Cloud/multi-user | Set `MLENS_DB_BACKEND=postgresql` |

### Cloud Platforms

- **Railway**: PostgreSQL addon + backend service
- **Render**: PostgreSQL + web service
- **Fly.io**: Postgres cluster + app
- **AWS**: RDS + ECS/EKS
- **Google Cloud**: Cloud SQL + Cloud Run
- **Azure**: Azure Database for PostgreSQL + Container Apps

See `online_db/README.md` and `online_backend/README.md` for detailed configuration.

## License

Proprietary - MarketLens 2026
