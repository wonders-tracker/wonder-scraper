# EPIC-002: Data Quality Improvements

**Status:** IN PROGRESS (Phase 1 Complete)
**Priority:** High
**Owner:** TBD
**Created:** 2025-12-18
**Target Sprint:** Q1 2025
**Phase 1 Completed:** 2025-12-30

---

## A. Goals & Context

### Product Goals
- Ensure marketplace data accuracy for reliable Fair Market Price (FMP) calculations
- Provide trustworthy seller reputation data for buyer decision-making
- Detect and flag data anomalies before they corrupt pricing algorithms
- Maintain data integrity for long-term market trend analysis

### Technical Goals
- Achieve 95%+ seller data population rate (currently ~70-80%)
- Eliminate bulk lot misattribution (estimated 50-100 listings affected)
- Create automated data quality monitoring with real-time alerting
- Establish data quality test suite to prevent regression
- Improve scraper edge case handling for treatments, subtypes, and quantities

### Constraints
- Cannot re-scrape historical eBay data with missing URLs (44% completeness is permanent)
- Must maintain backward compatibility with existing MarketPrice model
- Scraper rate limits: eBay (15 min), Blokpax (30 min)
- Database: Neon PostgreSQL with connection pooling limits

### Assumptions
- Seller data can be backfilled via eBay API for listings with external_id
- Bulk lot patterns are detectable via regex on title strings
- Data quality metrics can be computed efficiently via aggregation queries
- Treatment parsing edge cases are finite and documentable

### Missing Info / Questions
- **Q1:** What is the acceptable false positive rate for bulk lot detection?
  - **Context:** Too strict = flag legitimate multi-card sales; too loose = miss bulk lots
  - **Impact:** Affects FMP calculation accuracy
- **Q2:** Should we create a `DataQualityIssue` table for tracking anomalies over time?
  - **Context:** Would enable trend analysis and recurring issue detection
  - **Impact:** Requires schema migration and additional storage
- **Q3:** Do we need manual review workflow for flagged listings?
  - **Context:** Current `ListingReport` model exists but no admin UI
  - **Impact:** Scope creep if UI work required
- **Q4:** Should seller reputation score be computed or just raw metrics stored?
  - **Context:** Volume, avg price, reliability, positive feedback %
  - **Impact:** Affects analytics complexity

---

## B. Research Findings

### Current Data Issues (Quantified)

#### 1. Seller Data Gaps
**Severity:** Medium
**Prevalence:** Unknown (needs query)
- Many listings have `seller_name = None` despite eBay providing this data
- Seller feedback score/percent also missing
- **Root Cause:** Parser may not extract from new eBay HTML structure (`.s-card` format added 2024+)
- **Impact:** Cannot build seller reputation analytics, limits buyer trust features

#### 2. Bulk Lot Misattribution
**Severity:** High
**Prevalence:** ~50-100 listings (estimated from manual review)
- Listings like "3X - Wonders of the First Mixed Lot $0.65" incorrectly linked to single cards
- Creates artificial floor prices (e.g., $0.22 per card from $0.65 lot)
- **Root Cause:** Title parser detects "3X" as quantity but assigns full price to one card
- **Pattern Examples:**
  - `"3X - Wonders..."` → 3-card bundle sold as lot
  - `"LOT OF 5 COMMON CARDS"` → bulk commons
  - `"BUNDLE - 10 RANDOM WONDERS CARDS"` → mystery bundle
- **Impact:** Corrupts FMP for affected cards, misleading price signals

#### 3. Treatment Parsing Edge Cases
**Severity:** Low
**Prevalence:** <0.03% (10-15 listings out of 5,737 total)
- Most cases handled (99.97% coverage)
- Known issues:
  - "Alt Art" variants sometimes miss detection when not explicitly stated
  - "Proof/Sample" cards sometimes confused with "Promo"
  - Grading companies (PSA, BGS, TAG, CGC, SGC) have overlapping patterns
- **Impact:** Minor misclassification, doesn't affect price materially

#### 4. Product Subtype Population
**Severity:** Low
**Prevalence:** 63/3,327 active listings have product_subtype (1.9%)
- **Expected:** Only sealed products (Box, Pack, Bundle, Lot) should have subtype
- **Current:** 63 listings populated (likely correct subset)
- **Issue:** May be undercounting sealed subtypes due to title parsing
- **Impact:** Limited ability to segment sealed product pricing

