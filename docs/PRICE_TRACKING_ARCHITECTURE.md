# Price Tracking Architecture

## Overview
Comprehensive price tracking system for all product types (Cards, Packs, Lots, Boxes, Collectibles/NFTs) with support for multiple time periods and advanced metrics.

## Product Types
- **Single**: Individual cards (default)
- **Box**: Booster boxes, collector boxes, cases
- **Pack**: Individual booster packs, starter packs
- **Lot**: Card lots, bundles, collections, bulk lots
- **Proof**: Character proofs, sample cards, prototypes
- **Collectible**: NFTs and digital collectibles (future)

## Time Periods Supported
- **1d**: 1 day (24 hours)
- **3d**: 3 days (72 hours)
- **7d**: 7 days (1 week)
- **14d**: 14 days (2 weeks)
- **30d**: 30 days (1 month)
- **90d**: 90 days (3 months)
- **all**: All time

## Price Metrics

### 1. VWAP (Volume Weighted Average Price)
**Current**: Simple average of sold prices
**Improved**: True volume-weighted average
```sql
SELECT SUM(price * quantity) / SUM(quantity) as vwap
FROM marketprice
WHERE listing_type = 'sold' AND sold_date >= :cutoff
```
**Note**: Currently using simple AVG since quantity isn't tracked per sale

### 2. EMA (Exponential Moving Average)
**Definition**: Time-weighted average giving more weight to recent prices
**Formula**: EMA = Price(t) × k + EMA(y) × (1 - k)
**Smoothing Factor**: k = 2 / (N + 1)
**Periods**: 7-day, 14-day, 30-day EMAs

### 3. Floor Price
**By Rarity**: Minimum price for each rarity level
**By Treatment**: Minimum price for each treatment type
**Combined**: Minimum price for rarity + treatment combination

### 4. Bid/Ask Spread
**Bid**: Highest active auction bid (from MarketPrice.highest_bid equivalent)
**Ask**: Lowest active listing price (MarketSnapshot.lowest_ask)
**Spread**: (Ask - Bid) / Ask × 100%

### 5. Price-to-Sale Ratio
**Definition**: Current asking price / Average sold price
**Formula**: lowest_ask / vwap
**Interpretation**:
- < 1.0: Good deal (below average)
- = 1.0: Fair price
- > 1.0: Premium price

### 6. Price Delta (Fixed)
**Current Issue**: Uses snapshot comparison (unreliable)
**Fixed Approach**: Compare actual sold prices at period boundaries
```python
# Get price at start of period
start_price = first sold price before cutoff
# Get price at end of period
end_price = last sold price in period
# Calculate delta
delta = ((end_price - start_price) / start_price) * 100
```

## Database Schema

### Existing Tables (No Changes Needed)

**Card**
- Already has `product_type` field
- Already has `rarity_id` for floor tracking

**MarketPrice**
- Already has `treatment` field for floor tracking
- Already has `sold_date` for time-series
- Already has `listing_type` for bid/ask filtering

**MarketSnapshot**
- Already has `lowest_ask`, `highest_bid` for bid/ask
- Already has `timestamp` for time-series

### New Fields (Optional Enhancements)

**MarketPrice** (consider adding):
- `quantity` (INTEGER): Number of items in sale (for true VWAP)
- `sale_type` (VARCHAR): 'auction', 'buy_it_now', 'best_offer'

**MarketSnapshot** (consider adding):
- `vwap` (FLOAT): Pre-calculated VWAP for period
- `ema_7d`, `ema_14d`, `ema_30d` (FLOAT): Pre-calculated EMAs
- `price_delta_1d`, `price_delta_7d`, `price_delta_30d` (FLOAT): Pre-calculated deltas

## API Endpoints

### Product-Level Endpoints

#### GET /api/v1/cards
**Enhancement**: Add time period query parameter
```
?time_period=1d|3d|7d|14d|30d|90d|all
&product_type=Single|Box|Pack|Lot|Proof
```

#### GET /api/v1/cards/{id}/market
**Current**: Returns snapshot + vwap
**Enhancement**: Add all calculated metrics
```json
{
  "min_price": 10.00,
  "max_price": 50.00,
  "avg_price": 25.00,
  "vwap": 26.50,
  "ema_7d": 27.00,
  "ema_14d": 26.75,
  "ema_30d": 26.25,
  "volume": 150,
  "lowest_ask": 28.00,
  "highest_bid": 24.00,
  "bid_ask_spread": 14.29,
  "price_to_sale": 1.06,
  "price_delta_1d": 2.5,
  "price_delta_7d": 5.2,
  "price_delta_30d": 8.7,
  "timestamp": "2025-01-01T00:00:00Z"
}
```

### New Aggregated Endpoints

