# WondersTracker

[![CI](https://github.com/wonders-tracker/wonder-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/wonders-tracker/wonder-scraper/actions/workflows/ci.yml)
[![License: O'Saasy](https://img.shields.io/badge/License-O'Saasy-blue.svg)](LICENSE.md)

Real-time market tracking and price analytics platform for the **Wonders of the First** trading card game. Aggregates sales data from eBay and Blokpax to provide pricing, market trends, and portfolio management.

**Live Site**: [wonderstracker.com](https://wonderstracker.com)

## Features

- **Real-time Market Data** - Hourly polling of eBay sales and listings
- **Fair Market Price (FMP)** - MAD-trimmed pricing algorithm for accurate valuations
- **Portfolio Tracking** - Track your collection's value over time
- **Market Insights** - AI-generated daily market reports
- **Treatment Variants** - Track Classic Paper, Foil, Serialized, and more
- **Discord Integration** - Market alerts and new listing notifications

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 19, TanStack Router/Query, Tailwind CSS |
| **Backend** | FastAPI, SQLModel, APScheduler |
| **Database** | PostgreSQL (Neon) |
| **Scraping** | Playwright, BeautifulSoup |
| **Hosting** | Railway (API), Vercel (Frontend) |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 15+ (or [Neon](https://neon.tech) account)
- [Poetry](https://python-poetry.org/) package manager

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/wonders-tracker/wonder-scraper.git
cd wonder-scraper

# Install dependencies
poetry install

# Copy environment template
cp .env.example .env
# Edit .env with DATABASE_URL and SECRET_KEY

# Start the development server
poetry run uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:5173 (frontend) and http://localhost:8000/docs (API docs).

## Project Structure

```
wonder-scraper/
├── app/                    # Backend application
│   ├── api/               # API endpoints (cards, market, auth, etc.)
│   ├── core/              # Config, security, scheduler
│   ├── models/            # SQLModel database models
│   ├── scraper/           # eBay & Blokpax scrapers
│   ├── services/          # Business logic (pricing, insights)
│   └── discord_bot/       # Discord webhook integrations
├── frontend/              # React frontend
│   ├── app/
│   │   ├── components/    # Reusable UI components
│   │   ├── routes/        # TanStack Router pages
│   │   └── lib/           # Utilities & API client
├── scripts/               # CLI utilities
├── tests/                 # Test suite
└── docs/                  # Documentation
```

## Development

### Running Tests

```bash
# All tests
poetry run pytest

# With coverage
poetry run pytest --cov=app --cov-report=html

# Specific file
poetry run pytest tests/test_pricing.py -v
```

### Code Quality

```bash
# Backend lint
poetry run ruff check app/

# Frontend typecheck
cd frontend && npm run typecheck
```

## Branch Strategy

| Branch | Purpose | Auto-Deploys To |
|--------|---------|-----------------|
| `main` | Production code | Production (Railway) |
| `staging` | Pre-release testing | Staging environment |
| `preview` | Feature previews | Preview environment |

**Workflow**: `feature-branch` → PR → `staging` → PR → `main`

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SECRET_KEY` | Yes | JWT signing key |
| `DISCORD_UPDATES_WEBHOOK_URL` | No | Discord market updates |
| `OPENROUTER_API_KEY` | No | AI insights generation |
| `POLAR_ACCESS_TOKEN` | No | Billing integration |

See [docs/configuration.md](docs/configuration.md) for complete reference.

## API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Production API**: https://wonder-scraper-production.up.railway.app/docs

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

**O'Saasy License** - Source available with SaaS restriction.

You're free to use, modify, and deploy this software for personal or internal use. However, you may not offer it as a competing SaaS product.

See [LICENSE.md](LICENSE.md) for full terms.

## Links

- [Live Site](https://wonderstracker.com)
- [API Docs](https://wonder-scraper-production.up.railway.app/docs)
- [Wonders of the First](https://wondersofthefirst.com/)