#### 5. Variant Mixing (Card-Level Issue)
**Severity:** Medium
**Prevalence:** Unknown (Card 411 is one confirmed case)
- Card 411: $0.99 listings mixed with $44 listings (different sealed variants)
- **Root Cause:** Same card_id used for multiple sealed product variants
- **Example:** "Collector Booster Pack" vs "Play Booster Pack" both link to generic "Booster Pack" card
- **Impact:** Median price unreliable for cards with multiple product variants
- **Solution:** Requires card data normalization (out of scope for this epic, may need EPIC-003)

### Database Statistics (As of 2025-12-18)
- **Total listings:** 5,737 (3,327 active + 2,410 sold)
- **Total cards:** 355
- **Treatment coverage:** 99.97%
- **Seller name populated:** TBD (needs query in TASK-008)
- **Product subtype populated:** 63/3,327 (1.9%)
- **Data accuracy:** 100% (no invalid data)
- **Essential completeness:** 100% (all required fields present)
- **Full completeness:** ~44% (historical eBay URLs unrecoverable)

---

## C. Phase Plan

### PHASE 1: Assessment & Backfilling (1 Sprint - 1-2 weeks)
**Goal:** Quantify data gaps and backfill missing seller data
**In-Scope:**
- Data quality audit queries (seller coverage, bulk lot detection)
- Seller data backfill for listings with external_id
- Manual review of bulk lot patterns

**Out-of-Scope:**
- Automated bulk lot flagging (deferred to Phase 2)
- New data quality metrics table (deferred to Phase 3)

**Exit Criteria:**
- [x] Seller data population rate documented and >90%
- [x] Bulk lot prevalence quantified (252 listings detected)
- [x] Backfill script tested and deployed

**Status:** COMPLETED 2025-12-30
**Timeline:** 1 sprint (5-10 business days)

---

### PHASE 2: Scraper Improvements (1 Sprint - 1-2 weeks)
**Goal:** Fix scraper edge cases and add bulk lot detection
**In-Scope:**
- Improve seller data extraction for new eBay `.s-card` format
- Add bulk lot detection to title parser (`_is_bulk_lot()` function)
- Enhanced product subtype detection for sealed products
- Treatment parsing edge case fixes (Alt Art, Proof/Sample)

**Out-of-Scope:**
- Retroactive re-parsing of existing listings (backfill handled in Phase 1)
- Variant mixing fixes (requires card model changes, EPIC-003)

**Exit Criteria:**
- [ ] Seller extraction success rate >95% on new scrapes
- [ ] Bulk lots flagged with `quantity=-1` or new `is_bulk_lot` field
- [ ] Product subtype populated for 100% of sealed products
- [ ] Treatment parsing tested on 100+ edge cases

**Timeline:** 1 sprint (5-10 business days)

---

### PHASE 3: Testing Infrastructure (1 Sprint - 1 week)
**Goal:** Create automated data quality tests and monitoring
**In-Scope:**
- Data quality metrics dashboard (CLI tool or simple API)
- Automated pytest suite for scraper output validation
- Daily data quality check job (runs post-scrape)
- Alerting for anomalies (Discord webhook integration)

**Out-of-Scope:**
- Real-time frontend dashboard (frontend work out of scope)
- Historical data quality tracking table (defer to Phase 4)
- Manual review workflow UI (defer to future epic)

**Exit Criteria:**
- [ ] Data quality test suite covers: seller data, treatments, quantities, bulk lots, price outliers
- [ ] Daily quality check runs automatically after scraper cron jobs
- [ ] Discord alerts configured for: seller data <90%, bulk lot count >10, price outliers >5
- [ ] All tests passing on production data

**Timeline:** 1 sprint (3-7 business days)

---

### PHASE 4: Observability & Polish (Optional - 3-5 days)
**Goal:** Long-term data quality tracking and reporting
**In-Scope:**
- Historical data quality metrics table (`DataQualitySnapshot`)
- Weekly data quality report generation (similar to market reports)
- Data quality API endpoint for admin/monitoring dashboards

