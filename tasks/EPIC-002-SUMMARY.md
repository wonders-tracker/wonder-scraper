# EPIC-002: Data Quality Improvements - Summary

**Created:** 2025-12-18
**Status:** Ready for Review
**Total Effort:** 25-30 hours across 3-4 sprints

---

## Quick Overview

This epic addresses data quality issues discovered in the Wonder Scraper marketplace tracker:

### Problems Identified
1. **Seller Data Gaps:** 20-30% of listings missing seller information
2. **Bulk Lot Misattribution:** ~50-100 listings incorrectly attributed to single cards, corrupting FMP
3. **Treatment Parsing Edge Cases:** <0.03% edge cases (Alt Art, Proof/Sample)
4. **Product Subtype Coverage:** Only 1.9% of sealed products have subtype populated
5. **Variant Mixing:** Different sealed variants share card_id (e.g., Card 411)

### Impact
- **FMP Accuracy:** Bulk lots create $0.22 floor prices instead of $44 median
- **Analytics Gaps:** Cannot build seller reputation features
- **Data Consistency:** New scrapes differ from historical data

---

## Files Created

### Epic Document
- **EPIC-002-data-quality-improvements.md** (12,000+ words)
  - Complete phase breakdown (4 phases)
  - 11 detailed tasks with acceptance criteria
  - 40+ units of work (1-4 hour chunks)
  - Risk assessment and mitigation strategies
  - Sprint mapping with critical path analysis

### Task Files (Detailed)
1. **TASK-008-data-quality-audit.md** - Data audit queries and baseline metrics
2. **TASK-009-seller-data-backfill.md** - Backfill script for missing seller info
3. **TASK-010-bulk-lot-detection.md** - Detect and flag bulk lots to exclude from FMP

### Remaining Tasks (In Epic, Not Yet Separate Files)
4. TASK-011: Improved Seller Data Extraction (fix `.s-card` HTML parsing)
5. TASK-012: Enhanced Product Subtype Detection
6. TASK-013: Treatment Parsing Edge Case Fixes
7. TASK-014: Data Quality Test Suite (pytest)
8. TASK-015: Daily Data Quality Check Job
9. TASK-016: Data Quality Metrics Dashboard (CLI)
10. TASK-017: Data Quality Snapshot Table (optional Phase 4)
11. TASK-018: Weekly Data Quality Report (optional Phase 4)

---

## Phase Breakdown

### Phase 1: Assessment & Backfilling (1-2 weeks)
**Goal:** Quantify gaps and backfill seller data
- TASK-008: Audit (2-4h)
- TASK-009: Seller backfill (3-5h)
- **Deliverable:** Seller coverage >90%

### Phase 2: Scraper Improvements (1-2 weeks)
**Goal:** Fix edge cases and add bulk lot detection
- TASK-010: Bulk lot detection (4-6h)
- TASK-011: Seller extraction (3-4h)
- TASK-012: Product subtype (2-3h)
- TASK-013: Treatment fixes (2-3h)
- **Deliverable:** New scrapes >95% accurate

### Phase 3: Testing Infrastructure (1 week)
**Goal:** Automated monitoring and alerts
- TASK-014: Test suite (4-6h)
- TASK-015: Daily check job (3-4h)
- TASK-016: CLI dashboard (2-3h optional)
- **Deliverable:** Daily quality checks with Discord alerts

### Phase 4: Observability (Optional 3-5 days)
**Goal:** Long-term tracking
- TASK-017: Snapshot table (3-4h)
- TASK-018: Weekly reports (2-3h)
- **Deliverable:** Historical quality trends

---

## Key Decisions Needed

### 1. Bulk Lot Flagging Strategy
**Question:** Use `quantity=-1` hack or add `is_bulk_lot: bool` field?

**Recommendation:** Add `is_bulk_lot` field for semantic clarity
- **Pros:** Explicit, queryable, no quantity field overload
- **Cons:** Requires schema migration
- **Migration Time:** <1 minute (5,737 rows)

### 2. Alert Thresholds
**Question:** What thresholds trigger Discord alerts?

**Current Proposal:**
- Seller coverage <90%
- Bulk lot count >10 new/week
- Price outliers >5/day
- Treatment errors >5/day

**Recommendation:** Start conservative, adjust after Sprint 3

### 3. Manual Review Workflow
**Question:** Do we need admin UI for flagged listings?

**Recommendation:** Defer to future epic (frontend work)
- For now: Use SQL queries and `ListingReport` table
- Admin UI can be added in Phase 4 or separate epic

### 4. Snapshot Retention Policy
**Question:** Keep `DataQualitySnapshot` rows for how long?

**Recommendation:** 1 year with archival
- Daily snapshots = 365 rows/year (~50KB)
- Archive to CSV after 1 year for historical analysis

### 5. CI/CD Integration
**Question:** Run data quality tests on every PR or just daily?

**Recommendation:** Every PR to catch regressions early
- Scraper changes should trigger test suite
- Prevents deploying code that breaks seller extraction

---

## Critical Path

