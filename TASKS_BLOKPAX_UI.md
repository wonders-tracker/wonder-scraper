# Blokpax UI Integration Epic

## Overview
Integrate Blokpax marketplace data seamlessly into existing WondersTracker UI - same table, same navigation, platform-aware detail pages.

## Phases

### Phase 1: Backend API Foundation (Sprint 1)
Extend `/api/v1/cards` to support multi-platform querying

### Phase 2: Frontend Dashboard Integration (Sprint 2)
Add platform filter, display Blokpax assets in main table

### Phase 3: Card Detail Page Enhancement (Sprint 3)
Blokpax-specific widgets on detail page

### Phase 4: Polish & Observability
Error handling, loading states, documentation

---

## Epics & Tasks

### EPIC-1: Backend Platform Parameter Support
**Objective**: Modify `/api/v1/cards` endpoint to accept `platform` parameter

| Task | Description | Status |
|------|-------------|--------|
| T1.1 | Add `platform` query param to cards endpoint | pending |
| T1.2 | Implement eBay query path (wrap existing logic) | pending |
| T1.3 | Add Blokpax query path stub | pending |
| T1.4 | Implement `platform=all` mixed results | pending |

**Done-When**:
- `GET /api/v1/cards?platform=blokpax` returns Blokpax assets
- `GET /api/v1/cards?platform=ebay` returns existing behavior
- `GET /api/v1/cards?platform=all` returns mixed results

---

### EPIC-2: Blokpax Data Mapping Service
**Objective**: Transform BlokpaxAssetDB into CardOut format

| Task | Description | Status |
|------|-------------|--------|
| T2.1 | Create `/app/services/blokpax_mapper.py` | pending |
| T2.2 | Map basic fields (name, floor_price_usd → latest_price) | pending |
| T2.3 | Calculate volume_30d from BlokpaxSale count | pending |
| T2.4 | Include BPX price in response | pending |
| T2.5 | Handle missing/null data gracefully | pending |

**Field Mapping**:
```
BlokpaxAssetDB.name          → Card.name
BlokpaxAssetDB.floor_price_usd → Card.latest_price, Card.lowest_ask
BlokpaxStorefront.listed_count → Card.inventory
COUNT(BlokpaxSale 30d)       → Card.volume_30d
"Blokpax"                    → Card.product_type
"blokpax"                    → Card.platform (new field)
```

---

### EPIC-3: Frontend Platform Filter UI
**Objective**: Add platform dropdown to dashboard header

| Task | Description | Status |
|------|-------------|--------|
| T3.1 | Add `platform` state to index.tsx | pending |
| T3.2 | Add platform dropdown component | pending |
| T3.3 | Update useQuery to include platform in queryKey | pending |
| T3.4 | Pass platform param to API call | pending |

**UI Location**: After product type dropdown (line ~465 in index.tsx)

```tsx
<select value={platform} onChange={e => setPlatform(e.target.value)}>
  <option value="all">All Platforms</option>
  <option value="ebay">eBay</option>
  <option value="blokpax">Blokpax</option>
</select>
```

---

### EPIC-4: Table Display for Blokpax Assets
**Objective**: Render Blokpax assets with platform badge

| Task | Description | Status |
|------|-------------|--------|
| T4.1 | Add BPX badge to name column | pending |
| T4.2 | Add BPX price tooltip to price column | pending |
| T4.3 | Test mixed table rendering | pending |

**Badge Design**:
```tsx
{row.original.platform === 'blokpax' && (
  <span className="text-[8px] bg-purple-900/20 text-purple-400 border border-purple-800 px-1 py-0.5 rounded">
    BPX
  </span>
)}
```

---

### EPIC-5: Card Detail Page Platform Detection
**Objective**: Auto-detect Blokpax vs eBay asset on detail page

| Task | Description | Status |
|------|-------------|--------|
| T5.1 | Add isBlokpax detection logic | pending |
| T5.2 | Stub conditional rendering blocks | pending |

```tsx
const isBlokpax = useMemo(() => card?.platform === 'blokpax', [card])

{isBlokpax ? <BlokpaxDetailWidgets /> : <EbayDetailWidgets />}
```

---

### EPIC-6: Blokpax Detail Widgets
**Objective**: Build Blokpax-specific UI components

| Task | Description | Status |
|------|-------------|--------|
| T6.1 | Create BlokpaxPriceCard (BPX/USD toggle) | pending |
| T6.2 | Create RedemptionProgressBar | pending |
| T6.3 | Create BlokpaxListingsFeed | pending |
| T6.4 | Add external link to Blokpax marketplace | pending |
| T6.5 | Fetch and render price history chart | pending |

**Components**:
- `<BlokpaxPriceCard bpxPrice={} usdPrice={} />` - toggle between currencies
- `<RedemptionProgressBar redeemed={1368} total={3393} />` - for collector boxes
- `<BlokpaxListingsFeed storefrontSlug={} />` - recent sales/listings

---

### EPIC-7: Polish & Observability
**Objective**: Production-ready error handling and documentation

| Task | Description | Status |
|------|-------------|--------|
| T7.1 | Add error boundaries for Blokpax components | pending |
| T7.2 | Add loading skeletons | pending |
| T7.3 | Add BPX tooltip ("BPX is Blokpax marketplace token") | pending |
| T7.4 | Update API documentation | pending |

---

## Critical Path

```
T1.1-1.3 (endpoint) ──┬──> T3.1-3.4 (frontend filter)
                      │
T2.1-2.5 (mapper) ────┴──> T4.1-4.3 (table display)
                                    │
                                    v
                           T5.1-5.2 (detection)
                                    │
                                    v
                           T6.1-6.5 (widgets)
                                    │
                                    v
                           T7.1-7.4 (polish)
```

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| CardOut schema changes break frontend | High | Use optional fields, backward compatible |
| BPX exchange rate stale | High | Add "last updated" warning, refresh frequently |
| Mixed sort order confusing | Medium | Normalize date fields in mapper |
| Blokpax API slow | Medium | Aggressive caching (5-15 min TTL) |

---

## Questions to Resolve

1. **Schema Change**: Add `platform` field to Card model, or virtual mapping only?
   - **Decision**: Virtual mapping for V1 (no migration needed)

2. **Volume Calculation**: Use BlokpaxSale count or storefront stats?
   - **Decision**: COUNT(BlokpaxSale) for consistency

3. **Product Type vs Platform**: Separate filter or combined?
   - **Decision**: Separate platform filter for clarity

---

## Files to Modify

### Backend
- `/app/api/cards.py` - Add platform parameter
- `/app/services/blokpax_mapper.py` (new) - Mapping service
- `/app/models/card.py` - May need platform field (TBD)

### Frontend
- `/frontend/app/routes/index.tsx` - Platform filter, table display
- `/frontend/app/routes/cards.$cardId.tsx` - Platform detection, conditional widgets
- `/frontend/app/components/blokpax/` (new dir) - Blokpax-specific components