**Out-of-Scope:**
- Admin UI for manual review (requires frontend work)
- Automated correction of flagged issues (human review required)

**Exit Criteria:**
- [ ] Data quality snapshots stored daily for trend analysis
- [ ] Weekly report includes: seller coverage, bulk lot count, treatment accuracy, price outliers
- [ ] API endpoint returns latest metrics in JSON format

**Timeline:** 3-5 business days

---

## D. Epics & Tasks

### TASK-008: Data Quality Audit & Backfill Planning
**Priority:** P0 (Blocking)
**Estimate:** 2-4 hours
**Owner:** TBD

**Objective:** Quantify current data gaps and plan backfill strategy

**Acceptance Criteria:**
- [ ] SQL query to measure seller data population rate (by listing_type and platform)
- [ ] SQL query to detect bulk lot listings via title pattern matching
- [ ] SQL query to measure product_subtype coverage for sealed products
- [ ] Report generated with findings and recommendations

**Required Docs:**
- `/*** tasks/TASK-008-data-audit-report.md */`
  Document query results, prevalence of issues, backfill feasibility

**Dependencies:** None

**Units of Work:**
1. **UOW-008-1:** Write seller data coverage query (1h)
2. **UOW-008-2:** Write bulk lot detection query (1h)
3. **UOW-008-3:** Write product subtype coverage query (0.5h)
4. **UOW-008-4:** Generate audit report (1h)

---

### TASK-009: Seller Data Backfill Script
**Priority:** P0
**Estimate:** 3-5 hours
**Owner:** TBD

**Objective:** Backfill missing seller data for existing listings with external_id

**Acceptance Criteria:**
- [ ] Script fetches seller info from eBay API or HTML page scrape
- [ ] Updates existing MarketPrice records with seller_name, feedback_score, feedback_percent
- [ ] Handles rate limiting (max 10 requests/min to avoid eBay block)
- [ ] Dry-run mode to preview changes before commit
- [ ] Logs progress and errors to file

**Required Docs:**
- `/*** scripts/backfill_seller_data.py */`
  Docstring explaining usage, args, rate limits

**Dependencies:** TASK-008 (audit identifies scope)

**Units of Work:**
1. **UOW-009-1:** Extract seller info from eBay HTML (reuse existing parser) (1.5h)
2. **UOW-009-2:** Implement batch update logic with dry-run mode (1.5h)
3. **UOW-009-3:** Add rate limiting and error handling (1h)
4. **UOW-009-4:** Test on 50 listings, verify accuracy (1h)

---

### TASK-010: Bulk Lot Detection & Flagging
**Priority:** P1
**Estimate:** 4-6 hours
**Owner:** TBD

**Objective:** Detect bulk lot listings and flag them to exclude from FMP calculations

**Acceptance Criteria:**
- [ ] `_is_bulk_lot(title: str) -> bool` function added to `app/scraper/ebay.py`
- [ ] Detects patterns: "3X", "LOT", "BUNDLE", "RANDOM", "MIXED", "ASSORTED"
- [ ] Flagged listings use `quantity=-1` or new `is_bulk_lot: bool` field (discuss with team)
- [ ] Existing bulk lots backfilled with flag via migration script
- [ ] FMP service excludes bulk lots from calculations

**Required Docs:**
- `/*** app/scraper/ebay.py */`
  Docstring for `_is_bulk_lot()` with pattern examples

**Dependencies:** TASK-008 (audit identifies patterns)

**Units of Work:**
1. **UOW-010-1:** Implement `_is_bulk_lot()` with regex patterns (1.5h)
2. **UOW-010-2:** Add bulk lot flag to MarketPrice model (schema decision + migration) (1h)
3. **UOW-010-3:** Integrate flag into scraper pipeline (0.5h)
4. **UOW-010-4:** Backfill existing bulk lots via script (1h)
5. **UOW-010-5:** Update FMP service to exclude bulk lots (1h)
6. **UOW-010-6:** Test on 20 bulk lot examples (1h)

---

### TASK-011: Improved Seller Data Extraction
**Priority:** P1
**Estimate:** 3-4 hours
**Owner:** TBD

**Objective:** Fix seller data extraction for new eBay `.s-card` HTML format

