# WondersTracker API Documentation

The WondersTracker API provides programmatic access to market data for "Wonders of the First" trading cards.

## Data Sources

Data is aggregated from multiple marketplaces:

| Platform | Data Type | Update Frequency |
|----------|-----------|------------------|
| **eBay** | Sales, active listings, seller info | Every 15 minutes |
| **Blokpax** | NFT floors, sales, offers (BPX/USD) | Every 30 minutes |
| **OpenSea** | NFT sales, collection stats (ETH/USD) | Every 30 minutes |

eBay and OpenSea data flows through the Cards API. Blokpax has dedicated endpoints.

## Base URL

```
https://api.wonderstrader.com/api/v1
```

## Authentication

### API Key Authentication

For programmatic access, use an API key in the `X-API-Key` header:

```bash
curl -H "X-API-Key: wt_your_api_key_here" \
  https://api.wonderstrader.com/api/v1/cards
```

**Rate Limits:**
- 60 requests per minute
- 10,000 requests per day

### Bearer Token (Web App)

For authenticated users in the web application:

```bash
curl -H "Authorization: Bearer your_jwt_token" \
  https://api.wonderstrader.com/api/v1/cards
```

## Quick Start

```bash
# Get all cards with market data
curl "https://api.wonderstrader.com/api/v1/cards?limit=50"

# Get a specific card by ID or slug
curl "https://api.wonderstrader.com/api/v1/cards/42"
curl "https://api.wonderstrader.com/api/v1/cards/ember-the-flame"

# Get sales history for a card
curl "https://api.wonderstrader.com/api/v1/cards/42/history"

# Get market overview
curl "https://api.wonderstrader.com/api/v1/market/overview?time_period=7d"
```

## API Reference

- [Cards API](./cards.md) - Card data, pricing, and sales history (eBay + OpenSea)
- [Market API](./market.md) - Market overview, activity, and listing reports
- [Blokpax API](./blokpax.md) - NFT marketplace data (Blokpax integration)
- [Authentication](./authentication.md) - API keys, JWT tokens, rate limits

## Response Format

All endpoints return JSON. Successful responses return data directly or wrapped in a pagination object:

```json
{
  "items": [...],
  "total": 150,
  "skip": 0,
  "limit": 50,
  "hasMore": true
}
```

### Error Responses

```json
{
  "detail": "Card not found"
}
```

| Status Code | Meaning |
|-------------|---------|
| 200 | Success |
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Missing or invalid authentication |
| 403 | Forbidden - Access denied |
| 404 | Not Found - Resource doesn't exist |
| 429 | Too Many Requests - Rate limit exceeded |

## Caching

Most endpoints are cached for performance:
- Card list: 5 minutes
- Card detail: 5 minutes
- Market overview: 2 minutes

Responses include an `X-Cache` header (`HIT` or `MISS`) indicating cache status.

## Pagination

List endpoints support pagination:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip` | int | 0 | Number of items to skip |
| `limit` | int | varies | Max items to return |
| `include_total` | bool | false | Include total count (slower) |

## Common Parameters

### Time Periods

Many endpoints accept a `time_period` parameter:

| Value | Description |
|-------|-------------|
| `24h` | Last 24 hours |
| `7d` | Last 7 days |
| `30d` | Last 30 days |
| `90d` | Last 90 days |
| `all` | All time |

### Product Types

Filter cards by product type:

| Value | Description |
|-------|-------------|
| `Single` | Individual cards |
| `Box` | Sealed boxes |
| `Pack` | Sealed packs |
| `Bundle` | Bundles/lots |
| `Proof` | Proof prints |

## OpenAPI Specification

A full OpenAPI (Swagger) specification is available at:

```
https://api.wonderstrader.com/api/v1/openapi.json
```

Interactive documentation:
```
https://api.wonderstrader.com/docs
```
