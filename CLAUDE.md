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

## Development Workflow

### Environment Strategy

```
Feature Branch → Staging → Production
      ↓             ↓           ↓
  Local DB     Neon Staging   Neon Prod
```

| Environment | Backend | Frontend | Database |
|-------------|---------|----------|----------|
| **Local** | `localhost:8000` | `localhost:5173` | Docker PostgreSQL |
| **Staging** | `wonder-scraper-staging-staging.up.railway.app` | Vercel preview | Neon staging branch |
| **Production** | `api.wonderstracker.com` | `wonderstracker.com` | Neon main branch |

### Staging Environment

**Backend URL:** https://wonder-scraper-staging-staging.up.railway.app

**Health Checks:**
```bash
# Basic health
curl https://wonder-scraper-staging-staging.up.railway.app/health

# Detailed health (DB, scheduler, scraper status)
curl https://wonder-scraper-staging-staging.up.railway.app/health/detailed

# Circuit breaker status
curl https://wonder-scraper-staging-staging.up.railway.app/health/circuits
```

**Database:** Neon staging branch (copy of production data)

**Discord webhooks:** Disabled (to avoid polluting production channels)

### Feature Development Process

1. **Create feature branch** from `main`
   ```bash
   git checkout -b feature/my-feature main
   ```

2. **Develop locally** with Docker Compose
   ```bash
   docker-compose up -d postgres
   poetry run uvicorn app.main:app --reload
   cd frontend && npm run dev
   ```

3. **Push and create PR to staging**
   ```bash
   git push -u origin feature/my-feature
   gh pr create --base staging
   ```

4. **CI runs all checks** (tests, lint, type check, security scan)

5. **Merge to staging** → Auto-deploys to staging environment
   - Backend: Railway staging service
   - Frontend: Vercel staging preview
   - Database: Neon staging branch

6. **Test on staging** → Verify feature works end-to-end
   ```bash
   curl https://wonder-scraper-staging-staging.up.railway.app/health/detailed
   ```

7. **Create PR from staging to main**
   ```bash
   gh pr create --base main --head staging --title "Release: feature description"
   ```

8. **Merge to main** → Auto-deploys to production

### Quick Commands

```bash
# Create feature branch
git checkout -b feature/my-feature main

# Create PR to staging
gh pr create --base staging

# Create release PR (staging → main)
gh pr create --base main --head staging

# Check staging health
curl -s https://wonder-scraper-staging-staging.up.railway.app/health/detailed | python -m json.tool

# Check production health
curl -s https://api.wonderstracker.com/health/detailed | python -m json.tool
```

### Database Migrations

**Safe migration workflow:**
1. Write migration with `alembic revision --autogenerate -m "description"`
2. Test locally: `poetry run alembic upgrade head`
3. Push to feature branch → CI tests migration on fresh DB
4. Merge to staging → Migration runs on Neon staging branch
5. Verify staging works correctly
6. Merge to main → Migration runs on Neon production

**CI checks for dangerous operations:**
- DROP TABLE/COLUMN detection
- Column type changes
- NOT NULL without defaults

## CI/CD Pipeline

GitHub Actions workflow (`.github/workflows/ci.yml`) runs on push to main/staging/preview.

### CI Jobs

| Job | Trigger | Duration | Description |
|-----|---------|----------|-------------|
| **backend-test** | All branches | ~3m | Pytest with PostgreSQL service container |
| **backend-lint** | All branches | ~30s | Ruff check/format + ty type check (cached) |
| **frontend-test** | All branches | ~45s | TypeScript, ESLint, Vite build |
| **frontend-bundle-integrity** | All branches | ~8s | Validates React chunks, syntax check (reuses build artifact) |
| **security-scan** | All branches | ~15s | Trivy vulnerability scanner |
| **migration-check** | PRs only | ~5s | Detects DROP/ALTER operations |
| **staging-smoke-test** | staging push | ~10s | Health checks + auth validation |
| **production-auth-check** | PRs to main | ~5s | Validates production auth config |

### Running CI Locally

```bash
# Run all checks locally
./scripts/ci-local.sh

# Backend only
./scripts/ci-local.sh backend

# Frontend only
./scripts/ci-local.sh frontend

# Quick lint check
./scripts/ci-local.sh quick
```

### CI Optimizations

- **Dependency caching**: Backend lint uses cached virtualenv
- **Build artifact reuse**: Frontend bundle integrity reuses build from frontend-test
- **Polling over sleep**: Staging smoke test polls for deployment (vs fixed 90s wait)
- **Fail-fast tests**: Backend tests use `-x` flag for faster failure feedback

## Deployment

### Production Deployment

```bash
# 1. Create release PR
gh pr create --base main --head staging --title "Release: description"

# 2. Merge (auto-deploys to Railway + Vercel)
gh pr merge <PR_NUMBER> --merge

# 3. Verify
curl https://wonder-scraper-production.up.railway.app/health
```

### Staging Deployment

```bash
# Merge feature to staging (auto-deploys)
gh pr merge <PR_NUMBER> --merge

# Verify
curl https://wonder-scraper-staging-staging.up.railway.app/health
```

### Railway CLI Commands

```bash
# Switch environments
railway environment production
railway environment staging

# Check variables
railway variables

# Update variable
railway variables --set "KEY=value"

# Redeploy
railway redeploy -y

# View logs
railway logs
```

### Rollback

**Railway (code):**
1. Go to Railway Dashboard → Service → Deployments
2. Find previous working deployment
3. Click **Rollback**

**Or via CLI:**
```bash
railway rollback
```

**Neon (database):**
```bash
# Point-in-time recovery
neonctl branches restore staging --timestamp "2024-01-01T00:00:00Z"

# Reset staging to production
neonctl branches delete staging
neonctl branches create --name staging --parent main
```

## OAuth Configuration

### Discord OAuth Setup

**CRITICAL:** When changing `DISCORD_REDIRECT_URI`, update Discord Developer Portal FIRST.

**Production redirect URI:**
```
https://wonderstracker.com/api/v1/auth/discord/callback
```

**Staging redirect URI:**
```
https://wonder-scraper-staging-staging.up.railway.app/api/v1/auth/discord/callback
```

**To update:**
1. Go to https://discord.com/developers/applications
2. Select app → OAuth2 → Redirects
3. Add/update redirect URI
4. Save
5. THEN update Railway environment variable

### Auth Flow

```
User → Frontend → Discord OAuth → Backend Callback → Set Cookies → Redirect to Frontend
```

Cookies must be set on the same domain as the frontend for auth to work:
- Production: `wonderstracker.com` (via Vercel proxy)
- Staging: Direct Railway URL (no separate frontend)

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