**Acceptance Criteria:**
- [ ] `_extract_seller_info()` updated to handle `.s-card` format
- [ ] Extracts seller_name, feedback_score, feedback_percent
- [ ] Handles both old `.s-item` and new `.s-card` formats
- [ ] Unit tests for both HTML structures
- [ ] Tested on 100 recent listings, >95% extraction success

**Required Docs:**
- `/*** app/scraper/ebay.py */`
  Update docstring for `_extract_seller_info()` with format examples

**Dependencies:** None

**Units of Work:**
1. **UOW-011-1:** Analyze `.s-card` HTML structure from eBay (0.5h)
2. **UOW-011-2:** Update `_extract_seller_info()` with new selectors (1.5h)
3. **UOW-011-3:** Write unit tests for both formats (1h)
4. **UOW-011-4:** Test on production data, verify >95% success (1h)

---

### TASK-012: Enhanced Product Subtype Detection
**Priority:** P2
**Estimate:** 2-3 hours
**Owner:** TBD

**Objective:** Improve detection of sealed product subtypes from listing titles

**Acceptance Criteria:**
- [ ] `_detect_product_subtype()` expanded with more patterns
- [ ] Detects: Collector Booster Box, Play Bundle, Blaster Box, Serialized Advantage, Starter Set, Silver Pack, Case
- [ ] Unit tests for each subtype with 3+ title examples
- [ ] Coverage on sealed products >90%

**Required Docs:**
- `/*** app/scraper/ebay.py */`
  Update docstring for `_detect_product_subtype()` with examples

**Dependencies:** None

**Units of Work:**
1. **UOW-012-1:** Research sealed product naming conventions (0.5h)
2. **UOW-012-2:** Add missing patterns to `_detect_product_subtype()` (1h)
3. **UOW-012-3:** Write unit tests for each subtype (1h)
4. **UOW-012-4:** Backfill existing sealed listings via script (0.5h)

---

### TASK-013: Treatment Parsing Edge Case Fixes
**Priority:** P2
**Estimate:** 2-3 hours
**Owner:** TBD

**Objective:** Fix edge cases in treatment detection (Alt Art, Proof/Sample, grading overlaps)

**Acceptance Criteria:**
- [ ] Alt Art detection improved (check for A1-A8 numbering patterns)
- [ ] Proof/Sample vs Promo distinction clarified
- [ ] Grading company patterns de-duplicated (TAG vs STAG conflict)
- [ ] Unit tests for each edge case
- [ ] Coverage >99.99% (< 5 failures out of 5,737 listings)

**Required Docs:**
- `/*** app/scraper/ebay.py */`
  Update docstrings for `_detect_treatment()`, `_is_alt_art()`, `_detect_grading()`

**Dependencies:** None

**Units of Work:**
1. **UOW-013-1:** Fix Alt Art detection (add A1-A8 pattern) (0.5h)
2. **UOW-013-2:** Clarify Proof/Sample vs Promo logic (0.5h)
3. **UOW-013-3:** Fix TAG vs STAG grading conflict (0.5h)
4. **UOW-013-4:** Write unit tests for edge cases (1h)
5. **UOW-013-5:** Test on production data, verify <5 failures (0.5h)

---

### TASK-014: Data Quality Test Suite
**Priority:** P1
**Estimate:** 4-6 hours
**Owner:** TBD

**Objective:** Create automated pytest suite for data quality validation

**Acceptance Criteria:**
- [ ] Tests for: seller data presence, treatment validity, quantity sanity, price outliers, bulk lot detection
- [ ] Tests run on sample of production data (last 100 listings per platform)
- [ ] CI/CD integration (runs on PR merge)
- [ ] Test coverage >90% for scraper validation logic

**Required Docs:**
- `/*** tests/test_data_quality.py */`
  Test file with docstrings explaining each test case

**Dependencies:** TASK-010, TASK-011, TASK-013 (scraper improvements)

**Units of Work:**
1. **UOW-014-1:** Write test for seller data presence (1h)
2. **UOW-014-2:** Write test for treatment validity (known list) (1h)
3. **UOW-014-3:** Write test for quantity sanity (1-100 range, bulk flag) (1h)
4. **UOW-014-4:** Write test for price outliers (IQR method) (1.5h)
5. **UOW-014-5:** Write test for bulk lot pattern detection (0.5h)
6. **UOW-014-6:** Integrate with CI/CD (GitHub Actions or Railway) (1h)

