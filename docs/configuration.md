# Configuration Reference

Complete reference for all environment variables and configuration options.

## Required Variables

### `DATABASE_URL`
PostgreSQL connection string.

```env
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

For Neon (serverless Postgres):
```env
DATABASE_URL=postgresql://user:password@ep-xxx.us-west-2.aws.neon.tech/dbname?sslmode=require
```

### `SECRET_KEY`
Secret key for JWT token signing. Generate with:
```bash
openssl rand -hex 32
```

## Optional Variables

### Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Token expiry (24 hours) |

### Discord Integration

| Variable | Description |
|----------|-------------|
| `DISCORD_UPDATES_WEBHOOK_URL` | Webhook for market updates |
| `DISCORD_NEW_LISTINGS_WEBHOOK_URL` | Webhook for new listing alerts |
| `DISCORD_BOT_TOKEN` | Bot token (if using bot features) |

### AI Features

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | OpenRouter API key for AI insights |
| `AI_MODEL` | Model to use (default: `anthropic/claude-3-haiku`) |

### Billing (Polar.sh)

| Variable | Description |
|----------|-------------|
| `POLAR_ACCESS_TOKEN` | Polar API access token |
| `POLAR_WEBHOOK_SECRET` | Webhook signature secret |
| `POLAR_ENVIRONMENT` | `sandbox` or `production` |

### Scraping

| Variable | Default | Description |
|----------|---------|-------------|
| `SCRAPE_INTERVAL_MINUTES` | `30` | Polling interval |
| `MAX_CONCURRENT_SCRAPES` | `3` | Parallel scrape workers |
| `EBAY_RATE_LIMIT_DELAY` | `2` | Seconds between requests |

### Browser Scraper

| Variable | Default | Description |
|----------|---------|-------------|
| `BROWSER_SEMAPHORE_LIMIT` | `2` | Concurrent browser tabs |
| `BROWSER_MAX_RESTARTS` | `3` | Restarts before extended cooldown |
| `BROWSER_MAX_TOTAL_RESTARTS` | `20` | Hard limit - fails after this many |
| `BROWSER_EXTENDED_COOLDOWN` | `10` | Seconds to wait after hitting restart limit |
| `BROWSER_MAX_PAGES_BEFORE_RESTART` | `25` | Restart browser after N pages (memory leak prevention) |

### Observability

| Variable | Default | Description |
|----------|---------|-------------|
| `SENTRY_DSN` | `""` | Sentry DSN (empty = disabled) |
| `SENTRY_ENVIRONMENT` | `production` | Environment tag for Sentry |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.1` | % of transactions traced (0.1 = 10%) |
| `TRACE_QUEUE_MAX_SIZE` | `50` | Max concurrent fire-and-forget trace writes |

### Database Pool

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_POOL_SIZE` | `20` | Max persistent connections |
| `DB_MAX_OVERFLOW` | `15` | Extra connections under load |

### Frontend (Vite)

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Backend API URL |
| `VITE_GOOGLE_ANALYTICS_ID` | GA4 measurement ID |

## Example `.env` File

```env
# Required
DATABASE_URL=postgresql://user:password@localhost:5432/wonder
SECRET_KEY=your-secret-key-here-generate-with-openssl

# Discord (optional)
DISCORD_UPDATES_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/yyy
DISCORD_NEW_LISTINGS_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/zzz

# AI Insights (optional)
OPENROUTER_API_KEY=sk-or-v1-xxx

# Billing (optional)
POLAR_ACCESS_TOKEN=pat_xxx
POLAR_WEBHOOK_SECRET=whsec_xxx
POLAR_ENVIRONMENT=sandbox

# Scraping
SCRAPE_INTERVAL_MINUTES=30
```

## Environment-Specific Config

### Development
```env
DEBUG=true
LOG_LEVEL=DEBUG
DATABASE_URL=postgresql://localhost/wonder_dev
```

### Staging
```env
DEBUG=false
LOG_LEVEL=INFO
DATABASE_URL=postgresql://xxx@staging-host/wonder_staging
```

### Production
```env
DEBUG=false
LOG_LEVEL=WARNING
DATABASE_URL=postgresql://xxx@production-host/wonder_prod
```

## Railway Configuration

Railway automatically sets:
- `PORT` - Server port
- `RAILWAY_ENVIRONMENT` - Current environment name

Configure in Railway dashboard:
1. Go to your service → Variables
2. Add each required variable
3. Use "Raw Editor" for bulk paste

## Vercel Configuration

For the frontend, set in Vercel dashboard:
1. Project Settings → Environment Variables
2. Add `VITE_API_URL` pointing to Railway backend
