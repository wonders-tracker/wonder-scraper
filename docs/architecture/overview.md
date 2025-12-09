# Architecture Overview

High-level architecture of the WondersTracker platform.

## System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENTS                                  │
├─────────────────────────────────────────────────────────────────┤
│  Web Browser ──────┐                                            │
│  Mobile Browser ───┼──► wonderstracker.com (Vercel/Railway)     │
│  Discord Bot ──────┘                                            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FRONTEND (React)                            │
├─────────────────────────────────────────────────────────────────┤
│  TanStack Router ──► Routes                                     │
│  TanStack Query ───► API Cache & State                          │
│  Tailwind CSS ─────► Styling                                    │
│  Recharts ─────────► Data Visualization                         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ REST API
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  BACKEND API (FastAPI)                           │
├─────────────────────────────────────────────────────────────────┤
│  /api/v1/cards ────► Card CRUD & Search                         │
│  /api/v1/market ───► Market Data & Analytics                    │
│  /api/v1/auth ─────► Authentication (JWT)                       │
│  /api/v1/portfolio ► Portfolio Management                       │
│  /api/v1/billing ──► Subscription Management                    │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   DATABASE    │    │  SCHEDULER       │    │  EXTERNAL       │
│   (Neon PG)   │    │  (APScheduler)   │    │  SERVICES       │
├───────────────┤    ├──────────────────┤    ├─────────────────┤
│ Cards         │    │ Polling Job      │    │ eBay Scraper    │
│ MarketPrice   │    │ (30 min)         │    │ Blokpax API     │
│ Users         │    │                  │    │ Discord Webhook │
│ Portfolios    │    │ Insights Job     │    │ Polar.sh        │
│ Snapshots     │    │ (2x daily)       │    │ OpenRouter AI   │
└───────────────┘    └──────────────────┘    └─────────────────┘
```

## Component Details

### Frontend

**Tech Stack**: React 19 + TanStack Router + TanStack Query + Tailwind

- **Server-Side Rendering**: TanStack Start for SEO
- **Routing**: File-based with type safety
- **Data Fetching**: React Query with 5-minute cache
- **State**: Query cache + React context (auth)

### Backend API

**Tech Stack**: FastAPI + SQLModel + Pydantic

**Key Modules**:
| Module | Purpose |
|--------|---------|
| `app/api/` | REST endpoints |
| `app/core/` | Config, security, middleware |
| `app/models/` | Database models (SQLModel) |
| `app/services/` | Business logic |
| `app/scraper/` | Data collection |

### Database

**Tech Stack**: PostgreSQL 15 (Neon serverless)

**Key Tables**:
- `card` - Card metadata (name, rarity, set)
- `marketprice` - Individual sales/listings
- `marketsnapshot` - Daily aggregated stats
- `user` - User accounts
- `portfolio` / `portfoliocard` - User collections

### Scheduler

**Tech Stack**: APScheduler (in-process)

**Jobs**:
| Job | Interval | Purpose |
|-----|----------|---------|
| `polling_job` | 30 min | Scrape eBay listings |
| `insights_job` | 12 hours | Generate AI reports |
| `cleanup_job` | 24 hours | Remove stale data |

### Scrapers

**eBay Scraper** (`app/scraper/ebay.py`):
- Uses Playwright for browser automation
- Extracts sold listings and active inventory
- Rate-limited to avoid blocks

**Blokpax Scraper** (`app/scraper/blokpax.py`):
- REST API integration
- Pulls digital marketplace data

## Data Flow

### Price Collection Flow

```
1. Scheduler triggers polling job
2. For each card in tracking list:
   a. Query eBay for recent sales
   b. Parse listing details (price, date, treatment)
   c. Deduplicate against existing data
   d. Insert new MarketPrice records
   e. Update MarketSnapshot aggregates
3. Notify Discord of significant changes
```

### User Request Flow

```
1. User visits /cards/42
2. Frontend queries GET /api/v1/cards/42
3. Backend fetches card + joins pricing data
4. Response includes FMP, floor, history
5. Frontend renders with React Query cache
```

## Security

### Authentication
- JWT tokens with 24-hour expiry
- Argon2 password hashing
- Discord OAuth integration

### Authorization
- Role-based: user, pro, admin
- Endpoint-level permission checks
- Rate limiting per IP/user

### Data Protection
- HTTPS everywhere
- SQL injection prevention (SQLModel)
- XSS protection (React default escaping)
- CORS restricted to allowed origins

## Deployment

### Railway (Backend)
- Auto-deploy on push to `main`
- Environment variables in dashboard
- Health check at `/health`

### Vercel (Frontend)
- Auto-deploy on push
- Preview deployments for PRs
- Edge caching for static assets

### Database (Neon)
- Serverless auto-scaling
- Connection pooling enabled
- Point-in-time recovery