---

### TASK-015: Daily Data Quality Check Job
**Priority:** P1
**Estimate:** 3-4 hours
**Owner:** TBD

**Objective:** Automated daily job to compute data quality metrics and alert on anomalies

**Acceptance Criteria:**
- [ ] Script computes: seller coverage %, bulk lot count, treatment coverage %, price outlier count
- [ ] Runs daily after scraper cron jobs (eBay 15min, Blokpax 30min)
- [ ] Sends Discord alert if: seller coverage <90%, bulk lot count >10, price outliers >5
- [ ] Logs results to file for historical tracking

**Required Docs:**
- `/*** scripts/daily_data_quality_check.py */`
  Docstring with metric definitions and alert thresholds

**Dependencies:** TASK-014 (test suite provides metric logic)

**Units of Work:**
1. **UOW-015-1:** Write metric calculation logic (reuse test code) (1.5h)
2. **UOW-015-2:** Add Discord webhook integration (reuse existing logger) (0.5h)
3. **UOW-015-3:** Configure cron job (APScheduler or Railway scheduler) (1h)
4. **UOW-015-4:** Test alert triggering with mock data (0.5h)

---

### TASK-016: Data Quality Metrics Dashboard (CLI)
**Priority:** P2 (Optional)
**Estimate:** 2-3 hours
**Owner:** TBD

**Objective:** CLI tool to view current data quality metrics on demand

**Acceptance Criteria:**
- [ ] Script `scripts/show_data_quality.py` displays: seller coverage, bulk lot count, treatment breakdown, top price outliers
- [ ] Supports `--platform` filter (ebay, blokpax, all)
- [ ] Supports `--days` filter (last N days of data)
- [ ] Outputs table or JSON format

**Required Docs:**
- `/*** scripts/show_data_quality.py */`
  Usage examples in docstring

**Dependencies:** TASK-014, TASK-015 (metric logic)

**Units of Work:**
1. **UOW-016-1:** Implement metric queries with filters (1h)
2. **UOW-016-2:** Add CLI arg parsing (argparse) (0.5h)
3. **UOW-016-3:** Format output as ASCII table or JSON (0.5h)
4. **UOW-016-4:** Test with various filter combinations (0.5h)

---

### TASK-017: Data Quality Snapshot Table (Optional - Phase 4)
**Priority:** P3
**Estimate:** 3-4 hours
**Owner:** TBD

**Objective:** Store historical data quality metrics for trend analysis

**Acceptance Criteria:**
- [ ] New `DataQualitySnapshot` model with fields: timestamp, platform, seller_coverage, bulk_lot_count, treatment_coverage, price_outlier_count
- [ ] Migration to create table
- [ ] Daily job inserts snapshot row after quality check
- [ ] API endpoint `/api/v1/admin/data-quality/history` returns last 30 days

**Required Docs:**
- `/*** app/models/quality.py */`
  SQLModel definition with field descriptions

**Dependencies:** TASK-015 (quality check job)

**Units of Work:**
1. **UOW-017-1:** Define `DataQualitySnapshot` model (0.5h)
2. **UOW-017-2:** Create Alembic migration (0.5h)
3. **UOW-017-3:** Update daily job to insert snapshot (0.5h)
4. **UOW-017-4:** Create API endpoint for history (1.5h)
5. **UOW-017-5:** Test with 7 days of mock data (0.5h)

---

### TASK-018: Weekly Data Quality Report (Optional - Phase 4)
**Priority:** P3
**Estimate:** 2-3 hours
**Owner:** TBD

**Objective:** Generate weekly report summarizing data quality trends

**Acceptance Criteria:**
- [ ] Script `scripts/generate_data_quality_report.py` creates markdown and txt reports
- [ ] Includes: week-over-week metric changes, top issues, recommendations
- [ ] Saved to `data/qualityReports/{date}-weekly.{txt|md}`
- [ ] Optionally posts to Discord (flag `--post-discord`)

