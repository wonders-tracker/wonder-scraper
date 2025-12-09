# Market API

The Market API provides aggregate market data, recent activity, treatment pricing, and listing report functionality.

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/market/overview` | Market overview with all cards |
| GET | `/market/activity` | Recent sales across all cards |
| GET | `/market/treatments` | Price floors by treatment |
| POST | `/market/reports` | Submit a listing report |
| GET | `/market/reports` | Get listing reports (admin) |

---

## GET /market/overview

Get robust market overview statistics with temporal data for all cards.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `time_period` | string | `30d` | Period: `1h`, `24h`, `7d`, `30d`, `90d`, `all` |

### Response

```json
[
  {
    "id": 42,
    "slug": "ember-the-flame",
    "name": "Ember the Flame",
    "set_name": "Genesis",
    "rarity_id": 3,
    "latest_price": 15.00,
    "avg_price": 14.10,
    "vwap": 14.25,
    "floor_price": 12.50,
    "volume_period": 23,
    "volume_change": 0,
    "price_delta_period": 5.3,
    "deal_rating": -2.5,
    "market_cap": 345.00
  }
]
```

### Field Descriptions

| Field | Description |
|-------|-------------|
| `latest_price` | Most recent sale price |
| `avg_price` | Average from latest snapshot |
| `vwap` | Volume-weighted average price |
| `floor_price` | Avg of 4 lowest sales |
| `volume_period` | Number of sales in time period |
| `price_delta_period` | Price change % (last sale vs floor) |
| `deal_rating` | Deal score (last sale vs VWAP) |
| `market_cap` | latest_price × volume_period |

### Example

```bash
# Get 7-day market overview
curl "https://api.wonderstrader.com/api/v1/market/overview?time_period=7d"
```

---

## GET /market/activity

Get recent market activity (sales) across all cards.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 20 | Max items to return |

### Response

```json
[
  {
    "card_id": 42,
    "card_name": "Ember the Flame",
    "price": 15.00,
    "date": "2024-01-15T08:22:00Z",
    "treatment": "Classic Foil",
    "platform": "ebay"
  }
]
```

### Example

```bash
# Get last 50 sales
curl "https://api.wonderstrader.com/api/v1/market/activity?limit=50"
```

---

## GET /market/treatments

Get price floors by treatment variant.

### Response

```json
[
  {
    "name": "Classic Paper",
    "min_price": 0.99,
    "count": 1250
  },
  {
    "name": "Classic Foil",
    "min_price": 4.99,
    "count": 890
  },
  {
    "name": "Gilded Foil",
    "min_price": 45.00,
    "count": 125
  }
]
```

### Example

```bash
curl "https://api.wonderstrader.com/api/v1/market/treatments"
```

---

## POST /market/reports

Submit a report for an incorrect, fake, or duplicate listing.

### Request Body

```json
{
  "listing_id": 12345,
  "card_id": 42,
  "reason": "wrong_price",
  "notes": "Price is clearly a typo - listed at $0.15 instead of $15.00",
  "listing_title": "WOTF Ember the Flame",
  "listing_price": 0.15,
  "listing_url": "https://www.ebay.com/itm/..."
}
```

### Report Reasons

| Reason | Description |
|--------|-------------|
| `wrong_price` | Price appears incorrect (typo, error) |
| `fake_listing` | Not a legitimate sale |
| `duplicate` | Same sale listed multiple times |
| `wrong_card` | Listed under wrong card |
| `other` | Other issue (explain in notes) |

### Response

```json
{
  "id": 1,
  "listing_id": 12345,
  "reason": "wrong_price",
  "status": "pending",
  "created_at": "2024-01-15T10:30:00Z",
  "message": "Report submitted successfully"
}
```

---

## GET /market/reports

Get listing reports for admin review.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | - | Filter by status: `pending`, `resolved`, `rejected` |
| `limit` | int | 50 | Max items to return (max 200) |

### Response

```json
[
  {
    "id": 1,
    "listing_id": 12345,
    "card_id": 42,
    "reason": "wrong_price",
    "notes": "Price is clearly a typo",
    "listing_title": "WOTF Ember the Flame",
    "listing_price": 0.15,
    "listing_url": "https://www.ebay.com/itm/...",
    "status": "pending",
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```
