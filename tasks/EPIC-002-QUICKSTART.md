# EPIC-002: Data Quality - Quick Start Guide

**For:** Engineering team starting work on data quality improvements
**Time to read:** 5 minutes
**Last updated:** 2025-12-18

---

## What is this epic?

We're fixing data quality issues in the marketplace scraper that currently:
- Miss seller info on 20-30% of listings
- Corrupt FMP pricing with $0.65 bulk lots attributed to single cards
- Have edge cases in treatment/subtype parsing

**Business impact:** FMP shows $0.22 instead of $44 for some cards due to bulk lots.

---

## Files to read

### 1. Start here (5 min read):
- **EPIC-002-SUMMARY.md** - Executive summary with phase breakdown and key decisions

### 2. Full details (20 min read):
- **EPIC-002-data-quality-improvements.md** - Complete epic with all 11 tasks, 40+ UOWs, risk assessment

### 3. Task deep-dives (10 min each):
- **TASK-008-data-quality-audit.md** - Write queries to measure data gaps
- **TASK-009-seller-data-backfill.md** - Script to backfill missing seller info
- **TASK-010-bulk-lot-detection.md** - Detect and flag bulk lots

---

## Sprint 1: What to do this week

### Monday-Tuesday (4 hours)
**Execute TASK-008: Data Quality Audit**

1. Write 4 SQL queries:
   - Seller coverage: `SELECT COUNT(*) ... WHERE seller_name IS NULL`
   - Bulk lot detection: `SELECT ... WHERE title ~ '(?i)(3x|lot of|bundle)'`
   - Product subtype coverage: `SELECT ... JOIN card ... WHERE product_type IN (...)`
   - Price outliers: `SELECT ... WHERE price > median + 3*stddev`

2. Run queries on production (Neon PostgreSQL)

3. Generate audit report:
   - Save to `tasks/TASK-008-data-audit-report.md`
   - Include: Seller coverage %, bulk lot count, examples
   - Prioritize findings (High/Medium/Low)

**Deliverable:** Audit report with baseline metrics

### Wednesday-Friday (5 hours)
**Execute TASK-009: Seller Data Backfill**

1. Create `scripts/backfill_seller_data.py`:
   - Fetch eBay HTML for each listing with `external_id`
   - Reuse `_extract_seller_info()` from `app/scraper/ebay.py`
   - Update MarketPrice records

2. Add safety features:
   - `--dry-run` flag to preview changes
   - Rate limiting: 10 requests/min (6s delay)
   - Error handling: HTTP 404, 429, parse errors

3. Test on 50 listings:
   - Verify accuracy (manual check)
   - Measure success rate (expect >90%)

4. Run on production:
   - Backfill ~500-1,500 listings (estimated)
   - Takes ~50 minutes at 10 req/min

**Deliverable:** Seller coverage >90%

---

## Sprint 2: Scraper improvements

### TASK-010: Bulk Lot Detection (4-6 hours)
**Goal:** Flag bulk lots so FMP excludes them

**Schema decision needed:**
- Option 1: Use `quantity=-1` as flag (hack)
- Option 2: Add `is_bulk_lot: bool` field (clean)
- **Recommendation:** Option 2

**Steps:**
1. Implement `_is_bulk_lot(title, product_type)` function
2. Add `is_bulk_lot` field to MarketPrice model (migration)
3. Integrate into scraper pipeline
4. Backfill existing listings (detect ~50-100 bulk lots)
5. Update FMP service: `WHERE is_bulk_lot = False`

**Deliverable:** Zero bulk lots corrupting FMP

### TASK-011: Improved Seller Extraction (3-4 hours)
**Goal:** Fix seller extraction for new eBay `.s-card` HTML format

**Steps:**
1. Analyze new eBay HTML structure
2. Update `_extract_seller_info()` to handle `.s-card` selectors
3. Test on 100 recent listings (expect >95% success)

**Deliverable:** New scrapes >95% seller data populated

### TASK-013: Treatment Edge Cases (2-3 hours)
**Goal:** Fix Alt Art, Proof/Sample, grading detection edge cases

