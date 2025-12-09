# Database Setup for Contributors

This guide explains how to set up a local development database.

## Quick Start (Docker)

The easiest way to run a local database is with Docker:

```bash
# Start PostgreSQL
docker-compose up -d postgres

# Verify it's running
docker-compose ps

# Your DATABASE_URL is:
# postgresql://wonder:wonder@localhost:5432/wonder_dev
```

## Manual PostgreSQL Setup

If you prefer not to use Docker:

### macOS (Homebrew)
```bash
brew install postgresql@15
brew services start postgresql@15

# Create database
createdb wonder_dev
```

### Ubuntu/Debian
```bash
sudo apt install postgresql-15
sudo systemctl start postgresql

# Create database
sudo -u postgres createdb wonder_dev
```

## Environment Configuration

Add to your `.env` file:

```env
# Docker setup
DATABASE_URL=postgresql://wonder:wonder@localhost:5432/wonder_dev

# Or manual setup (adjust as needed)
DATABASE_URL=postgresql://localhost/wonder_dev
```

## Running Migrations

### Apply all migrations
```bash
poetry run alembic upgrade head
```

### Create a new migration
```bash
# Auto-generate from model changes
poetry run alembic revision --autogenerate -m "Add new_column to cards"

# Or create empty migration
poetry run alembic revision -m "Custom migration"
```

### Rollback migration
```bash
# Rollback one step
poetry run alembic downgrade -1

# Rollback to specific revision
poetry run alembic downgrade abc123

# Rollback all
poetry run alembic downgrade base
```

### View migration status
```bash
# Show current revision
poetry run alembic current

# Show migration history
poetry run alembic history --verbose
```

## Seeding Data

### Option 1: Sync from production (recommended)

Contact a maintainer for a sanitized database dump, or use the scraper to populate fresh data:

```bash
# Run initial card scrape
poetry run python -c "from app.scraper.ebay import run_full_scrape; run_full_scrape()"
```

### Option 2: Create test data

```python
# scripts/seed_dev_data.py
from app.core.database import get_session
from app.models import Card, Rarity

with get_session() as session:
    # Create rarity
    rarity = Rarity(name="Common")
    session.add(rarity)
    session.commit()

    # Create card
    card = Card(
        name="Test Card",
        set_name="Test Set",
        rarity_id=rarity.id
    )
    session.add(card)
    session.commit()
```

## Testing with Database

Tests use a separate test database. The CI creates one automatically.

For local testing:

```bash
# Create test database
createdb wonder_test

# Set test DATABASE_URL (or use docker)
export DATABASE_URL=postgresql://localhost/wonder_test

# Run tests
poetry run pytest
```

## Common Issues

### "Connection refused"
- Ensure PostgreSQL is running: `docker-compose ps` or `brew services list`
- Check port 5432 is available: `lsof -i :5432`

### "Database does not exist"
- Run: `docker-compose exec postgres createdb -U wonder wonder_dev`
- Or: `createdb wonder_dev`

### "Migration failed"
- Check DATABASE_URL is set correctly
- Ensure you're in the project root directory
- Try: `poetry run alembic downgrade base && poetry run alembic upgrade head`

### "Models not found in autogenerate"
- Ensure model is imported in `alembic/env.py`
- Check model inherits from `SQLModel` with `table=True`

## Connecting to Production Database

**Warning**: Only for debugging. Never modify production data directly.

```bash
# Get connection string from Railway dashboard
# Settings > Variables > DATABASE_URL

# Connect with psql
psql "postgresql://xxx@production-host/dbname?sslmode=require"
```

## Database Schema Overview

```
card              - Card metadata (name, set, rarity)
├── rarity_id     → rarity (rarity name/tier)

marketprice       - Individual sales/listings
├── card_id       → card
└── listing_type  - 'sold' or 'active'

marketsnapshot    - Daily aggregated stats
└── card_id       → card

user              - User accounts
├── portfolio items
└── watchlist items

portfolioitem     - User's portfolio entries
├── user_id       → user
└── card_id       → card
```

## Maintenance Commands

```bash
# Vacuum database (reclaim space)
docker-compose exec postgres vacuumdb -U wonder -d wonder_dev

# Analyze for query optimization
docker-compose exec postgres psql -U wonder -d wonder_dev -c "ANALYZE;"

# Backup database
docker-compose exec postgres pg_dump -U wonder wonder_dev > backup.sql

# Restore database
cat backup.sql | docker-compose exec -T postgres psql -U wonder wonder_dev
```
