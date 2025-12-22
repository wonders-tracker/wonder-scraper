# Wonder Scraper - Project Documentation

## Project Overview

Wonder Scraper is a market tracking application for "Wonders of the First" trading card game. It scrapes eBay and Blokpax for listings and sales data, stores them in PostgreSQL, and presents them via a React frontend.

## Useful Scripts

### Market Reports

Generate weekly/daily market reports with ASCII bars and stats:

```bash
# Weekly report (both txt and md)
python scripts/generate_market_report.py --type weekly --format all

# Daily report as txt only
python scripts/generate_market_report.py --type daily --format txt

# Custom 14-day report as markdown
python scripts/generate_market_report.py --days 14 --format md

# Print to terminal while saving
python scripts/generate_market_report.py --type weekly --print
```

**Arguments:**
- `--type, -t` - `weekly` (7 days) or `daily` (1 day)
- `--format, -f` - `txt`, `md`, or `all` (both)
- `--days, -d` - Custom number of days (overrides --type)
- `--output, -o` - Custom output dir (default: `data/marketReports`)
- `--print, -p` - Also print to terminal

**Output location:** `data/marketReports/{date}-{type}.{txt|md}`

**Report includes:**
- Market summary with % change vs previous period
- Daily sales volume with ASCII bar charts
- Sales by product type breakdown
- Top 10 sellers by volume
- Price movers (gainers/losers)
- Hot deals (sold below floor)
- Market health stats

### Discord Market Insights

Automated 2x daily market insights are posted to Discord at 9:00 and 18:00 UTC. Uses the same format as the market report script.

To manually trigger:
```bash
python -c "
from app.services.market_insights import get_insights_generator
from app.discord_bot.logger import log_market_insights

gen = get_insights_generator()
data = gen.gather_market_data(days=1)
insights = gen.generate_insights(data)
log_market_insights(insights)
"
```

### Frontend Deployment

Use the deploy script for reliable Vercel deployments:

```bash
# Deploy to production
./scripts/deploy-frontend.sh

# Deploy to staging
./scripts/deploy-frontend.sh --staging

# Preview deployment
./scripts/deploy-frontend.sh --preview

# Validate build without deploying
./scripts/deploy-frontend.sh --dry-run

# Skip build (use existing dist)
./scripts/deploy-frontend.sh --skip-build
```

**What the script does:**
1. Cleans stale `.vercel/output` and `.vercel/builders` directories
2. Runs TypeScript type check
3. Builds the frontend with Vite
4. Validates bundle integrity (React chunks, syntax check)
5. Deploys to Vercel

**Important:** Never commit `.vercel/output` - it causes Vercel to skip builds and serve stale content. This is already in `.gitignore`.

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`) runs on push to main/staging/preview:

- **backend-test**: Runs pytest with PostgreSQL
- **backend-lint**: Runs ruff check/format and ty type check
- **frontend-test**: Runs typecheck, lint, and build
- **frontend-bundle-integrity**: Validates production bundle structure:
  - React vendor chunk exists and contains runtime
  - Router and main entry chunks exist
  - All JS files pass syntax validation
  - Reports bundle sizes
- **security-scan**: Trivy vulnerability scanner

## Key Directories

- `app/` - Backend FastAPI application
  - `api/` - API endpoints
  - `models/` - SQLModel database models
  - `scraper/` - eBay and Blokpax scrapers
  - `services/` - Business logic (market insights, etc.)
  - `discord_bot/` - Discord webhook integrations
  - `core/` - Scheduler, config, database
- `frontend/` - React + TanStack Router frontend
- `scripts/` - CLI utilities
- `data/marketReports/` - Generated market reports

## Environment Variables

Required:
- `DATABASE_URL` - PostgreSQL connection string
- `DISCORD_UPDATES_WEBHOOK_URL` - Discord webhook for market updates
- `DISCORD_NEW_LISTINGS_WEBHOOK_URL` - Discord webhook for new listings
- `OPENROUTER_API_KEY` - For AI-powered insights (optional)