#### GET /api/v1/market/floor
**Purpose**: Get floor prices by rarity and treatment
**Parameters**:
- `?product_type=Single|Box|Pack|Lot|Proof`
- `?time_period=1d|3d|7d|14d|30d|90d|all`

**Response**:
```json
{
  "by_rarity": {
    "Common": {"floor": 1.00, "count": 50},
    "Rare": {"floor": 5.00, "count": 30},
    "Legendary": {"floor": 25.00, "count": 10}
  },
  "by_treatment": {
    "Classic Paper": {"floor": 2.00, "count": 80},
    "Classic Foil": {"floor": 8.00, "count": 40},
    "OCM Serialized": {"floor": 50.00, "count": 5}
  },
  "by_combination": {
    "Legendary_OCM Serialized": {"floor": 150.00, "count": 2},
    "Rare_Classic Foil": {"floor": 12.00, "count": 15}
  }
}
```

#### GET /api/v1/market/time-series
**Purpose**: Get aggregated market metrics over time
**Parameters**:
- `?card_id=123` (optional, for single card)
- `?product_type=Single` (optional, for product type)
- `?interval=1d|1w|1m` (data point interval)
- `?period=7d|30d|90d|1y` (total time range)

**Response**:
```json
{
  "interval": "1d",
  "period": "30d",
  "data": [
    {
      "date": "2025-01-01",
      "vwap": 25.50,
      "ema_7d": 26.00,
      "volume": 15,
      "floor": 20.00,
      "price_delta": 2.5
    },
    // ... more data points
  ]
}
```

#### GET /api/v1/market/bid-ask
**Purpose**: Current bid/ask spreads
**Parameters**:
- `?product_type=Single`
- `?limit=50`

**Response**:
```json
{
  "cards": [
    {
      "card_id": 123,
      "name": "Card Name",
      "lowest_ask": 28.00,
      "highest_bid": 24.00,
      "spread_percent": 14.29,
      "spread_amount": 4.00,
      "vwap": 26.50,
      "price_to_sale": 1.06
    }
  ]
}
```

## Service Layer

### PriceCalculationService
**Location**: `app/services/price_calculator.py`

**Methods**:
- `calculate_vwap(card_id, period)` → float
- `calculate_ema(card_id, period, window)` → float
- `calculate_floor_by_rarity(rarity_id, period)` → float
- `calculate_floor_by_treatment(treatment, period)` → float
- `calculate_price_delta(card_id, period)` → float
- `calculate_bid_ask_spread(card_id)` → dict
- `calculate_price_to_sale(card_id)` → float
- `get_time_series(card_id, interval, period)` → List[dict]

### Benefits
- Centralized calculation logic
- Reusable across endpoints
- Easier testing
- Consistent formulas

## Migration Plan

### Phase 1: Service Layer (No DB Changes)
1. Create `app/services/price_calculator.py`
2. Implement all calculation methods
3. Unit tests for calculations

### Phase 2: API Enhancement
1. Update existing endpoints to use service
2. Add new aggregated endpoints
3. Add time period support (1d, 3d, 14d)

### Phase 3: Database Optimization (Optional)
1. Add `quantity` field to MarketPrice
2. Add pre-calculated EMA fields to MarketSnapshot
3. Create materialized view for floor prices
4. Add database-level time-series optimization

### Phase 4: Frontend Integration
1. Update charts to show EMA overlays
2. Add floor price indicators
3. Add bid/ask spread visualization
4. Add price-to-sale indicators

## Performance Considerations

### Caching Strategy
- Cache floor prices: 5 minutes
- Cache VWAP/EMA: 1 minute
- Cache time-series: 10 minutes
- Invalidate on new MarketPrice insert

### Query Optimization
- Use indexed `sold_date` for time filtering
- Use indexed `card_id` for filtering
- Pre-calculate EMAs in background job
- Use PostgreSQL window functions for time-series

### Background Jobs
- Calculate and cache floor prices every 5 minutes
- Update EMA calculations every 1 minute
- Generate time-series snapshots every hour

## Implementation Priority

### High Priority (Immediate)
1. ✅ Fix price delta calculation
2. ✅ Add 1d, 3d, 14d time period support
3. ✅ Implement EMA calculation
4. ✅ Create price calculation service

### Medium Priority (Next Sprint)
5. Add floor price endpoints
6. Add bid/ask spread endpoints
7. Add price-to-sale calculation
8. Add time-series endpoint

### Low Priority (Future)
9. Add quantity tracking for true VWAP
10. Add materialized views for performance
11. Add WebSocket support for real-time updates
12. Add NFT/collectible support

## Testing Requirements

### Unit Tests
- Each calculation method
- Edge cases (no data, single data point)
- Different time periods

### Integration Tests
- API endpoint responses
- Database query performance
- Cache invalidation

### Load Tests
- Time-series queries under load
- Concurrent calculation requests
- Cache hit/miss ratios
