# TASK-008: Data Quality Audit & Backfill Planning

**Epic:** EPIC-002 Data Quality Improvements
**Priority:** P0 (Blocking)
**Status:** COMPLETED
**Owner:** TBD
**Completed:** 2025-12-30
**Estimate:** 2-4 hours

---

## Objective
Quantify current data gaps in the MarketPrice table and identify patterns for backfilling. This audit provides the baseline metrics to measure improvement and informs the scope of TASK-009 (seller backfill) and TASK-010 (bulk lot detection).

## User Impact
Transparent data quality metrics enable:
- Product team to prioritize which data issues affect FMP accuracy most
- Engineering team to estimate backfill effort and scraper improvement ROI
- Future monitoring to detect regression in data quality

## Tech Scope

### Queries to Write
1. **Seller Data Coverage Query**
   - Measure `seller_name IS NULL` rate by platform (ebay, blokpax) and listing_type (sold, active)
   - Breakdown: Total listings, Missing seller_name, Missing feedback_score, Missing feedback_percent
   - Expected output: Percentage coverage per dimension

2. **Bulk Lot Detection Query**
   - Pattern match on `title` field using regex for bulk indicators
   - Patterns: `(?i)(3x|4x|5x|lot of|bundle|random|mixed|assorted|\d+\s*card\s*lot)`
   - Filter out legitimate multi-card sales (e.g., "Play Bundle" is a product, not a bulk lot)
   - Expected output: Count of bulk lots, grouped by pattern type

3. **Product Subtype Coverage Query**
   - Measure `product_subtype IS NOT NULL` rate for sealed products (product_type IN ('Box', 'Pack', 'Bundle', 'Lot'))
   - Join with Card table to filter by product_type
   - Expected output: Total sealed listings, Subtype populated count, Coverage %

4. **Price Outlier Detection Query**
   - Identify listings with price >3 standard deviations from card median
   - Group by card_id, calculate median and stddev
   - Flag listings as potential errors (or rare variants)
   - Expected output: Count of outliers, top 10 by deviation magnitude

### Report Structure
```markdown
# Data Quality Audit Report
**Date:** 2025-12-18
**Database:** Neon PostgreSQL (wonder-scraper production)

## Summary
- Total listings: 5,737 (3,327 active + 2,410 sold)
- Platforms: eBay (X%), Blokpax (Y%)
- Date range: [earliest sold_date] to [latest scraped_at]

## 1. Seller Data Coverage
| Dimension | Total | Missing seller_name | Missing feedback | Coverage % |
|-----------|-------|---------------------|------------------|------------|
| eBay Sold | X | X | X | X% |
| eBay Active | X | X | X | X% |
| Blokpax Sold | X | X | X | X% |
| Blokpax Active | X | X | X | X% |
| **Overall** | **5,737** | **X** | **X** | **X%** |

**Findings:**
- [e.g., eBay active listings have 85% seller coverage, sold listings only 70%]
- [Root cause hypothesis: New `.s-card` format not parsed correctly]

**Backfill Feasibility:**
- Listings with external_id: X (can re-fetch from eBay)
- Listings without external_id: X (cannot backfill, accept gap)

## 2. Bulk Lot Detection
| Pattern | Count | Example Titles |
|---------|-------|----------------|
| "3X", "4X", "5X" | X | [examples] |
| "LOT OF" | X | [examples] |
| "BUNDLE" (non-product) | X | [examples] |
| "RANDOM", "MIXED" | X | [examples] |
| "X CARD LOT" | X | [examples] |
| **Total Bulk Lots** | **X** | - |

**Findings:**
- [e.g., 73 listings detected as bulk lots, average price $2.45]
- [Affected cards: X cards have bulk lots incorrectly skewing median]

**Backfill Feasibility:**
- Flag via quantity=-1 or new is_bulk_lot field (schema decision needed)
- Estimated migration time: <1 min (5,737 row table scan)

## 3. Product Subtype Coverage (Sealed Products)
| Product Type | Total Listings | Subtype Populated | Coverage % |
|--------------|----------------|-------------------|------------|
| Box | X | X | X% |
| Pack | X | X | X% |
| Bundle | X | X | X% |
| Lot | X | X | X% |
| **Total Sealed** | **X** | **63** | **X%** |

**Findings:**
- [e.g., Only 1.9% of sealed products have subtype populated]
- [Root cause: Parser detects subtypes but doesn't populate for all variants]

**Backfill Feasibility:**
- Re-run `_detect_product_subtype()` on existing titles (no API call needed)
- Estimated time: <5 min (batch update)

## 4. Price Outliers
| Card Name | Listing Count | Median Price | Outlier Count | Max Deviation |
|-----------|---------------|--------------|---------------|---------------|
| [Card 411] | X | $44.00 | X | $0.99 (-98%) |
| [Example 2] | X | $X.XX | X | $X.XX (+X%) |

**Findings:**
- [e.g., Card 411 has $0.99 listings that are Play Bundle Packs mixed with Collector Packs]
- [Root cause: Variant mixing (same card_id for different sealed products)]

**Remediation:**
- Variant mixing requires card model normalization (out of scope for this epic → EPIC-003)
- For now: Document as known issue, exclude outliers from FMP via IQR filtering

## 5. Recommendations
1. **High Priority:**
   - Backfill seller data for listings with external_id (TASK-009)
   - Implement bulk lot detection and flag (TASK-010)

2. **Medium Priority:**
   - Re-run product subtype detection on existing sealed listings (TASK-012)
   - Improve seller extraction for new scrapes (TASK-011)

3. **Low Priority:**
   - Treatment edge case fixes (TASK-013) - affects <5 listings
   - Variant mixing fix (EPIC-003) - requires card model changes

4. **Monitoring:**
   - Track seller coverage weekly to detect scraper regression
   - Alert if bulk lot count increases >10/week (new scraper bug)
```