```
TASK-008 (Audit) [BLOCKING]
  ↓
TASK-009 (Seller Backfill)
  ↓
┌─────────────────────────────────────┐
│ Parallel Sprint 2:                  │
│ - TASK-010 (Bulk Lot)               │
│ - TASK-011 (Seller Extract)         │
│ - TASK-013 (Treatment)              │
│ - TASK-012 (Subtype) [optional]     │
└─────────────────────────────────────┘
  ↓
TASK-014 (Test Suite)
  ↓
TASK-015 (Daily Check)
  ↓
┌─────────────────────────────────────┐
│ Optional Phase 4:                   │
│ - TASK-017 (Snapshot Table)         │
│ - TASK-018 (Weekly Report)          │
└─────────────────────────────────────┘
```

**Bottleneck:** TASK-010 requires schema decision - block for team alignment before Sprint 2

---

## Success Metrics

### Before (Current State - from TASK-008 audit)
- Seller coverage: ~70-80%
- Bulk lot count: ~50-100 (corrupting FMP)
- Treatment accuracy: 99.97%
- Product subtype: 1.9%
- No automated monitoring

### After (Target State - post EPIC-002)
- Seller coverage: >95%
- Bulk lot count: 0 affecting FMP (flagged and excluded)
- Treatment accuracy: >99.99%
- Product subtype: >90% for sealed products
- Daily quality checks with Discord alerts
- Weekly quality reports

### KPIs to Track
1. **Seller data population rate** (weekly)
2. **Bulk lot detection rate** (false positive/negative)
3. **FMP accuracy improvement** (compare before/after excluding bulk lots)
4. **Alert false positive rate** (<5%)
5. **Test suite coverage** (>90% for scraper validation)

---

## Risks & Mitigations

### High-Risk Items
1. **eBay HTML structure changes** → Scraper breaks
   - **Mitigation:** Daily quality checks alert within 24h, manual fix deployed
2. **Bulk lot schema decision delayed** → Blocks Sprint 2
   - **Mitigation:** Schedule team sync week 1, decide before Sprint 2 start
3. **Backfill triggers eBay rate limit** → IP ban
   - **Mitigation:** Rate limit to 10 req/min, run during low traffic hours

### Medium-Risk Items
1. **False positive bulk lot detection** → Legitimate sales excluded from FMP
   - **Mitigation:** Manual review of first 50 flagged listings, adjust patterns
2. **CI/CD test suite slows PR merges** → Developer friction
   - **Mitigation:** Optimize tests to run <30s, only sample production data
3. **Discord webhook downtime** → Missed alerts
   - **Mitigation:** Fallback to email or Slack if critical

---

## Open Questions for Team

1. ✅ **RESOLVED:** Schema design for bulk lots → Use `is_bulk_lot: bool` field
2. ⏳ **PENDING:** Alert threshold tuning → Adjust after Sprint 1 data
3. ⏳ **PENDING:** Manual review workflow → Defer to future epic
4. ⏳ **PENDING:** Snapshot retention policy → 1 year recommended
5. ✅ **RESOLVED:** CI/CD integration → Run tests on every PR

---

## Next Steps

### Week 1 (Immediate)
1. **Team review** of epic document
   - Address open questions
   - Confirm bulk lot schema decision (`is_bulk_lot` field)
   - Prioritize tasks (confirm P0-P3 labels)
2. **Assign owners** for Sprint 1 tasks
   - TASK-008: [Owner TBD]
   - TASK-009: [Owner TBD]
3. **Schedule Sprint 1** kickoff (Week 1-2)

### Week 2-3 (Sprint 1)
1. Execute TASK-008 (Audit)
2. Execute TASK-009 (Seller Backfill)
3. Create detailed task files for TASK-011 through TASK-018

### Week 4-5 (Sprint 2)
1. Execute scraper improvement tasks (TASK-010, TASK-011, TASK-013)
2. Optional: TASK-012 (Product subtype)

### Week 6-7 (Sprint 3)
1. Execute testing infrastructure tasks (TASK-014, TASK-015)
2. Optional: TASK-016 (CLI dashboard)

### Week 8+ (Optional Sprint 4)
1. Execute observability tasks (TASK-017, TASK-018)

---

## Resources

### Documentation
- Epic: `/tasks/EPIC-002-data-quality-improvements.md`
- Task files: `/tasks/TASK-008-*.md`, `/tasks/TASK-009-*.md`, `/tasks/TASK-010-*.md`
- Queries: `/tasks/queries/` (to be created in TASK-008)

### Codebase References
- Scraper: `/app/scraper/ebay.py` (seller extraction, treatment detection)
- Models: `/app/models/market.py` (MarketPrice model)
- FMP Service: `/saas/services/pricing.py` (SaaS), `/app/services/pricing.py` (OSS stub)

### External References
- eBay HTML structure: `.s-card` format (2024+)
- Neon PostgreSQL: Connection pooling, migration best practices
- Discord webhooks: Rate limits (30 msg/min)

---

## Conclusion

This epic provides a **systematic approach** to improving data quality across the Wonder Scraper platform. By addressing seller data gaps, bulk lot misattribution, and scraper edge cases, we ensure:

- **Accurate FMP calculations** (no more $0.22 floor prices from bulk lots)
- **Complete seller analytics** (>95% coverage for reputation features)
- **Reliable monitoring** (daily checks with Discord alerts)
- **Future-proof infrastructure** (test suite prevents regression)

**Total Effort:** 25-30 hours (achievable in 3-4 sprints)
**Risk Level:** Low-Medium (well-scoped, incremental changes)
**Business Impact:** High (FMP accuracy is critical for user trust)

Ready to proceed with Sprint 1!