**Required Docs:**
- `/*** scripts/generate_data_quality_report.py */`
  Usage and output format examples

**Dependencies:** TASK-017 (snapshot table for historical data)

**Units of Work:**
1. **UOW-018-1:** Query snapshot table for last 7 days (0.5h)
2. **UOW-018-2:** Calculate week-over-week deltas (0.5h)
3. **UOW-018-3:** Generate report text (reuse market report template) (1h)
4. **UOW-018-4:** Add Discord posting option (0.5h)

---

## E. Delivery & Risk Plan

### Sprint Mapping

#### Sprint 1: Assessment & Backfilling
**Theme:** Quantify and fix existing data gaps
**Phase/Epic:** Phase 1
**Must-Have UOWs:**
- UOW-008-1, UOW-008-2, UOW-008-3, UOW-008-4 (Audit)
- UOW-009-1, UOW-009-2, UOW-009-3, UOW-009-4 (Seller backfill)

**Nice-to-Have UOWs:**
- UOW-010-4 (Backfill bulk lot flags if schema ready)

**Demo Checkpoint:**
- Audit report showing seller coverage improved from X% to >90%
- X bulk lots identified and flagged

---

#### Sprint 2: Scraper Improvements
**Theme:** Fix scraper edge cases and prevent future issues
**Phase/Epic:** Phase 2
**Must-Have UOWs:**
- UOW-010-1, UOW-010-2, UOW-010-3, UOW-010-5 (Bulk lot detection)
- UOW-011-1, UOW-011-2, UOW-011-3 (Seller extraction)
- UOW-013-1, UOW-013-2, UOW-013-3, UOW-013-4 (Treatment fixes)

**Nice-to-Have UOWs:**
- UOW-012-1, UOW-012-2, UOW-012-3 (Product subtype expansion)

**Demo Checkpoint:**
- New scrapes show >95% seller data population
- Zero bulk lots incorrectly attributed to single cards

---

#### Sprint 3: Testing & Monitoring
**Theme:** Automated quality checks and alerting
**Phase/Epic:** Phase 3
**Must-Have UOWs:**
- UOW-014-1, UOW-014-2, UOW-014-3, UOW-014-4, UOW-014-5 (Test suite)
- UOW-015-1, UOW-015-2, UOW-015-3 (Daily check job)

**Nice-to-Have UOWs:**
- UOW-016-1, UOW-016-2, UOW-016-3 (CLI dashboard)
- UOW-014-6 (CI/CD integration if time permits)

**Demo Checkpoint:**
- Daily quality check running automatically
- Discord alert triggered by mock anomaly
- All pytest data quality tests passing

---

#### Sprint 4 (Optional): Observability
**Theme:** Long-term tracking and reporting
**Phase/Epic:** Phase 4
**Must-Have UOWs:**
- UOW-017-1, UOW-017-2, UOW-017-3 (Snapshot table)

**Nice-to-Have UOWs:**
- UOW-017-4, UOW-017-5 (API endpoint)
- UOW-018-1, UOW-018-2, UOW-018-3 (Weekly report)

**Demo Checkpoint:**
- 7-day quality trend visible in snapshot table
- Weekly report generated with insights

---

### Critical Path

```
TASK-008 (Audit)
  ↓
TASK-009 (Seller Backfill) ← Must complete before Sprint 2
  ↓
TASK-010 (Bulk Lot) + TASK-011 (Seller Extract) + TASK-013 (Treatment) ← Parallel in Sprint 2
  ↓
TASK-014 (Test Suite) ← Depends on scraper improvements
  ↓
TASK-015 (Daily Check) ← Depends on test logic
  ↓
TASK-017 (Snapshot Table) ← Optional Phase 4
  ↓
TASK-018 (Weekly Report) ← Optional Phase 4
```

**Bottleneck Risk:** TASK-010 (bulk lot detection) requires schema decision (quantity=-1 vs is_bulk_lot field). Block early for team alignment.

---

### Risks & Hidden Work

