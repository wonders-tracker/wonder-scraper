# PRD: MoonPay NFT Buy Now Integration

## Overview

Enable users to purchase NFT cards directly through Wonder Tracker using MoonPay's NFT checkout widget. Users can buy with credit/debit cards and have NFTs delivered directly to their wallets, all without leaving our platform.

---

## Problem Statement

Currently, users browsing card listings on Wonder Tracker must:
1. Navigate to external marketplaces (OpenSea, Blokpax)
2. Connect their wallet
3. Have crypto ready or go through a separate fiat on-ramp
4. Complete the purchase on a third-party site

This friction results in lost conversions and a fragmented user experience.

---

## Solution

Integrate MoonPay's NFT checkout widget to provide a seamless "Buy Now" experience:
- One-click purchase initiation from card detail pages
- Credit/debit card payments
- NFT delivered directly to user's wallet
- Revenue via MoonPay's partner/affiliate fee mechanism

---

## Goals & Success Metrics

| Goal | Metric | Target |
|------|--------|--------|
| Increase purchase conversions | Checkout completion rate | >40% |
| Generate affiliate revenue | Monthly affiliate fees | $500+ within 3 months |
| Reduce time-to-purchase | Avg clicks to complete | <5 clicks |
| User satisfaction | Post-purchase NPS | >50 |

---

## User Stories

### As a collector
- I want to buy an NFT card I see on Wonder Tracker without leaving the site
- I want to pay with my credit card without needing crypto first
- I want the NFT delivered directly to my wallet

### As a casual browser
- I want to see a clear "Buy Now" price including all fees
- I want to complete purchase without complex wallet setup

### As a power user
- I want to specify which wallet receives my NFT
- I want transaction history in my Wonder Tracker account

---

## Scope

### In Scope (Phase 1)
- MoonPay Web SDK integration
- NFT checkout for OpenSea listings
- NFT checkout for Blokpax listings
- Server-side URL signing (security)
- Webhook handling for transaction status
- Purchase intent tracking in database
- Basic purchase history UI
- Partner/affiliate fee setup

### Out of Scope (Phase 1)
- Bulk purchases
- Auction bidding
- Physical card checkout
- Custom wallet creation/custody
- Mobile app integration

### Future Phases
- Phase 2: Bulk purchase discounts, watchlist quick-buy
- Phase 3: Mobile app SDK, Apple Pay/Google Pay (newTab flow)

---

## Technical Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        Wonder Tracker                           │
├─────────────────────────────────────────────────────────────────┤
│  Frontend (TanStack)           │  Backend (FastAPI/SaaS)        │
│  ┌─────────────────────────┐   │  ┌─────────────────────────┐   │
│  │ MoonPay Web SDK         │   │  │ /api/v1/checkout/       │   │
│  │ @moonpay/moonpay-js     │   │  │   - create-intent       │   │
│  │                         │   │  │   - sign-url            │   │
│  │ - flow: "nft"           │   │  │   - webhook             │   │
│  │ - variant: embedded     │   │  │                         │   │
│  │ - updateSignature()     │   │  │ PurchaseIntent model    │   │
│  └─────────────────────────┘   │  └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
                              ┌───────────────────────┐
                              │       MoonPay         │
                              │  - NFT Widget         │
                              │  - Payment Processing │
                              │  - KYC (as needed)    │
                              │  - Webhooks           │
                              └───────────────────────┘
                                          │
                                          ▼
                              ┌───────────────────────┐
                              │   NFT Marketplaces    │
                              │  - OpenSea            │
                              │  - Blokpax            │
                              └───────────────────────┘
```

### Data Flow

```
1. User clicks "Buy Now"
         │
         ▼
2. Frontend → POST /checkout/create-intent
   { listing_id, marketplace, wallet_address? }
         │
         ▼
3. Backend creates PurchaseIntent (idempotency)
   Returns: { intent_id, widget_params }
         │
         ▼
4. Frontend initializes MoonPay SDK
   Calls generateUrlForSigning()
         │
         ▼
5. Frontend → POST /checkout/sign-url
   { url_to_sign }
         │
         ▼
6. Backend signs URL with MoonPay secret
   Returns: { signature }
         │
         ▼
7. Frontend calls updateSignature(signature)
   Shows MoonPay widget (embedded/overlay)
         │
         ▼
8. User completes payment in widget
         │
         ▼
9. MoonPay → POST /checkout/webhook
   { transaction_id, status, ... }
         │
         ▼
10. Backend verifies signature, updates intent
    Marks complete/failed
         │
         ▼
11. Frontend polls/subscribes for status
    Shows success + tracker link