**Steps:**
1. Add A1-A8 pattern for Alt Art detection
2. Clarify Proof/Sample vs Promo logic
3. Fix TAG vs STAG grading conflict
4. Test on production data (<5 failures)

**Deliverable:** Treatment accuracy >99.99%

---

## Sprint 3: Testing & monitoring

### TASK-014: Data Quality Test Suite (4-6 hours)
**Goal:** Automated pytest suite for data quality validation

**Test coverage:**
- Seller data presence (>90%)
- Treatment validity (known list)
- Quantity sanity (1-100 range, bulk flag)
- Price outliers (IQR method)
- Bulk lot pattern detection

**Deliverable:** Test suite in CI/CD

### TASK-015: Daily Quality Check Job (3-4 hours)
**Goal:** Automated daily job with Discord alerts

**Metrics to track:**
- Seller coverage %
- Bulk lot count
- Treatment coverage %
- Price outlier count

**Alert thresholds:**
- Seller coverage <90%
- Bulk lot count >10
- Price outliers >5

**Deliverable:** Daily quality checks running in production

---

## Key decisions

### 1. Bulk lot schema (URGENT - blocks Sprint 2)
**Question:** `quantity=-1` hack or `is_bulk_lot: bool` field?
**Recommendation:** `is_bulk_lot` field for clarity
**Decision by:** End of Sprint 1 (Week 2)

### 2. Alert thresholds
**Current proposal:**
- Seller coverage <90%
- Bulk lot count >10/week
- Price outliers >5/day

**Tune after:** Sprint 1 audit data

### 3. Manual review workflow
**Question:** Admin UI for flagged listings?
**Recommendation:** Defer to future epic (SQL queries sufficient for now)

---

## How to run queries

### Connect to production DB
```bash
# .env file has DATABASE_URL
source .env
psql $DATABASE_URL
```

### Example queries

**Seller coverage:**
```sql
SELECT
    platform,
    listing_type,
    COUNT(*) as total,
    COUNT(seller_name) as has_seller,
    ROUND(100.0 * COUNT(seller_name) / COUNT(*), 2) as coverage_pct
FROM marketprice
GROUP BY platform, listing_type;
```

**Bulk lot detection:**
```sql
SELECT
    id, title, price, card_id
FROM marketprice
WHERE title ~* '(3x|4x|5x|lot of|bundle|random|mixed|assorted|\d+\s+card\s+lot)'
    AND title !~* '(play bundle|blaster box|collector booster box|serialized advantage)'
ORDER BY card_id, price;
```

---

## File structure

```
tasks/
├── EPIC-002-data-quality-improvements.md  (29KB - full epic)
├── EPIC-002-SUMMARY.md                    (9.4KB - executive summary)
├── EPIC-002-QUICKSTART.md                 (this file)
├── TASK-008-data-quality-audit.md         (10KB - audit queries)
├── TASK-009-seller-data-backfill.md       (14KB - backfill script)
├── TASK-010-bulk-lot-detection.md         (18KB - bulk lot flagging)
└── queries/                               (to be created in TASK-008)
    ├── seller_coverage.sql
    ├── bulk_lot_detection.sql
    └── subtype_coverage.sql
```

---

## Success metrics

### Before (current)
- Seller coverage: ~70-80%
- Bulk lot count: ~50-100 (corrupting FMP)
- No monitoring

### After (target)
- Seller coverage: >95%
- Bulk lots: 0 affecting FMP (flagged)
- Daily quality checks with alerts

---

## Questions?

- **EPIC scope:** See EPIC-002-data-quality-improvements.md
- **Task details:** See individual TASK-*.md files
- **Quick overview:** This file (EPIC-002-QUICKSTART.md)
- **Team sync:** Schedule in Week 1 for bulk lot schema decision

---

## Next immediate action

1. Read EPIC-002-SUMMARY.md (5 min)
2. Review TASK-008 (10 min)
3. Schedule team sync for bulk lot schema decision
4. Start Sprint 1: Execute TASK-008 (audit)

Good luck!
