# Cards API

The Cards API provides access to card data, pricing information, sales history, and active listings.

## Data Sources

Card market data is aggregated from:
- **eBay** - Physical card sales and active listings
- **OpenSea** - NFT sales for digital collections (ETH pricing converted to USD)

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cards` | List all cards with market data |
| GET | `/cards/{id}` | Get a specific card |
| GET | `/cards/{id}/market` | Get latest market snapshot |
| GET | `/cards/{id}/history` | Get sales history |
| GET | `/cards/{id}/active` | Get active listings |
| GET | `/cards/{id}/pricing` | Get FMP breakdown by treatment |
| GET | `/cards/{id}/snapshots` | Get historical snapshots (for charts) |

---

## GET /cards

List all cards with latest market data.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip` | int | 0 | Offset for pagination |
| `limit` | int | 100 | Items per page (max 500) |
| `search` | string | - | Search by card name |
| `time_period` | string | `7d` | Time period: `24h`, `7d`, `30d`, `90d`, `all` |
| `product_type` | string | - | Filter by type: `Single`, `Box`, `Pack`, etc. |
| `include_total` | bool | false | Include total count (slower) |
| `slim` | bool | false | Return lightweight payload (~50% smaller) |

### Response (slim=false)

```json
[
  {
    "id": 42,
    "name": "Ember the Flame",
    "slug": "ember-the-flame",
    "set_name": "Genesis",
    "rarity_id": 3,
    "rarity_name": "Rare",
    "product_type": "Single",

    "floor_price": 12.50,
    "vwap": 14.25,
    "latest_price": 15.00,
    "lowest_ask": 13.99,
    "max_price": 45.00,
    "avg_price": 14.10,
    "fair_market_price": null,

    "volume": 23,
    "inventory": 8,

    "price_delta": 5.3,
    "floor_delta": 20.0,

    "last_treatment": "Classic Foil",
    "last_updated": "2024-01-15T10:30:00Z"
  }
]
```

### Response (slim=true)

Recommended for list views - ~50% smaller payload:

```json
[
  {
    "id": 42,
    "name": "Ember the Flame",
    "slug": "ember-the-flame",
    "set_name": "Genesis",
    "rarity_name": "Rare",
    "product_type": "Single",
    "floor_price": 12.50,
    "latest_price": 15.00,
    "lowest_ask": 13.99,
    "max_price": 45.00,
    "volume": 23,
    "inventory": 8,
    "price_delta": 5.3,
    "last_treatment": "Classic Foil"
  }
]
```

### Response (include_total=true)

```json
{
  "items": [...],
  "total": 150,
  "skip": 0,
  "limit": 100,
  "hasMore": true
}
```

### Example

```bash
# Get rare singles from the last 30 days
curl "https://api.wonderstrader.com/api/v1/cards?product_type=Single&time_period=30d&slim=true"
```

---

## GET /cards/{id}

Get detailed information for a specific card. Accepts numeric ID or URL slug.

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Card ID (numeric) or slug (e.g., `ember-the-flame`) |

### Response

```json
{
  "id": 42,
  "name": "Ember the Flame",
  "slug": "ember-the-flame",
  "set_name": "Genesis",
  "rarity_id": 3,
  "rarity_name": "Rare",
  "product_type": "Single",

  "floor_price": 12.50,
  "vwap": 14.25,
  "latest_price": 15.00,
  "lowest_ask": 13.99,
  "max_price": 45.00,
  "avg_price": 14.10,
  "fair_market_price": 13.80,

  "volume": 23,
  "inventory": 8,

  "price_delta": 5.3,
  "floor_delta": 20.0,

  "last_treatment": "Classic Foil",
  "last_updated": "2024-01-15T10:30:00Z"
}
```

### Price Fields Explained

| Field | Description |
|-------|-------------|
| `floor_price` | Average of 4 lowest sales (base treatment preferred) |
| `vwap` | Volume Weighted Average Price |
| `latest_price` | Most recent sale price |
| `lowest_ask` | Cheapest active listing |
| `max_price` | Highest confirmed sale |
| `fair_market_price` | Calculated FMP (detail page only) |
| `price_delta` | Last sale vs rolling average (%) |
| `floor_delta` | Last sale vs floor price (%) |

---

## GET /cards/{id}/history

Get sales history for a card.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Items per page (max 200) |
| `offset` | int | 0 | Offset for pagination |
| `paginated` | bool | false | Return paginated response with metadata |

### Response

```json
[
  {
    "id": 1234,
    "card_id": 42,
    "price": 15.00,
    "title": "WOTF Ember the Flame Classic Foil Genesis",
    "sold_date": "2024-01-15T08:22:00Z",
    "listing_type": "sold",
    "treatment": "Classic Foil",
    "bid_count": 3,
    "url": "https://www.ebay.com/itm/...",
    "image_url": "https://...",
    "seller_name": "CardShop123",
    "seller_feedback_score": 1250,
    "seller_feedback_percent": 99.8,
    "condition": "Near Mint",
    "shipping_cost": 4.50,
    "quantity": 1,
    "scraped_at": "2024-01-15T10:00:00Z"
  }
]
```

---

## GET /cards/{id}/active

Get active listings for a card.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Max items to return |

### Response

Same structure as `/history` but with `listing_type: "active"`.

---

## GET /cards/{id}/pricing

Get Fair Market Price (FMP) breakdown by treatment variant.

### Response

```json
{
  "card_id": 42,
  "card_name": "Ember the Flame",
  "product_type": "Single",
  "fair_market_price": 13.80,
  "floor_price": 12.50,
  "calculation_method": "formula",
  "breakdown": {
    "floor": 12.50,
    "vwap": 14.25,
    "median": 14.00,
    "lowest_ask": 13.99,
    "weight_floor": 0.4,
    "weight_vwap": 0.3,
    "weight_median": 0.2,
    "weight_ask": 0.1
  },
  "by_treatment": [
    {
      "treatment": "Classic Paper",
      "floor_price": 8.50,
      "fair_market_price": 9.20,
      "sales_count": 15,
      "last_sale": 9.00
    },
    {
      "treatment": "Classic Foil",
      "floor_price": 18.00,
      "fair_market_price": 21.50,
      "sales_count": 8,
      "last_sale": 22.00
    }
  ]
}
```

---

## GET /cards/{id}/snapshots

Get historical market snapshots for price charts.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | int | 90 | Number of days of history (max 365) |
| `limit` | int | 100 | Max snapshots to return (max 500) |

### Response

```json
[
  {
    "id": 5678,
    "card_id": 42,
    "min_price": 10.00,
    "max_price": 25.00,
    "avg_price": 14.50,
    "volume": 5,
    "lowest_ask": 12.99,
    "highest_bid": null,
    "inventory": 12,
    "timestamp": "2024-01-15T00:00:00Z"
  }
]
```

---

## GET /cards/{id}/market

Get the latest market snapshot for a card.

### Response

```json
{
  "id": 5678,
  "card_id": 42,
  "min_price": 10.00,
  "max_price": 25.00,
  "avg_price": 14.50,
  "volume": 5,
  "lowest_ask": 12.99,
  "highest_bid": null,
  "inventory": 12,
  "timestamp": "2024-01-15T00:00:00Z"
}
```

---

## Treatments

Card treatments (print variants):

| Treatment | Description |
|-----------|-------------|
| Classic Paper | Standard card |
| Classic Foil | Foil version |
| Gilded Paper | Gold-bordered standard |
| Gilded Foil | Gold-bordered foil |
| Artist Proof Paper | Artist proof standard |
| Artist Proof Foil | Artist proof foil |