```

---

## Database Schema

### PurchaseIntent (SaaS module)

```python
class PurchaseIntent(SQLModel, table=True):
    """Tracks NFT purchase attempts through MoonPay"""

    id: int = Field(primary_key=True)

    # User & listing
    user_id: int = Field(foreign_key="user.id", index=True)
    card_id: int = Field(foreign_key="card.id", index=True)
    marketplace: str  # "opensea" | "blokpax"
    listing_id: str  # External marketplace listing ID

    # NFT details
    contract_address: str
    token_id: str
    chain: str = "ethereum"  # ethereum, polygon, arbitrum

    # Pricing (snapshot at intent creation)
    listing_price_usd: float
    affiliate_fee_usd: float | None = None
    total_usd: float

    # Wallet
    destination_wallet: str | None = None

    # MoonPay tracking
    moonpay_transaction_id: str | None = None
    moonpay_widget_url: str | None = None

    # Status
    status: str = "pending"  # pending, widget_opened, processing, completed, failed, expired
    failure_reason: str | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None

    # Idempotency
    idempotency_key: str = Field(unique=True, index=True)
```

### PurchaseTransaction (for completed purchases)

```python
class PurchaseTransaction(SQLModel, table=True):
    """Completed purchase record with MoonPay details"""

    id: int = Field(primary_key=True)
    intent_id: int = Field(foreign_key="purchaseintent.id", unique=True)
    user_id: int = Field(foreign_key="user.id", index=True)

    # MoonPay transaction details
    moonpay_transaction_id: str = Field(unique=True, index=True)
    moonpay_status: str

    # Financials
    fiat_amount: float
    fiat_currency: str = "USD"
    crypto_amount: float | None = None
    crypto_currency: str | None = None
    network_fee: float | None = None
    moonpay_fee: float | None = None
    affiliate_fee: float | None = None

    # NFT delivery
    nft_delivered: bool = False
    delivery_tx_hash: str | None = None

    # Tracker
    tracker_url: str | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
```

---

## API Endpoints

### POST /api/v1/checkout/create-intent

Create a purchase intent for an NFT listing.

**Request:**
```json
{
  "card_id": 123,
  "marketplace": "opensea",
  "listing_id": "0x1234...5678",
  "wallet_address": "0xuser...wallet"  // optional
}
```

**Response:**
```json
{
  "intent_id": "pi_abc123",
  "idempotency_key": "ik_xyz789",
  "widget_params": {
    "contractAddress": "0xcontract...",
    "tokenId": "12345",
    "listingId": "0x1234...5678",
    "walletAddress": "0xuser...wallet",
    "baseCurrencyCode": "USD",
    "externalTransactionId": "pi_abc123"
  },
  "pricing": {
    "listing_price_usd": 49.99,
    "estimated_fees_usd": 5.00,
    "affiliate_fee_usd": 2.50,
    "total_usd": 57.49
  }
}
```

### POST /api/v1/checkout/sign-url

Sign MoonPay widget URL for security.

**Request:**
```json
{
  "url": "https://buy.moonpay.com/?apiKey=pk_...&contractAddress=..."
}
```

**Response:**
```json
{
  "signature": "abc123def456..."
}
```

### POST /api/v1/checkout/webhook

MoonPay webhook endpoint (called by MoonPay).

**Headers:**
- `Moonpay-Signature`: Webhook signature for verification

**Request:** (MoonPay webhook payload)

**Response:** `200 OK`

### GET /api/v1/checkout/intent/{intent_id}

Get purchase intent status.

**Response:**
```json
{
  "intent_id": "pi_abc123",
  "status": "completed",
  "transaction": {
    "moonpay_transaction_id": "tx_...",
    "tracker_url": "https://buy.moonpay.com/transaction_receipt/...",
    "nft_delivered": true,
    "delivery_tx_hash": "0x..."
  }
}
```

### GET /api/v1/user/purchases

Get user's purchase history.

**Response:**
```json
{
  "purchases": [
    {
      "id": 1,
      "card": { "id": 123, "name": "Dragonmaster Cai", ... },
      "marketplace": "opensea",
      "total_usd": 57.49,
      "status": "completed",
      "completed_at": "2025-01-09T12:00:00Z",
      "tracker_url": "..."
    }
  ]
}
```

---

## Frontend Components

### BuyNowButton

```tsx
// Location: frontend/app/components/checkout/BuyNowButton.tsx

interface BuyNowButtonProps {
  listing: {
    id: string
    marketplace: 'opensea' | 'blokpax'
    price_usd: number
    contract_address: string
    token_id: string
  }
  card: Card
  variant?: 'primary' | 'compact'
}
```

### MoonPayCheckout

```tsx
// Location: frontend/app/components/checkout/MoonPayCheckout.tsx

// Wraps MoonPay Web SDK
// Handles: init → sign → show → poll status
```

### PurchaseHistoryPanel

```tsx
// Location: frontend/app/components/checkout/PurchaseHistoryPanel.tsx

