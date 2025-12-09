# SaaS Module Setup

This document explains how the SaaS/billing features are separated from the core open-source codebase.

## Architecture Overview

WondersTracker uses a **dual-mode architecture**:

- **OSS Mode**: Core functionality runs without the `saas/` module. Billing endpoints return 501, metering is disabled.
- **SaaS Mode**: Full functionality with billing, usage metering, and Polar integration.

## How It Works

### Import Wrappers

The main `app/` directory contains wrapper modules that gracefully handle the absence of `saas/`:

```
app/
├── api/
│   ├── billing.py      # Imports from saas/api/billing.py or provides stub
│   └── webhooks.py     # Imports from saas/api/webhooks.py or provides stub
├── middleware/
│   └── metering.py     # Imports from saas/middleware/metering.py or pass-through
└── services/
    └── polar.py        # Imports from saas/services/polar.py or provides stub
```

Each wrapper follows this pattern:

```python
try:
    from saas.api.billing import router
    BILLING_AVAILABLE = True
except ImportError:
    BILLING_AVAILABLE = False
    # Provide stub implementation
    router = APIRouter()
    @router.get("/billing/status")
    async def billing_status():
        return {"available": False}
```

### SaaS Module Structure

The private `saas/` module contains:

```
saas/
├── __init__.py         # Exports all SaaS components
├── api/
│   ├── billing.py      # Polar checkout, portal, subscription management
│   └── webhooks.py     # Polar webhook handlers
├── middleware/
│   └── metering.py     # API usage tracking for billing
├── services/
│   └── polar.py        # Polar SDK integration
└── tests/              # SaaS-specific tests
    ├── conftest.py
    └── test_*.py
```

## For OSS Contributors

**You don't need the `saas/` module!** The app runs fully in OSS mode:

```bash
# Clone and run - no extra setup needed
git clone https://github.com/yourusername/wonder-scraper.git
cd wonder-scraper
poetry install
poetry run uvicorn app.main:app --reload
```

Check startup logs for mode confirmation:
```
INFO: WondersTracker API Starting
INFO: SaaS Features: DISABLED (OSS mode)
INFO: Usage Metering: DISABLED
```

## For Maintainers (SaaS Setup)

### Option 1: Git Submodule (Recommended)

1. **Create private repository** for SaaS code:
   ```bash
   # In a separate directory
   mkdir wonderstracker-saas
   cd wonderstracker-saas
   git init
   # Copy saas/ contents here
   git add .
   git commit -m "Initial SaaS module"
   git remote add origin git@github.com:yourusername/wonderstracker-saas.git
   git push -u origin main
   ```

2. **Add as submodule** in main repo:
   ```bash
   cd wonder-scraper
   git submodule add git@github.com:yourusername/wonderstracker-saas.git saas
   git commit -m "Add SaaS submodule"
   ```

3. **Clone with submodule**:
   ```bash
   git clone --recurse-submodules git@github.com:yourusername/wonder-scraper.git
   # Or if already cloned:
   git submodule update --init --recursive
   ```

### Option 2: Local Development

For local development without submodule setup:

1. Create `saas/` directory manually
2. Copy the SaaS files from private repo/backup
3. The directory is gitignored (won't be committed)

### CI/CD Configuration

GitHub Actions automatically handles both modes:

1. **OSS CI** (no submodule token): Runs tests in OSS mode, SaaS tests are skipped
2. **Full CI** (with submodule token): Runs complete test suite

To enable full CI, add repository secret:
- Name: `SAAS_SUBMODULE_TOKEN`
- Value: GitHub PAT with access to private saas repo

## Testing

### Running Tests

```bash
# All tests (SaaS tests skipped if module not available)
poetry run pytest

# Only OSS tests explicitly
poetry run pytest tests/ -m "not saas"

# Only SaaS tests (requires saas/ module)
poetry run pytest -m saas
```

### Test Markers

- `@pytest.mark.saas` - Tests requiring SaaS module
- `@pytest.mark.integration` - Tests requiring PostgreSQL database

## Environment Variables

SaaS mode requires additional environment variables:

```env
# Polar Integration (SaaS only)
POLAR_ACCESS_TOKEN=your_polar_token
POLAR_WEBHOOK_SECRET=your_webhook_secret
POLAR_ORGANIZATION_ID=your_org_id

# Product IDs
POLAR_PRODUCT_ID_PRO=prod_xxx
POLAR_PRODUCT_ID_PREMIUM=prod_yyy
```

## Feature Detection

Check SaaS availability in code:

```python
from app.api.billing import BILLING_AVAILABLE
from app.middleware.metering import METERING_AVAILABLE
from app.services.polar import POLAR_AVAILABLE

if BILLING_AVAILABLE:
    # SaaS features enabled
    pass
```

## Troubleshooting

### "SaaS module not available" in logs

Expected in OSS mode. If you need SaaS features:
1. Ensure `saas/` directory exists
2. Ensure `saas/__init__.py` exists and exports correctly
3. Check for import errors: `python -c "import saas"`

### Submodule not updating

```bash
git submodule update --remote --merge
```

### Tests failing with "saas not found"

Ensure tests are properly marked:
```python
@pytest.mark.saas
def test_billing_checkout():
    ...
```