#### Architectural Risks
| Risk | Why it matters | Phase/Epic | Impact if ignored |
|------|----------------|------------|-------------------|
| **Bulk lot schema design:** Flag via quantity=-1 vs new field | quantity=-1 is a hack; new field requires migration | TASK-010 | High - affects FMP calculation logic, API responses |
| **Seller data size:** Adding 3 fields to 5,737 listings | Minimal storage impact (~500KB), but needs index on seller_name | TASK-009 | Low - minor query performance hit |
| **Discord rate limits:** Daily alerts may hit webhook rate limit | 30 msg/min limit, unlikely to hit with 1 alert/day | TASK-015 | Low - use exponential backoff |

#### Data Model Risks
| Risk | Why it matters | Phase/Epic | Impact if ignored |
|------|----------------|------------|-------------------|
| **Treatment enum explosion:** Adding Alt Art suffix doubles treatment count | 8 base treatments × 2 (with/without Alt Art) = 16 combinations | TASK-013 | Medium - complicates filtering, may need is_alt_art boolean |
| **Product subtype vs treatment:** Sealed products use "treatment" field for condition (Sealed/Open Box) | Confusing overload of "treatment" field | TASK-012 | Low - documented in code, but may confuse new devs |
| **External ID collisions:** eBay IDs may collide across platforms | Currently using platform field, but no composite unique constraint | TASK-009 | Low - add unique constraint in future migration |

#### External API/Integration Risks
| Risk | Why it matters | Phase/Epic | Impact if ignored |
|------|----------------|------------|-------------------|
| **eBay HTML structure changes:** Seller extraction depends on `.s-card` selectors | eBay changes format ~yearly | TASK-011 | High - extraction will break, needs monitoring |
| **Rate limiting on backfill:** Backfilling 1,000+ listings may trigger eBay IP block | Must rate limit to 10 req/min | TASK-009 | High - IP ban = scraper downtime |
| **Blokpax API stability:** Blokpax v2/v4 API has undocumented quirks | Not relevant for this epic (eBay focus) | N/A | N/A |

#### Migration Risks
| Risk | Why it matters | Phase/Epic | Impact if ignored |
|------|----------------|------------|-------------------|
| **Backfill script idempotency:** Re-running backfill should not duplicate data | Must use UPSERT logic | TASK-009 | High - duplicate records corrupt stats |
| **Bulk lot flag backfill:** Existing listings need retroactive flagging | Requires full table scan (5,737 rows) | TASK-010 | Medium - slow migration, run during low traffic |
| **Snapshot table size:** 1 row/day × 365 days = 365 rows/year | Negligible storage, but needs retention policy | TASK-017 | Low - cleanup after 1 year |

#### DevOps/CI/Monitoring Needs
| Risk | Why it matters | Phase/Epic | Impact if ignored |
|------|----------------|------------|-------------------|
| **CI/CD for data tests:** Tests must run on PR merge, not just locally | Prevents regression | TASK-014 | Medium - manual testing unreliable |
| **Cron job failures:** Daily quality check may fail silently | Needs dead man's switch or health check | TASK-015 | Medium - missed alerts = undetected issues |
| **Discord webhook downtime:** Alerts depend on Discord API availability | Need fallback (email, Slack) if critical | TASK-015 | Low - Discord uptime >99.9% |