// Shows user's purchase history with status, receipts, tracker links
```

---

## MoonPay Configuration

### Dashboard Setup

1. **API Keys**
   - Publishable key → Frontend (env: `VITE_MOONPAY_API_KEY`)
   - Secret key → Backend (env: `MOONPAY_SECRET_KEY`)

2. **Domain Allowlist**
   - Add `wonderstracker.com` for embedded widget
   - Add staging domain for testing

3. **Webhook Configuration**
   - URL: `https://api.wonderstracker.com/api/v1/checkout/webhook`
   - Events: `transaction_created`, `transaction_updated`, `transaction_failed`

4. **Partner/Affiliate Fee**
   - Contact MoonPay partner support to configure
   - Typical range: 1-5% of transaction value
   - Payout address: Configure in dashboard

### Environment Variables

```bash
# Backend (.env)
MOONPAY_SECRET_KEY=sk_live_...
MOONPAY_WEBHOOK_SECRET=whs_...
MOONPAY_AFFILIATE_FEE_PERCENT=2.5

# Frontend (.env)
VITE_MOONPAY_API_KEY=pk_live_...
VITE_MOONPAY_ENVIRONMENT=production  # or sandbox
```

---

## Security Considerations

1. **URL Signing** (Required)
   - All widget URLs must be signed server-side
   - Prevents parameter tampering

2. **Webhook Verification** (Required)
   - Verify `Moonpay-Signature` header on all webhooks
   - Reject unsigned/invalid requests

3. **Idempotency**
   - Use idempotency keys to prevent duplicate purchases
   - Check for existing intents before creating new ones

4. **Rate Limiting**
   - Limit intent creation: 10/minute per user
   - Limit sign requests: 20/minute per user

5. **Wallet Validation**
   - Validate wallet addresses before passing to MoonPay
   - Prevent typos/invalid addresses

---

## Error Handling

| Error | User Message | Action |
|-------|--------------|--------|
| Listing no longer available | "This item has been sold" | Redirect to similar items |
| MoonPay KYC required | "Verification needed" | Show MoonPay KYC flow |
| Payment declined | "Payment unsuccessful" | Suggest retry or different card |
| Network error | "Connection issue" | Retry with exponential backoff |
| Webhook verification failed | (internal) | Log, alert, don't update status |

---

## Testing Plan

### Unit Tests
- [ ] URL signing produces valid signatures
- [ ] Webhook signature verification
- [ ] Intent state machine transitions
- [ ] Idempotency key generation/validation

### Integration Tests
- [ ] Full purchase flow (MoonPay sandbox)
- [ ] Webhook processing
- [ ] Status polling

### E2E Tests (Staging)
- [ ] Buy button renders for eligible listings
- [ ] Widget opens correctly
- [ ] User can complete test purchase
- [ ] Purchase appears in history

### Manual Testing
- [ ] Test with MoonPay sandbox credentials
- [ ] Verify embedded vs overlay vs newTab variants
- [ ] Test on mobile browsers
- [ ] Verify affiliate fee appears in MoonPay dashboard

---

## Rollout Plan

### Phase 1: Internal Testing (Week 1)
- Deploy to staging
- Team testing with sandbox credentials
- Fix issues

### Phase 2: Beta (Week 2)
- Enable for 10% of users (feature flag)
- Monitor conversion rates, errors
- Collect feedback

### Phase 3: General Availability (Week 3)
- Enable for all users
- Announce feature
- Monitor metrics

---

## Dependencies

| Dependency | Type | Notes |
|------------|------|-------|
| MoonPay Partner Account | External | Apply at moonpay.com/partners |
| `@moonpay/moonpay-js` | npm | Frontend SDK |
| OpenSea API | External | For listing data |
| Blokpax API | External | For listing data |

---

## Open Questions

1. **Wallet address source**: Should we prompt users to enter wallet, connect wallet, or use a custodial solution?
2. **Minimum purchase amount**: MoonPay has minimums (~$30 USD) - how to handle lower-priced NFTs?
3. **Supported chains**: Start with Ethereum only, or include Polygon/Arbitrum from day 1?
4. **Mobile experience**: Embedded iframe vs newTab for mobile users?

---

## References

- [MoonPay Web SDK](https://dev.moonpay.com/docs/on-ramp-web-sdk)
- [MoonPay NFT Widget Integration](https://dev.moonpay.com/v1.0/docs/integrating-the-widget)
- [MoonPay URL Signing](https://dev.moonpay.com/docs/on-ramp-enhance-security-using-signed-urls)
- [MoonPay Webhooks](https://dev.moonpay.com/reference/reference-webhooks-signature)
- [MoonPay Partner FAQ](https://dev.moonpay.com/v1.0/docs/faqs)
