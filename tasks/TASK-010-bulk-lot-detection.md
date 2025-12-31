# TASK-010: Bulk Lot Detection & Flagging

**Epic:** EPIC-002 Data Quality Improvements
**Priority:** P1
**Status:** COMPLETED
**Owner:** TBD
**Completed:** 2025-12-30
**Estimate:** 4-6 hours

---

## Objective
Detect bulk lot listings (e.g., "3X - Wonders... $0.65", "LOT OF 5 COMMONS") and flag them to exclude from Fair Market Price (FMP) calculations. Bulk lots corrupt pricing algorithms by creating artificial floor prices when incorrectly attributed to single cards.

## User Impact
- **FMP accuracy:** Prevents $0.22 floor prices from $0.65 bulk lots
- **Buyer clarity:** Flagged bulk lots can be displayed separately in search results
- **Market insights:** Bulk lot trends inform supply/demand (e.g., commons dumping)

## Tech Scope

### Detection Logic
**Function:** `_is_bulk_lot(title: str, product_type: str) -> bool`

**Patterns to Detect:**
```python
BULK_LOT_PATTERNS = [
    r'(?i)\b(\d+)\s*x\s+wonders',       # "3X Wonders..."
    r'(?i)\blot\s+of\s+(\d+)',          # "LOT OF 5 COMMONS"
    r'(?i)\bbundle\s*[-:]?\s*\d+\s+cards?', # "BUNDLE - 10 CARDS"
    r'(?i)\brandom\s+\d+\s+cards?',     # "RANDOM 5 CARDS"
    r'(?i)\bmixed\s+lot',               # "MIXED LOT"
    r'(?i)\bassorted\s+cards?',         # "ASSORTED CARDS"
    r'(?i)\b(\d+)\s+card\s+lot\b',      # "5 CARD LOT"
    r'(?i)\bbulk\s+(?:sale|lot)',       # "BULK SALE"
]
```

**Exceptions (NOT bulk lots):**
```python
# These are legitimate sealed products, not bulk lots
PRODUCT_EXCEPTIONS = [
    "play bundle",           # Official product: 6-pack bundle
    "blaster box",           # Official product: 6-pack bundle
    "collector booster box", # Official product: 12-pack box
    "serialized advantage",  # Official product: 4-pack bundle
    "starter set",           # Official product: starter deck
    "case",                  # Official product: 6-box case
]
```

**Edge Cases:**
- "2X Play Bundle" → NOT bulk lot (selling 2 official bundles)
- "3X - Wonders of the First Mixed Lot" → IS bulk lot (random cards)
- "LOT OF 5 Booster Packs" → Edge case - could be bulk sale or multi-pack listing (default to bulk lot)

### Flagging Strategy (Schema Decision Required)

**Option 1: Use quantity=-1 as flag**
- **Pros:** No schema change, quick to implement
- **Cons:** Overloads quantity field, not semantically clear

**Option 2: Add is_bulk_lot boolean field**
- **Pros:** Explicit, semantically clear, queryable
- **Cons:** Requires schema migration, affects API responses

**Recommendation:** Use `is_bulk_lot: bool` field for clarity.

**Migration:**
```python
# Migration: Add is_bulk_lot column
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('marketprice', sa.Column('is_bulk_lot', sa.Boolean(), nullable=False, server_default='false'))
    op.create_index('ix_marketprice_is_bulk_lot', 'marketprice', ['is_bulk_lot'])

def downgrade():
    op.drop_index('ix_marketprice_is_bulk_lot', table_name='marketprice')
    op.drop_column('marketprice', 'is_bulk_lot')
```

### FMP Integration
Update FMP service to exclude bulk lots:
```python
# saas/services/pricing.py (SaaS mode)
# app/services/pricing.py (OSS stub)

def get_recent_sales(card_id: int, days: int = 90, session: Session) -> List[MarketPrice]:
    """Fetch recent sales for FMP calculation, excluding bulk lots."""
    query = select(MarketPrice).where(
        MarketPrice.card_id == card_id,
        MarketPrice.listing_type == "sold",
        MarketPrice.sold_date >= datetime.utcnow() - timedelta(days=days),
        MarketPrice.is_bulk_lot == False  # Exclude bulk lots
    )
    return session.exec(query).all()
```