## Dependencies
None (blocking task for Sprint 1)

## Done-When
- [x] All 4 SQL queries written and tested on production database
- [x] Audit report markdown file generated and saved to `docs/DATA_QUALITY_AUDIT_2025-12-30.md`
- [x] Seller coverage percentage measured and documented
- [x] Bulk lot count measured and example titles extracted
- [x] Product subtype coverage measured for sealed products
- [x] Price outlier count measured with top 10 examples
- [x] Recommendations prioritized (High/Medium/Low)
- [x] Report reviewed by team and backfill scope agreed

## Completion Notes

Full audit completed on 2025-12-30. Key findings:
- Seller coverage: 0.9% active, 44.4% sold (CRITICAL)
- Bulk lots: 252 detected (HIGH priority)
- Treatment coverage: 100% (OK)
- Product subtype (sealed): 93.9% (OK)
- Report: `/Users/Cody/code_projects/wonder-scraper/docs/DATA_QUALITY_AUDIT_2025-12-30.md`

---

## Units of Work

### UOW-008-1: Write Seller Data Coverage Query
**Type:** data
**Estimate:** 1 hour
**Dependencies:** None

**Exact Action:**
Write SQL query to measure seller data population rate:
- Count total listings by (platform, listing_type)
- Count `seller_name IS NULL`, `seller_feedback_score IS NULL`, `seller_feedback_percent IS NULL`
- Calculate coverage percentage
- Save query to `tasks/queries/seller_coverage.sql`

**Acceptance Checks:**
- [ ] Query runs successfully on production DB (Neon)
- [ ] Returns breakdown by platform (ebay, blokpax) and listing_type (sold, active)
- [ ] Coverage percentage accurate (verified with manual COUNT on sample)
- [ ] Query executes in <5 seconds (indexed on platform, listing_type)

---

### UOW-008-2: Write Bulk Lot Detection Query
**Type:** data
**Estimate:** 1 hour
**Dependencies:** None

**Exact Action:**
Write SQL query to detect bulk lot listings via regex pattern matching:
- Pattern: `(?i)(3x|4x|5x|lot of|bundle|random|mixed|assorted|\d+\s*card\s*lot)`
- Exclude known product names (e.g., "Play Bundle", "Collector Booster Bundle")
- Group by pattern type, count occurrences
- Extract example titles for each pattern (LIMIT 3)
- Save query to `tasks/queries/bulk_lot_detection.sql`

**Acceptance Checks:**
- [ ] Query detects known bulk lots from manual review (e.g., "3X - Wonders... $0.65")
- [ ] Does NOT flag legitimate products (e.g., "Play Bundle", "Blaster Box")
- [ ] Returns count by pattern type and example titles
- [ ] Query executes in <10 seconds (full table scan on title field)

---

### UOW-008-3: Write Product Subtype Coverage Query
**Type:** data
**Estimate:** 0.5 hours
**Dependencies:** None

**Exact Action:**
Write SQL query to measure product_subtype population for sealed products:
- Join MarketPrice with Card on card_id
- Filter where Card.product_type IN ('Box', 'Pack', 'Bundle', 'Lot')
- Count total sealed listings
- Count `product_subtype IS NOT NULL`
- Calculate coverage percentage
- Group by product_type (Box, Pack, Bundle, Lot)
- Save query to `tasks/queries/subtype_coverage.sql`

**Acceptance Checks:**
- [ ] Query correctly joins MarketPrice and Card tables
- [ ] Returns coverage breakdown by product_type
- [ ] Coverage percentage matches expected (63/3327 for known data)
- [ ] Query executes in <5 seconds (indexed on card_id)

---

### UOW-008-4: Generate Audit Report
**Type:** docs
**Estimate:** 1 hour
**Dependencies:** UOW-008-1, UOW-008-2, UOW-008-3

**Exact Action:**
Run all queries, compile results into audit report markdown file:
- Execute each query against production database
- Copy results into report template (see above)
- Add findings and root cause hypotheses
- Prioritize recommendations (High/Medium/Low)
- Include examples of affected listings (titles, prices)
- Save report to `tasks/TASK-008-data-audit-report.md`

**Acceptance Checks:**
- [ ] Report includes all 5 sections (Summary, Seller Coverage, Bulk Lots, Subtype Coverage, Outliers, Recommendations)
- [ ] Numbers are accurate (verified against raw query results)
- [ ] Example titles provided for bulk lots and outliers
- [ ] Recommendations prioritized with reasoning
- [ ] Report reviewed by at least one other team member
- [ ] Backfill scope agreed (e.g., target 95% seller coverage, flag 73 bulk lots)

---

## Testing Plan
1. **Query validation:** Run each query on local dev database with known test data, verify results match manual count
2. **Production dry-run:** Run queries with READ-ONLY transaction on production, verify no errors
3. **Performance test:** Check query execution time on 5,737 row table, optimize if >10s
4. **Report review:** Share report with team, incorporate feedback on findings and recommendations

---

## Rollback Plan
No schema changes or data mutations in this task. Queries are read-only. Rollback not applicable.

---

## Documentation Required
- `/tasks/queries/seller_coverage.sql` - SQL query with comments
- `/tasks/queries/bulk_lot_detection.sql` - SQL query with pattern explanation
- `/tasks/queries/subtype_coverage.sql` - SQL query with join logic
- `/tasks/TASK-008-data-audit-report.md` - Audit results and recommendations

---

## Notes
- This task is blocking for TASK-009 (seller backfill) and TASK-010 (bulk lot detection).
- Audit results inform prioritization and scope for all subsequent data quality tasks.
- Report should be updated quarterly to track improvement over time.
