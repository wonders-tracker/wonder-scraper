# Blokpax API

The Blokpax API provides access to NFT marketplace data from Blokpax, including storefronts, floor prices, sales, and offers.

## Overview

Blokpax is an NFT marketplace where WOTF digital cards are traded. This API provides:
- Storefront data (collections)
- Price snapshots over time
- Sales history
- Active offers/bids

Prices are tracked in both BPX (Blokpax token) and USD.

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/blokpax/storefronts` | List all WOTF storefronts |
| GET | `/blokpax/storefronts/{slug}` | Get specific storefront |
| GET | `/blokpax/storefronts/{slug}/snapshots` | Get price history |
| GET | `/blokpax/storefronts/{slug}/sales` | Get storefront sales |
| GET | `/blokpax/sales` | Get all recent sales |
| GET | `/blokpax/assets` | List indexed assets |
| GET | `/blokpax/offers` | List all offers |
| GET | `/blokpax/offers/asset/{id}` | Get offers for an asset |
| GET | `/blokpax/summary` | Dashboard summary |

---

## GET /blokpax/storefronts

List all WOTF storefronts with current floor prices.

### Response

```json
[
  {
    "id": 1,
    "slug": "wonders-of-the-first",
    "name": "Wonders of the First",
    "description": "Official WOTF collection",
    "image_url": "https://...",
    "network_id": 1,
    "floor_price_bpx": 50.0,
    "floor_price_usd": 12.50,
    "total_tokens": 10000,
    "listed_count": 250,
    "updated_at": "2024-01-15T10:30:00Z"
  }
]
```

---

## GET /blokpax/storefronts/{slug}

Get detailed data for a specific storefront.

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `slug` | string | Storefront slug (e.g., `wonders-of-the-first`) |

### Response

Same structure as list response, single object.

---

## GET /blokpax/storefronts/{slug}/snapshots

Get price history snapshots for a storefront (useful for charts).

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `slug` | string | - | Storefront slug |
| `days` | int | 30 | Number of days of history (max 365) |
| `limit` | int | 100 | Max snapshots (max 1000) |

### Response

```json
[
  {
    "id": 123,
    "storefront_slug": "wonders-of-the-first",
    "floor_price_bpx": 50.0,
    "floor_price_usd": 12.50,
    "bpx_price_usd": 0.25,
    "listed_count": 250,
    "total_tokens": 10000,
    "timestamp": "2024-01-15T00:00:00Z"
  }
]
```

---

## GET /blokpax/storefronts/{slug}/sales

Get recent sales for a specific storefront.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `slug` | string | - | Storefront slug |
| `days` | int | 30 | Number of days of history (max 365) |
| `limit` | int | 50 | Max items (max 500) |

### Response

```json
[
  {
    "id": 456,
    "listing_id": "abc123",
    "asset_id": "wotf-ember-123",
    "asset_name": "Ember the Flame #123",
    "price_bpx": 100.0,
    "price_usd": 25.00,
    "quantity": 1,
    "seller_address": "0x1234...",
    "buyer_address": "0x5678...",
    "filled_at": "2024-01-15T08:22:00Z",
    "card_id": 42
  }
]
```

---

## GET /blokpax/sales

Get recent sales across all WOTF storefronts.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | int | 7 | Number of days (max 90) |
| `limit` | int | 100 | Max items (max 500) |

### Response

Same structure as storefront sales.

---

## GET /blokpax/assets

List indexed Blokpax assets.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `storefront_slug` | string | - | Filter by storefront |
| `limit` | int | 50 | Max items (max 500) |

### Response

```json
[
  {
    "id": 1,
    "external_id": "wotf-ember-123",
    "storefront_slug": "wonders-of-the-first",
    "name": "Ember the Flame",
    "description": "A powerful fire elemental...",
    "image_url": "https://...",
    "network_id": 1,
    "owner_count": 150,
    "token_count": 500,
    "floor_price_bpx": 80.0,
    "floor_price_usd": 20.00,
    "card_id": 42
  }
]
```

---

## GET /blokpax/offers

List all offers/bids across WOTF storefronts.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | `open` | Filter: `open`, `filled`, `cancelled` |
| `limit` | int | 50 | Max items (max 500) |

### Response

```json
[
  {
    "id": 789,
    "external_id": "offer-abc123",
    "asset_id": "wotf-ember-123",
    "price_bpx": 75.0,
    "price_usd": 18.75,
    "quantity": 1,
    "buyer_address": "0x1234...",
    "status": "open",
    "created_at": "2024-01-14T15:00:00Z",
    "scraped_at": "2024-01-15T10:00:00Z"
  }
]
```

---

## GET /blokpax/offers/asset/{asset_id}

Get all offers for a specific asset.

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `asset_id` | string | Asset ID (e.g., `wotf-ember-123`) |
| `status` | string | Optional status filter |

### Response

Same structure as offers list.

---

## GET /blokpax/summary

Get a summary of all WOTF Blokpax data for dashboard display.

### Response

```json
{
  "storefronts": [
    {
      "slug": "wonders-of-the-first",
      "name": "Wonders of the First",
      "floor_price_usd": 12.50,
      "floor_price_bpx": 50.0,
      "listed_count": 250,
      "total_tokens": 10000
    }
  ],
  "totals": {
    "total_listed": 250,
    "total_tokens": 10000,
    "lowest_floor_usd": 12.50,
    "recent_sales_24h": 15,
    "volume_7d_usd": 1250.00
  }
}
```

---

## BPX Token

BPX is the native token of the Blokpax marketplace. All prices are tracked in both BPX and USD:

- `price_bpx` - Price in BPX tokens
- `price_usd` - Price in US dollars (converted at time of snapshot)
- `bpx_price_usd` - BPX/USD exchange rate at time of snapshot

USD prices may fluctuate based on BPX token price changes.