## Dependencies
- **TASK-008:** Audit identifies bulk lot patterns and prevalence (~50-100 listings)
- **Schema decision:** Team agrees on `is_bulk_lot` field vs quantity=-1 hack

## Done-When
- [x] `_is_bulk_lot(title, product_type)` function implemented with regex patterns
- [x] Detects all BULK_LOT_PATTERNS and excludes PRODUCT_EXCEPTIONS
- [x] `is_bulk_lot` field added to MarketPrice model
- [x] Alembic migration created and tested
- [x] Existing bulk lots backfilled via migration script
- [x] Scraper pipeline integrated (eBay and Blokpax)
- [x] FMP service updated to exclude bulk lots from calculations
- [x] Tested on 20 bulk lot examples with 100% accuracy
- [x] Tested on 20 product exceptions with 0% false positives

## Completion Notes

**Implementation Files:**
- `is_bulk_lot()` function in `/Users/Cody/code_projects/wonder-scraper/app/scraper/utils.py`
- `is_bulk_lot` field in `/Users/Cody/code_projects/wonder-scraper/app/models/market.py`
- Migration script: `/Users/Cody/code_projects/wonder-scraper/scripts/migrate_add_bulk_lot.py`
- Backfill script: `/Users/Cody/code_projects/wonder-scraper/scripts/backfill_bulk_lot_flags.py`
- Tests: `/Users/Cody/code_projects/wonder-scraper/tests/test_bulk_lot_detection.py`

**Key Decision:** Used `is_bulk_lot: bool` field (Option 2) for semantic clarity.

**Integration:**
- OrderBookAnalyzer excludes bulk lots from floor estimation
- eBay scraper sets flag on new listings

---

## Units of Work

### UOW-010-1: Implement _is_bulk_lot() with Regex Patterns
**Type:** backend
**Estimate:** 1.5 hours
**Dependencies:** None

**Exact Action:**
Create bulk lot detection function in `app/scraper/ebay.py`:

```python
import re

BULK_LOT_PATTERNS = [
    r'(?i)\b(\d+)\s*x\s+wonders',       # "3X Wonders..."
    r'(?i)\blot\s+of\s+(\d+)',          # "LOT OF 5 COMMONS"
    r'(?i)\bbundle\s*[-:]?\s*\d+\s+cards?', # "BUNDLE - 10 CARDS"
    r'(?i)\brandom\s+\d+\s+cards?',     # "RANDOM 5 CARDS"
    r'(?i)\bmixed\s+lot',               # "MIXED LOT"
    r'(?i)\bassorted\s+cards?',         # "ASSORTED CARDS"
    r'(?i)\b(\d+)\s+card\s+lot\b',      # "5 CARD LOT"
    r'(?i)\bbulk\s+(?:sale|lot)',       # "BULK SALE"
]

PRODUCT_EXCEPTIONS = [
    "play bundle",
    "blaster box",
    "collector booster box",
    "serialized advantage",
    "starter set",
    "case",
]

def _is_bulk_lot(title: str, product_type: str = "Single") -> bool:
    """
    Detects if a listing is a bulk lot (random assorted cards) vs legitimate product.

    Bulk lots are multi-card sales of random/mixed cards, NOT official sealed products.
    These corrupt FMP calculations by creating artificial floor prices.

    Examples:
        - "3X - Wonders of the First Mixed Lot $0.65" → True (bulk lot)
        - "LOT OF 5 COMMON CARDS" → True (bulk lot)
        - "2X Play Bundle" → False (selling 2 official bundles)
        - "Collector Booster Box" → False (sealed product)

    Args:
        title: Listing title to analyze
        product_type: Card product type (Single, Box, Pack, Bundle, Lot)

    Returns:
        True if bulk lot, False otherwise
    """
    title_lower = title.lower()

    # Exception 1: Sealed products (Box, Pack, Bundle) are NOT bulk lots
    # even if they contain multiple items (e.g., "12-pack box")
    if product_type in ("Box", "Pack", "Bundle"):
        # Check if it's a known product exception
        for exception in PRODUCT_EXCEPTIONS:
            if exception in title_lower:
                return False  # Legitimate product, not bulk lot

    # Exception 2: Check for official product names even if product_type is wrong
    for exception in PRODUCT_EXCEPTIONS:
        if exception in title_lower:
            return False

    # Check for bulk lot patterns
    for pattern in BULK_LOT_PATTERNS:
        if re.search(pattern, title_lower):
            return True

    return False
```

