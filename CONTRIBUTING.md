# Contributing to WondersTracker

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful, inclusive, and constructive. We're all here to build something great together.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/wonder-scraper.git
   cd wonder-scraper
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/wonders-tracker/wonder-scraper.git
   ```
4. **Set up development environment** (see below)

## Development Environment Setup

### Prerequisites

- Python 3.11+
- Poetry (Python package manager)
- Node.js 20+
- Docker (for local PostgreSQL)

### Quick Start

```bash
# 1. Start local PostgreSQL
docker-compose up -d postgres

# 2. Install dependencies
poetry install
cd frontend && npm install && cd ..

# 3. Configure environment
cp .env.example .env
# Edit .env if needed - defaults work with docker-compose

# 4. Run database migrations
poetry run alembic upgrade head

# 5. (Optional) Import sample data - see "Working with Data" below

# 6. Start the backend
poetry run uvicorn app.main:app --reload

# 7. Start the frontend (separate terminal)
cd frontend && npm run dev
```

## Working with Data

### Option A: Empty Database (Minimal)

For most contributions, an empty database with just the schema is fine:

```bash
poetry run alembic upgrade head
```

### Option B: Sample Data (Recommended)

For a realistic development experience, import the contributor data dump:

1. **Request access** to the [wonders-tracker/wonder-data](https://github.com/wonders-tracker/wonder-data) private repo
   - Join the `contributors` team on the wonders-tracker org
   - This repo contains sanitized market data (no user PII)

2. **Clone the data repo**:
   ```bash
   git clone https://github.com/wonders-tracker/wonder-data.git ../wonder-data
   ```

3. **Import the data**:
   ```bash
   python scripts/import_contributor_data.py ../wonder-data/exports/latest.sql.gz
   ```

### What's in the Data Dump?

The contributor data includes **public market data only**:

| Included (Safe) | Excluded (Sensitive) |
|-----------------|----------------------|
| Cards & Rarities | Users & Passwords |
| Market Prices | Portfolios |
| Market Snapshots | API Keys |
| Blokpax Data | Page Views |
| Listing Reports | Watchlists |

### Creating Test Data

For unit tests, use the test fixtures in `tests/conftest.py`:

```python
def test_my_feature(sample_cards, sample_market_prices):
    # sample_cards and sample_market_prices are automatically created
    pass
```

## OSS vs SaaS Mode

WondersTracker runs in two modes:

| Mode | Description | Who Uses It |
|------|-------------|-------------|
| **OSS** | Core features only, billing disabled | Contributors |
| **SaaS** | Full features with billing/metering | Production |

### How It Works

- The `saas/` directory contains proprietary code (billing, Polar integration)
- When `saas/` is not present, the app runs in OSS mode automatically
- All core features work identically in both modes

### What You'll See

On startup, check the logs:
```
INFO: WondersTracker API Starting
INFO: SaaS Features: DISABLED (OSS mode)   ← This is normal for contributors
INFO: Usage Metering: DISABLED
```

### Testing

SaaS-specific tests are automatically skipped when running in OSS mode:
```bash
poetry run pytest  # SaaS tests show as "skipped"
```

See [docs/architecture/saas-setup.md](docs/architecture/saas-setup.md) for more details.

## Development Workflow

### Branch Strategy

```
main (production)
  ↑
staging (pre-release testing)
  ↑
feature/your-feature (your work)
```

### Creating a Feature Branch

```bash
# Sync with upstream
git fetch upstream
git checkout main
git merge upstream/main

# Create feature branch
git checkout -b feature/your-feature-name
```

### Branch Naming Conventions

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feature/` | New features | `feature/portfolio-export` |
| `fix/` | Bug fixes | `fix/price-calculation` |
| `docs/` | Documentation | `docs/api-reference` |
| `refactor/` | Code refactoring | `refactor/scraper-module` |
| `test/` | Test additions | `test/pricing-service` |

## Making Changes

### Backend (Python)

1. **Follow PEP 8** and use type hints
2. **Run tests** before committing:
   ```bash
   poetry run pytest tests/ -v
   ```
3. **Check linting**:
   ```bash
   poetry run ruff check app/
   poetry run ruff format app/
   ```

### Frontend (TypeScript/React)

1. **Use TypeScript** for all new code
2. **Run type check**:
   ```bash
   cd frontend
   npm run typecheck
   ```
3. **Check linting**:
   ```bash
   npm run lint
   ```

### Database Changes

If your changes require database schema modifications:

1. Create a migration using Alembic
2. Test migration both up and down
3. Document the migration in your PR

## Commit Guidelines

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no code change |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or modifying tests |
| `chore` | Maintenance tasks |

### Examples

```bash
feat(pricing): add MAD-based FMP calculation
fix(scraper): handle eBay rate limiting gracefully
docs(readme): update installation instructions
test(api): add portfolio endpoint tests
```

## Pull Request Process

### Before Submitting

- [ ] Tests pass locally (`poetry run pytest`)
- [ ] Code is linted (`poetry run ruff check app/`)
- [ ] Frontend builds (`cd frontend && npm run build`)
- [ ] Documentation updated if needed
- [ ] Commit messages follow conventions

### PR Title Format

Same as commit format:
```
feat(scope): description
```

### PR Description

Use the PR template. Include:
- Summary of changes
- Related issues (e.g., "Fixes #123")
- Testing performed
- Screenshots for UI changes

### Review Process

1. Submit PR to `staging` branch
2. CI must pass
3. At least one approval required
4. Squash and merge when approved

## Testing

### Running Tests

```bash
# All tests
poetry run pytest

# With coverage
poetry run pytest --cov=app --cov-report=html

# Specific module
poetry run pytest tests/test_pricing.py -v

# Skip integration tests
poetry run pytest -m "not integration"
```

### Writing Tests

- Place tests in `tests/` directory
- Name test files `test_*.py`
- Use pytest fixtures for setup
- Mock external services (eBay, Discord, etc.)

Example:
```python
def test_calculate_fmp_returns_correct_value(test_session):
    """Test FMP calculation with valid sales data."""
    service = FairMarketPriceService(test_session)
    result = service.calculate_fmp(card_id=42, ...)

    assert result['fair_market_price'] is not None
    assert result['calculation_method'] == 'mad_trimmed'
```

## Documentation

### When to Update Docs

- New features require docs
- API changes require OpenAPI updates
- Configuration changes require `.env.example` updates

### Documentation Locations

| Content | Location |
|---------|----------|
| General | `README.md` |
| Contributing | `CONTRIBUTING.md` |
| API Reference | Auto-generated at `/docs` |
| Architecture | `docs/architecture/` |
| Runbooks | `docs/runbooks/` |
| Configuration | `docs/configuration.md` |

## Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open an Issue with the bug template
- **Features**: Open an Issue with the feature template

## Recognition

Contributors are recognized in:
- Git commit history
- GitHub contributors page
- Release notes (for significant contributions)

---

Thank you for contributing!
