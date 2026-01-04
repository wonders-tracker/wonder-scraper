# Data Quality Audit Report

**Date:** 2025-12-30
**Branch:** feature/data-quality-and-order-book

## Executive Summary

| Issue | Severity | Count | Action Required |
|-------|----------|-------|-----------------|
| Seller data - Active | CRITICAL | 0.9% coverage | Backfill from eBay |
| Seller data - Sold | HIGH | 44.4% coverage | Backfill from eBay |
| Bulk lots | HIGH | 252 listings | Flag and exclude from FMP |
| Missing URLs (sold) | MEDIUM | 57.3% | Historical - accept |
| Duplicates | LOW | 36 extra rows | Dedup script |
| Treatment coverage | OK | 100% | No action |
| Product subtype (sealed) | OK | 93.9% | No action |

## Dataset Overview

| Metric | Value |
|--------|-------|
| Total listings | 5,521 |
| Active listings | 2,985 |
| Sold listings | 2,536 |

### Platform Breakdown

| Platform | Active | Sold |
|----------|--------|------|
| eBay | 2,936 | 2,380 |
| Blokpax | 22 | 99 |
| OpenSea | 27 | 57 |

## Critical Issues

### 1. Seller Data Coverage

**Active Listings:**
- Only **27 of 2,985** (0.9%) have seller_name
- 0% have seller feedback scores
- Root cause: Scraper not extracting seller info for active listings

**Sold Listings:**
- Only **1,126 of 2,536** (44.4%) have seller_name
- 1,013 (39.9%) have feedback scores
- Root cause: Historical scrapes before seller extraction was added

**Action:**
- TASK-009: Backfill seller data from eBay
- TASK-011: Fix scraper to extract seller for active listings

### 2. Bulk Lot Contamination

**Count:** 252 potential bulk lots detected

**Pattern:** Listings with titles containing:
- "2X", "3X", "4X", "5X"
- "LOT OF", "BUNDLE", "PLAYSET"
- "\d+ cards", "\d+ pcs"

**Example Problem:**
```
$0.65 | 3X - Wonders of the First - Synapse Ridge...
```
These $0.65 bulk lots are corrupting floor price calculations.

**Action:**
- TASK-010: Add `is_bulk_lot` flag to MarketPrice model
- Update FMP calculation to exclude bulk lots

### 3. Missing URLs (Historical)

**Sold Listings:** 57.3% (1,452/2,536) missing URL

**Root cause:** Historical eBay data where URLs were not captured.

**Action:** Accept as historical limitation. New scrapes have URLs.

## Data Quality Metrics

### Treatment Coverage
- Active: 100% (2,985/2,985)
- Sold: 100% (2,536/2,536)
- **Status:** Excellent

### Product Subtype (Sealed Products)
- Sealed listings: 198
- With product_subtype: 186 (93.9%)
- **Status:** Good

### Price Outliers
- Price < $0.50: 30 listings (mostly bulk lots)
- Price > $5,000: 3 listings (high-end singles)
- **Status:** Expected, handled by outlier filtering

### Data Freshness
- Active listings: 2025-12-19 to 2025-12-30 (current)
- Sold listings: 2025-11-21 to 2025-12-19
- **Status:** Good

### Duplicates
- Duplicate groups: 34
- Extra rows: 36
- **Status:** Minor, needs cleanup

## Recommendations

### Immediate (Sprint 1)
1. Run seller data backfill (TASK-009)
2. Add bulk lot detection (TASK-010)
3. Update floor price calculation to exclude bulk lots

### Short-term (Sprint 2)
4. Fix active listing seller extraction in scraper
5. Add automated data quality tests
6. Set up daily quality monitoring

### Long-term (Sprint 3+)
7. Historical URL recovery (if possible)
8. Duplicate detection and cleanup
9. Data quality dashboard

## SQL Queries Used

```sql
-- Seller coverage
SELECT listing_type, COUNT(*),
       COUNT(CASE WHEN seller_name IS NOT NULL THEN 1 END)
FROM marketprice GROUP BY listing_type;

-- Bulk lot detection
SELECT COUNT(*) FROM marketprice
WHERE title ~* '(^|\s)(2x|3x|4x|5x|lot of|bundle|playset|set of)\s';

-- Duplicates
SELECT COUNT(*) FROM (
  SELECT card_id, price, seller_name, listing_type, COUNT(*)
  FROM marketprice WHERE seller_name IS NOT NULL
  GROUP BY card_id, price, seller_name, listing_type
  HAVING COUNT(*) > 1
) dupes;
```

## Appendix: Raw Audit Output

```
============================================================
DATA QUALITY AUDIT - Wonder Scraper
============================================================

### 1. OVERALL DATASET SIZE ###
Total listings: 5,521
  Active: 2,985
  Sold: 2,536

### 2. SELLER DATA COVERAGE ###
active: 27/2,985 have seller (0.9%), 0 have feedback (0.0%)
sold: 1,126/2,536 have seller (44.4%), 1,013 have feedback (39.9%)

### 3. PLATFORM BREAKDOWN ###
blokpax (active): 22
blokpax (sold): 99
ebay (active): 2,936
ebay (sold): 2,380
opensea (active): 27
opensea (sold): 57

### 4. POTENTIAL BULK LOTS ###
Potential bulk lots: 252

### 5. TREATMENT COVERAGE ###
active: 2,985/2,985 have treatment (100.0%)
sold: 2,536/2,536 have treatment (100.0%)

### 6. PRODUCT SUBTYPE (SEALED) ###
Sealed listings: 198
With product_subtype: 186 (93.9%)

### 7. PRICE OUTLIERS ###
Price < $0.50: 30
Price > $5000: 3

### 8. MISSING URLS ###
active: 23/2,985 missing URL (0.8%)
sold: 1,452/2,536 missing URL (57.3%)

### 9. DATA FRESHNESS ###
active: latest=2025-12-30, oldest=2025-12-19
sold: latest=2025-12-19, oldest=2025-11-21

### 10. POTENTIAL DUPLICATES ###
Duplicate groups: 34
Extra rows (potential dupes): 36
```