#### "Invisible Work" Engineers Forget
| Work | Why needed | Phase/Epic | Estimate |
|------|------------|------------|----------|
| **Error handling for backfill:** Network failures, invalid HTML, missing fields | Backfill script must handle gracefully | TASK-009 | +1h |
| **Logging for quality checks:** Daily job needs structured logs for debugging | Helps diagnose why alerts triggered | TASK-015 | +0.5h |
| **Rollback plan for schema changes:** Bulk lot flag migration needs down migration | Must be reversible if issues found | TASK-010 | +0.5h |
| **Documentation updates:** README, CLAUDE.md need data quality section | Future devs need context | All tasks | +1h |
| **API versioning:** If adding DataQualitySnapshot endpoint, needs v1 prefix | Consistent with existing /api/v1/* | TASK-017 | +0.5h |

---

### Intentional Tech Debt Decisions

#### Defer to Future Epic
1. **Variant mixing fix (Card 411 issue):** Requires card data model normalization (separate cards for each sealed variant). Out of scope for data quality epic, track as EPIC-003.
2. **Admin UI for manual review:** `ListingReport` model exists but no UI. Defer to frontend-focused epic.
3. **Real-time frontend dashboard:** Data quality metrics available via API, but no React UI. Defer to Phase 4 or future epic.

#### Accept as Low Priority
1. **Historical URL completeness (44%):** Cannot re-scrape old eBay URLs. Accept as permanent limitation, document in data quality report.
2. **Treatment coverage <100%:** 99.97% is acceptable. Edge cases (< 5 listings) can be handled manually via ListingReport.
3. **Product subtype for singles:** Singles don't need subtype. Null is correct, not a gap.

#### Quick Wins Deprioritized
1. **Seller reputation score:** Computing weighted score (volume × feedback %) is useful but not critical. Store raw metrics, compute on-demand.
2. **Price outlier auto-correction:** Flagging outliers is enough. Auto-correcting requires manual review workflow (defer).
3. **Duplicate listing detection:** External_id deduplication exists. Cross-platform duplicates (eBay + Blokpax) are rare, defer.

---

### Recommended Sequencing

#### Week 1-2: Sprint 1 (Assessment & Backfilling)
- **Mon-Tue:** TASK-008 (Audit) - 4h
- **Wed-Fri:** TASK-009 (Seller Backfill) - 5h
- **Buffer:** 1 day for schema decision on bulk lot flag (team discussion)

#### Week 3-4: Sprint 2 (Scraper Improvements)
- **Mon-Tue:** TASK-011 (Seller Extract) - 4h
- **Wed:** TASK-010 (Bulk Lot Detection) - 6h
- **Thu:** TASK-013 (Treatment Fixes) - 3h
- **Fri:** TASK-012 (Product Subtype) - 3h (optional)

#### Week 5-6: Sprint 3 (Testing & Monitoring)
- **Mon-Tue:** TASK-014 (Test Suite) - 6h
- **Wed-Thu:** TASK-015 (Daily Check Job) - 4h
- **Fri:** TASK-016 (CLI Dashboard) - 3h (optional)

#### Week 7+ (Optional): Sprint 4 (Observability)
- **Mon:** TASK-017 (Snapshot Table) - 4h
- **Tue:** TASK-018 (Weekly Report) - 3h

**Total Effort:** 25-30 hours (3-4 sprints)

---

## F. Success Metrics

### Key Performance Indicators (KPIs)
- **Seller data population rate:** >95% (currently ~70-80%)
- **Bulk lot misattribution count:** <10 (currently ~50-100)
- **Treatment accuracy:** >99.99% (currently 99.97%)
- **Product subtype coverage (sealed):** >90% (currently 1.9%)
- **Daily quality check uptime:** >99% (automated)
- **Alert false positive rate:** <5% (accurate alerts only)

### Acceptance Tests
1. **Seller backfill test:** After TASK-009, query `SELECT COUNT(*) FROM marketprice WHERE seller_name IS NULL` returns <5% of total.
2. **Bulk lot test:** After TASK-010, query for bulk patterns returns 0 listings with normal quantity (1-100).
3. **Scraper regression test:** After TASK-011, scrape 100 new listings, >95% have seller_name populated.
4. **Quality alert test:** Manually insert 10 bulk lots, daily job triggers Discord alert within 5 minutes.
5. **Historical tracking test:** After TASK-017, query DataQualitySnapshot table returns 7+ days of metrics.

---

## G. Open Questions for Team Discussion

1. **Schema design for bulk lots:** Use quantity=-1 hack or add is_bulk_lot boolean field? (Recommend boolean for clarity)
2. **Alert threshold tuning:** Is seller_coverage <90% the right threshold, or too aggressive? (May need adjustment after Sprint 1)
3. **Manual review workflow:** Do we need admin UI for ListingReport, or is DB query sufficient? (Defer to future epic)
4. **Retention policy for snapshots:** Keep DataQualitySnapshot rows for 1 year, or indefinitely? (Recommend 1 year with archival)
5. **CI/CD integration:** Run data quality tests on every PR, or just daily on main branch? (Recommend PR to catch regressions early)

---

**Next Steps:**
1. Review epic with team, address open questions
2. Prioritize tasks (P0 → P3)
3. Assign owners and schedule Sprint 1
4. Create task files for TASK-008 through TASK-018 (detailed UOWs)
