# WondersTracker

Real-time market tracker for Wonders of the First TCG cards.

## Architecture

### Frontend (Vercel)
- **Tech**: React + TanStack Router + TanStack Query + Tailwind CSS
- **URL**: https://wonderstracker.com
- **Features**:
  - Real-time card price tracking
  - Market analysis & trends
  - Portfolio management
  - SEO optimized with dynamic OG images

### Backend (Railway)
- **Tech**: FastAPI + SQLModel + PostgreSQL (Neon)
- **URL**: https://wonder-scraper-production.up.railway.app
- **Purpose**: 
  - REST API for card and market data
  - Scheduled jobs for scraping (every 30 minutes)
  - Background data processing

### Database (Neon)
- **Tech**: PostgreSQL with connection pooling
- **Purpose**: Central data store accessed by both backend jobs and frontend API calls

## Data Flow

```
eBay/OpenSea → Backend Scrapers → Neon DB ← Frontend (via REST API)
                     ↑
                Scheduled Jobs (30min intervals)
```

## Development

### Backend
```bash
cd /path/to/wonder-scraper
poetry install
poetry run uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Distributed Backfill
```bash
# Run with 4 parallel workers
python scripts/distributed_backfill.py 4

# Force update all cards
python scripts/distributed_backfill.py 4 --force
```

## Environment Variables

### Backend (Railway)
- `DATABASE_URL`: Neon PostgreSQL connection string
- `SECRET_KEY`: JWT secret
- `PORT`: Auto-set by Railway

### Frontend (Vercel)
- `VITE_API_URL`: Backend API URL (Railway)

## Deployment

### Frontend
```bash
vercel --prod
```

### Backend
```bash
railway up
```

## Key Features

- ✅ SEO optimized with meta tags and OG images
- ✅ 5-minute API response caching for instant page loads
- ✅ Distributed backfill with multiprocessing
- ✅ Optimized polling system (30min intervals, batch processing)
- ✅ User authentication (signup/login)
- ✅ Product type tracking (Singles, Boxes, Packs, Proofs)
- ✅ Multi-platform scraping (eBay, OpenSea)
- ✅ ETH to USD conversion for OpenSea data