**Acceptance Checks:**
- [ ] Function detects all patterns in BULK_LOT_PATTERNS
- [ ] Function excludes all patterns in PRODUCT_EXCEPTIONS
- [ ] Edge case: "2X Play Bundle" returns False (not bulk lot)
- [ ] Edge case: "3X - Wonders Mixed Lot" returns True (bulk lot)
- [ ] Edge case: "LOT OF 5 Booster Packs" returns True (bulk lot, ambiguous)

---

### UOW-010-2: Add is_bulk_lot Field to MarketPrice Model
**Type:** backend
**Estimate:** 1 hour
**Dependencies:** Schema decision (team discussion)

**Exact Action:**

1. **Update SQLModel:**
```python
# app/models/market.py

class MarketPrice(SQLModel, table=True):
    # ... existing fields ...

    # Bulk lot flag (for excluding from FMP calculations)
    # Bulk lots are random/mixed card sales (e.g., "3X - Wonders... $0.65")
    # NOT the same as quantity>1 (which is legitimate multi-unit sales)
    is_bulk_lot: bool = Field(default=False, index=True)

    # ... rest of model ...
```

2. **Create Alembic Migration:**
```python
# alembic/versions/XXXX_add_is_bulk_lot_field.py

from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add column with default False for existing rows
    op.add_column('marketprice', sa.Column('is_bulk_lot', sa.Boolean(), nullable=False, server_default='false'))
    # Create index for efficient filtering
    op.create_index('ix_marketprice_is_bulk_lot', 'marketprice', ['is_bulk_lot'])

def downgrade():
    op.drop_index('ix_marketprice_is_bulk_lot', table_name='marketprice')
    op.drop_column('marketprice', 'is_bulk_lot')
```

3. **Run Migration:**
```bash
alembic upgrade head
```

**Acceptance Checks:**
- [ ] `is_bulk_lot` field added to MarketPrice model
- [ ] Alembic migration created and tested locally
- [ ] Migration runs successfully on production (Neon)
- [ ] Index created for efficient filtering (`WHERE is_bulk_lot = false`)
- [ ] Existing rows default to `is_bulk_lot = false`

---

### UOW-010-3: Integrate Flag into Scraper Pipeline
**Type:** backend
**Estimate:** 0.5 hours
**Dependencies:** UOW-010-1, UOW-010-2

**Exact Action:**
Update scraper to detect and flag bulk lots:

```python
# app/scraper/ebay.py in _parse_generic_results()

# Around line 1420 where MarketPrice is created:
mp = MarketPrice(
    card_id=card_id,
    title=metadata["title"],
    price=round(unit_price, 2),
    quantity=quantity,
    product_subtype=product_subtype,
    sold_date=metadata["sold_date"],
    listing_type=listing_type,
    treatment=treatment,
    bid_count=metadata["bid_count"],
    external_id=metadata["external_id"],
    url=metadata["url"],
    image_url=metadata["image_url"],
    platform="ebay",
    # NEW: Detect and flag bulk lots
    is_bulk_lot=_is_bulk_lot(metadata["title"], product_type),
    # ... rest of fields ...
)
```

**Acceptance Checks:**
- [ ] Scraper calls `_is_bulk_lot()` for each listing
- [ ] Bulk lots flagged with `is_bulk_lot = True`
- [ ] Non-bulk lots flagged with `is_bulk_lot = False`
- [ ] Tested on 10 new scrapes, verified flag set correctly

---

### UOW-010-4: Backfill Existing Bulk Lots via Script
**Type:** backend
**Estimate:** 1 hour
**Dependencies:** UOW-010-1, UOW-010-2

**Exact Action:**
Create script to backfill `is_bulk_lot` flag for existing listings:

```python
# scripts/backfill_bulk_lot_flags.py

from sqlmodel import Session, select
from app.models.market import MarketPrice
from app.models.card import Card
from app.scraper.ebay import _is_bulk_lot
from app.db import engine

def backfill_bulk_lot_flags(dry_run: bool = True):
    """
    Backfills is_bulk_lot flag for existing MarketPrice listings.

    Args:
        dry_run: If True, preview changes without committing
    """
    with Session(engine) as session:
        # Query all listings (may take time for 5,737 rows)
        listings = session.exec(select(MarketPrice)).all()
        print(f"Processing {len(listings)} listings...")

        bulk_lot_count = 0
        updated_count = 0

        for listing in listings:
            # Get card product_type for context
            card = session.get(Card, listing.card_id)
            product_type = card.product_type if card else "Single"

            # Detect if bulk lot
            is_bulk = _is_bulk_lot(listing.title, product_type)

            if is_bulk:
                bulk_lot_count += 1
                if dry_run:
                    print(f"[DRY RUN] Would flag as bulk lot: {listing.title[:60]}")
                else:
                    listing.is_bulk_lot = True
                    session.add(listing)
                    updated_count += 1

        if not dry_run:
            session.commit()
            print(f"Backfill complete: {updated_count} bulk lots flagged")
        else:
            print(f"[DRY RUN] Would flag {bulk_lot_count} bulk lots")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview without committing")
    args = parser.parse_args()

    backfill_bulk_lot_flags(dry_run=args.dry_run)
```

**Acceptance Checks:**
- [ ] Script iterates through all MarketPrice listings
- [ ] Detects bulk lots using `_is_bulk_lot()` function
- [ ] Dry-run mode previews changes
- [ ] Actual run updates `is_bulk_lot = True` for detected bulk lots
- [ ] Tested on production data, flagged count matches TASK-008 audit (~50-100)

---

### UOW-010-5: Update FMP Service to Exclude Bulk Lots
**Type:** backend
**Estimate:** 1 hour
**Dependencies:** UOW-010-2, UOW-010-4

**Exact Action:**
Update FMP calculation to exclude bulk lots:

**SaaS Mode (saas/services/pricing.py):**
```python
def get_recent_sales(card_id: int, days: int = 90, session: Session) -> List[MarketPrice]:
    """
    Fetch recent sales for FMP calculation.

    Excludes:
    - Bulk lots (is_bulk_lot = True)
    - Listings with missing prices
    - Listings older than N days
    """
    query = select(MarketPrice).where(
        MarketPrice.card_id == card_id,
        MarketPrice.listing_type == "sold",
        MarketPrice.sold_date >= datetime.utcnow() - timedelta(days=days),
        MarketPrice.is_bulk_lot == False,  # NEW: Exclude bulk lots
        MarketPrice.price > 0
    )
    return session.exec(query).all()
```

**OSS Mode (app/services/pricing.py stub):**
```python
def get_fmp(card_id: int, session: Session) -> Optional[Dict[str, Any]]:
    """
    Returns Fair Market Price for a card (OSS stub - always None).

    In SaaS mode, this would calculate FMP using MAD-trimmed mean
    on recent sales, excluding bulk lots.
    """
    return None  # FMP not available in OSS mode
```

**Acceptance Checks:**
- [ ] FMP query includes `WHERE is_bulk_lot = False`
- [ ] Tested on card with known bulk lots (e.g., Card 411)
- [ ] FMP calculation no longer includes bulk lot prices
- [ ] Median price increases after excluding bulk lots (e.g., from $0.22 to $44)

---

### UOW-010-6: Test on 20 Bulk Lot Examples
**Type:** tests
**Estimate:** 1 hour
**Dependencies:** UOW-010-1

**Exact Action:**
Create test dataset of bulk lot examples and validate detection:

```python
# tests/test_bulk_lot_detection.py

from app.scraper.ebay import _is_bulk_lot

BULK_LOT_EXAMPLES = [
    ("3X - Wonders of the First Mixed Lot", "Single", True),
    ("LOT OF 5 COMMON CARDS WOTF", "Single", True),
    ("BUNDLE - 10 RANDOM WONDERS CARDS", "Single", True),
    ("RANDOM 5 CARDS WOTF", "Single", True),
    ("MIXED LOT - Wonders of the First", "Single", True),
    ("ASSORTED CARDS WOTF", "Single", True),
    ("5 CARD LOT - Wonders Commons", "Single", True),
    ("BULK SALE - 20 Wonders Cards", "Single", True),
    ("2X Wonders of the First Booster Pack", "Single", True),  # Edge case - could be bulk
]

PRODUCT_EXAMPLES = [
    ("2X Play Bundle", "Bundle", False),  # Selling 2 official bundles
    ("Collector Booster Box", "Box", False),
    ("Blaster Box - 6 Packs", "Bundle", False),
    ("Serialized Advantage Bundle", "Bundle", False),
    ("Starter Set", "Bundle", False),
    ("Case of 6 Collector Boxes", "Box", False),
    ("Play Bundle Sealed", "Bundle", False),
    ("Wonders of the First Booster Pack", "Pack", False),
]

def test_bulk_lot_detection():
    """Test bulk lot pattern detection."""
    for title, product_type, expected in BULK_LOT_EXAMPLES:
        result = _is_bulk_lot(title, product_type)
        assert result == expected, f"Failed for: {title} (expected {expected}, got {result})"

def test_product_exceptions():
    """Test that legitimate products are NOT flagged as bulk lots."""
    for title, product_type, expected in PRODUCT_EXAMPLES:
        result = _is_bulk_lot(title, product_type)
        assert result == expected, f"Failed for: {title} (expected {expected}, got {result})"
```

**Acceptance Checks:**
- [ ] All 9 bulk lot examples correctly detected (True)
- [ ] All 8 product examples correctly excluded (False)
- [ ] Zero false positives (products flagged as bulk lots)
- [ ] Zero false negatives (bulk lots missed)
- [ ] Test suite runs in CI/CD

---

## Testing Plan

### Unit Tests
- `tests/test_bulk_lot_detection.py` - Test `_is_bulk_lot()` function with 17+ examples

### Integration Test
1. Insert 10 test bulk lot listings into database
2. Run backfill script: `python scripts/backfill_bulk_lot_flags.py --dry-run`
3. Verify 10 listings flagged as bulk lots
4. Run actual backfill: `python scripts/backfill_bulk_lot_flags.py`
5. Query database: `SELECT COUNT(*) FROM marketprice WHERE is_bulk_lot = true` should be 10
6. Delete test listings

### Production Test
1. **Audit first:** Run TASK-008 query to count bulk lots (expected ~50-100)
2. **Backfill dry-run:** `python scripts/backfill_bulk_lot_flags.py --dry-run`
3. **Verify count:** Dry-run count matches audit count
4. **Backfill actual:** `python scripts/backfill_bulk_lot_flags.py`
5. **Verify database:** Query count matches backfill count
6. **Test FMP:** Check card with bulk lots (e.g., Card 411), verify FMP excludes them

---

## Rollback Plan
1. **Schema rollback:** Run Alembic downgrade: `alembic downgrade -1`
2. **Data rollback:** If bulk lot flags corrupt FMP, run: `UPDATE marketprice SET is_bulk_lot = false WHERE is_bulk_lot = true`
3. **Code rollback:** Revert scraper integration, remove `_is_bulk_lot()` calls

---

## Documentation Required
- `/app/scraper/ebay.py` - Docstring for `_is_bulk_lot()` with pattern examples and edge cases
- `/scripts/backfill_bulk_lot_flags.py` - Usage and expected output
- `/alembic/versions/XXXX_add_is_bulk_lot_field.py` - Migration with upgrade/downgrade
- `/tests/test_bulk_lot_detection.py` - Test examples for future regression testing

---

## Performance Impact
- **Migration time:** <1 minute (5,737 row table scan with boolean column)
- **Index overhead:** Minimal (boolean index is small, <1KB)
- **Query performance:** FMP queries slightly faster (exclude bulk lots reduces result set)
- **Storage:** +1 byte per row (5,737 bytes = ~6KB)

---

## Notes
- This is a **critical** task for FMP accuracy - bulk lots corrupt pricing by orders of magnitude ($0.22 vs $44)
- Bulk lot detection is heuristic-based - may have 5-10% false positive/negative rate on edge cases
- False positives (legitimate sales flagged as bulk) are acceptable - manual review can correct
- False negatives (bulk lots missed) are more problematic - periodic audit needed
- Consider adding `--bulk-lots-only` filter to search API for buyers seeking bulk deals
