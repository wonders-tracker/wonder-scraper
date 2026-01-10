# PRD: MoonPay NFT Buy Now Integration

## Overview

Enable users to purchase NFT cards directly through Wonder Tracker using MoonPay's NFT checkout widget. Users can buy with credit/debit cards (including Apple Pay and Google Pay) and have NFTs delivered directly to their wallets—all without leaving our platform. Purchases automatically sync to the user's portfolio.

---

## Problem Statement

Currently, users browsing card listings on Wonder Tracker must:
1. Navigate to external marketplaces (OpenSea, Blokpax)
2. Connect their wallet
3. Have crypto ready or go through a separate fiat on-ramp
4. Complete the purchase on a third-party site
5. Manually add the card to their portfolio

This friction results in lost conversions and a fragmented user experience.

---

## Solution

Integrate MoonPay's NFT checkout widget to provide a seamless "Buy Now" experience:
- One-click purchase initiation from card detail pages and listings panel
- Credit/debit card payments with Apple Pay & Google Pay support
- NFT delivered directly to user's wallet
- **Automatic portfolio sync** after successful purchase
- Revenue via MoonPay's partner/affiliate fee mechanism

---

## Goals & Success Metrics

| Goal | Metric | Target |
|------|--------|--------|
| Increase purchase conversions | Checkout completion rate | >40% |
| Generate affiliate revenue | Monthly affiliate fees | $500+ within 3 months |
| Reduce time-to-purchase | Avg clicks to complete | <5 clicks |
| Auto-portfolio adoption | % purchases auto-added | >90% |
| User satisfaction | Post-purchase NPS | >50 |

---

## User Stories

### As a collector
- I want to buy an NFT card I see on Wonder Tracker without leaving the site
- I want to pay with my credit card or Apple Pay without needing crypto
- I want the NFT delivered directly to my wallet
- I want the card automatically added to my portfolio with correct price/date

### As a casual browser
- I want to see a clear "Buy Now" price including all fees
- I want to complete purchase without complex wallet setup
- I want my purchase history tracked

### As a power user
- I want to specify which wallet receives my NFT
- I want to see transaction receipts and blockchain confirmations
- I want portfolio P&L to reflect my actual purchase price

---

## Scope

### In Scope (Phase 1)
- MoonPay Web SDK integration (newTab variant for Apple Pay)
- NFT checkout for OpenSea listings
- NFT checkout for Blokpax listings
- Server-side URL signing (security)
- Webhook handling for transaction status
- **Auto-add to portfolio after purchase**
- Purchase history in user profile
- Partner/affiliate fee setup

### Out of Scope (Phase 1)
- Bulk purchases
- Auction bidding
- Physical card checkout (eBay non-NFT)
- Custom wallet creation/custody
- Embedded widget variant (no Apple Pay)

### Future Phases
- Phase 2: Bulk purchase discounts, watchlist quick-buy
- Phase 3: Embedded widget for desktop, mobile app SDK

---

## Native Integration Points

### 1. Card Detail Page (`cards.$cardId.tsx`)

**Location**: PriceBox component "Buy Now" button

```
Current Flow:
┌─────────────────────────┐
│ Buy Now from $12.99     │ → Opens external eBay/Blokpax URL
│ [External Link Icon]    │
└─────────────────────────┘

New Flow:
┌─────────────────────────┐
│ Buy Now from $12.99     │ → For NFTs: Opens MoonPay checkout
│ [Apple Pay available]   │ → For physical: Opens external URL (unchanged)
└─────────────────────────┘
```

**Integration**: Modify `PriceBox.tsx` to detect NFT listings and route to MoonPay instead of external URL.

### 2. Listings Panel (`ListingsPanel.tsx`)

**Location**: Individual listing rows

```
Current:
┌──────────────────────────────────────────────────┐
│ Seller: nft_collector  │ $12.99  │ [View on OS] │
└──────────────────────────────────────────────────┘

New:
┌──────────────────────────────────────────────────┐
│ Seller: nft_collector  │ $12.99  │ [Buy Now]    │
│ OpenSea • Legendary    │  +fees  │ [Apple Pay]  │
└──────────────────────────────────────────────────┘
```

**Integration**: Add "Buy Now" button to NFT listings with MoonPay checkout.

### 3. Mobile Sticky Actions (`MobileStickyActions.tsx`)

**Location**: Bottom sticky bar on mobile card detail

```
┌────────────────────────────────────────┐
│ [+ Portfolio]     [Buy $12.99  ]   │
└────────────────────────────────────────┘
```

**Integration**: Route NFT purchases through MoonPay with newTab for Apple Pay support.

### 4. Product Cards (`ProductCard.tsx`)

**Location**: Hot deals section, grid views

```
Current:
┌─────────────┐
│   [Image]   │
│ Card Name   │
│ $12.99      │
│ [Buy Now]   │  ← Badge only, links to detail page
└─────────────┘

Enhanced:
┌─────────────┐
│   [Image]   │
│ Card Name   │
│ $12.99      │
│ [Buy Now ]  │  ← Quick checkout for NFTs
└─────────────┘
```

### 5. Portfolio Auto-Add (`AddToPortfolioModal.tsx`)

**After purchase completes**:
```tsx
// Auto-create portfolio entry
const portfolioEntry: PortfolioCardCreate = {
  card_id: purchasedCard.id,
  treatment: listing.treatment || 'Standard',
  source: 'MoonPay',  // New source type
  purchase_price: transaction.fiat_amount,
  purchase_date: transaction.completed_at,
  notes: `MoonPay TX: ${transaction.moonpay_transaction_id}`,
}
```

**Source options update** (schemas.py):
```python
VALID_SOURCES = {"eBay", "Blokpax", "TCGPlayer", "LGS", "Trade", "Pack Pull", "MoonPay", "Other"}
```

---

## Apple Pay & Google Pay Support

### Requirement
MoonPay's overlay/embedded variants run in iframes which **don't support** Apple Pay or Google Pay due to browser security restrictions.

### Solution
Use `newTab` or `newWindow` variant for checkout:

```tsx
// MoonPay SDK initialization
const moonPay = window.MoonPayWebSdk.init({
  flow: 'nft',
  environment: 'production',
  variant: 'newTab',  // Required for Apple Pay / Google Pay
  params: {
    apiKey: import.meta.env.VITE_MOONPAY_API_KEY,
    // ... other params
  }
});
```

### UX Flow with Apple Pay

```
1. User clicks "Buy Now" on Wonder Tracker
         │
         ▼
2. New tab opens with MoonPay checkout
   ┌─────────────────────────────────────┐
   │  MoonPay Checkout                   │
   │  ┌─────────────────────────────────┐│
   │  │  [Apple Pay]  [Google Pay]     ││
   │  │  ─────────── or ───────────     ││
   │  │  [Credit/Debit Card]           ││
   │  └─────────────────────────────────┘│
   │  Total: $14.99 (incl. fees)        │
   └─────────────────────────────────────┘
         │
         ▼
3. User completes payment (Apple Pay = 1 tap)
         │
         ▼
4. MoonPay redirects to Wonder Tracker receipt page
   OR user returns to original tab
         │
         ▼
5. Webhook fires → Portfolio updated → Success toast
```

### Mobile Considerations
- `newTab` works well on mobile Safari/Chrome
- Apple Pay button appears automatically when available
- Smooth native payment sheet experience

---

## Portfolio Integration

### Auto-Add Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    Purchase Completes                         │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  Webhook: transaction_completed                               │
│  - moonpay_transaction_id: "tx_abc123"                       │
│  - fiat_amount: 14.99                                        │
│  - nft_delivered: true                                       │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  Backend: Create PortfolioCard                                │
│  - card_id: 123                                              │
│  - treatment: "Legendary" (from listing metadata)            │
│  - source: "MoonPay"                                         │
│  - purchase_price: 14.99                                     │
│  - purchase_date: 2025-01-09                                 │
│  - notes: "MoonPay TX: tx_abc123 | OpenSea listing xyz"      │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  Frontend: Show success + portfolio link                      │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ ✓ Purchase complete!                                   │  │
│  │ Dragonmaster Cai added to portfolio                    │  │
│  │ [View in Portfolio] [View Receipt]                     │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### Portfolio Card Fields Mapping

| Portfolio Field | Source |
|-----------------|--------|
| `card_id` | From listing metadata |
| `treatment` | From listing (e.g., "Legendary", "Animated") |
| `source` | "MoonPay" (new valid source) |
| `purchase_price` | `transaction.fiat_amount` |
| `purchase_date` | `transaction.completed_at` |
| `grading` | null (NFTs ungraded) |
| `notes` | Transaction ID + marketplace + listing ID |

### Duplicate Prevention

Before auto-adding:
1. Check if user already has this exact NFT (contract + tokenId)
2. If exists, update notes with new transaction info
3. If not exists, create new portfolio entry

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
│  │ - variant: newTab       │   │  │   - status              │   │
│  │ - updateSignature()     │   │  │                         │   │
│  │                         │   │  │ Portfolio auto-add      │   │
│  │ Components:             │   │  │   - PortfolioCard       │   │
│  │ - BuyNowButton          │   │  │   - PurchaseTransaction │   │
│  │ - CheckoutStatus        │   │  └─────────────────────────┘   │
│  │ - PurchaseHistory       │   │                                │
│  └─────────────────────────┘   │                                │
└─────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
                              ┌───────────────────────┐
                              │       MoonPay         │
                              │  - NFT Widget         │
                              │  - Apple Pay          │
                              │  - Google Pay         │
                              │  - Card Payments      │
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
1. User clicks "Buy Now" on NFT listing
         │
         ▼
2. Frontend checks: Is this an NFT? Has wallet address?
   - If no wallet: Prompt to enter/connect
   - If NFT: Continue to MoonPay
   - If physical: Use existing external link flow
         │
         ▼
3. Frontend → POST /checkout/create-intent
   {
     card_id: 123,
     listing_id: "opensea_xyz",
     marketplace: "opensea",
     wallet_address: "0x...",
     auto_add_portfolio: true
   }
         │
         ▼
4. Backend creates PurchaseIntent
   - Generates idempotency key
   - Fetches listing details from marketplace API
   - Returns widget params
         │
         ▼
5. Frontend initializes MoonPay SDK (newTab variant)
   - Calls generateUrlForSigning()
   - POSTs to /checkout/sign-url
   - Calls updateSignature(signature)
   - Opens MoonPay in new tab
         │
         ▼
6. User completes payment (Apple Pay / Card / etc)
         │
         ▼
7. MoonPay → POST /checkout/webhook
   - Backend verifies signature
   - Updates PurchaseIntent status
   - If success: Creates PortfolioCard
         │
         ▼
8. Frontend polls /checkout/intent/{id}/status
   - Shows success toast
   - Links to portfolio
   - Shows receipt/tracker
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
    treatment: str | None = None  # For portfolio: "Legendary", "Animated", etc.

    # Pricing (snapshot at intent creation)
    listing_price_usd: float
    affiliate_fee_usd: float | None = None
    total_usd: float

    # Wallet
    destination_wallet: str | None = None

    # MoonPay tracking
    moonpay_transaction_id: str | None = None
    moonpay_widget_url: str | None = None

    # Portfolio integration
    auto_add_portfolio: bool = True
    portfolio_card_id: int | None = Field(foreign_key="portfoliocard.id", default=None)

    # Status
    status: str = "pending"
    # pending → widget_opened → processing → completed → portfolio_added
    # pending → widget_opened → processing → failed
    # pending → expired
    failure_reason: str | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None

    # Idempotency
    idempotency_key: str = Field(unique=True, index=True)
```

### PurchaseTransaction (completed purchases)

```python
class PurchaseTransaction(SQLModel, table=True):
    """Completed purchase record with MoonPay details"""

    id: int = Field(primary_key=True)
    intent_id: int = Field(foreign_key="purchaseintent.id", unique=True)
    user_id: int = Field(foreign_key="user.id", index=True)

    # MoonPay transaction details
    moonpay_transaction_id: str = Field(unique=True, index=True)
    moonpay_status: str
    payment_method: str  # "apple_pay", "google_pay", "card"

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

### Schema Updates

```python
# app/schemas.py - Update VALID_SOURCES
VALID_SOURCES = {"eBay", "Blokpax", "TCGPlayer", "LGS", "Trade", "Pack Pull", "MoonPay", "Other"}

# Also update frontend
# frontend/app/components/AddToPortfolioModal.tsx
const SOURCES_BY_TYPE: Record<string, string[]> = {
    'NFT': ['OpenSea', 'Blur', 'Magic Eden', 'MoonPay', 'Other'],  // Add MoonPay
    'default': ['eBay', 'Blokpax', 'TCGPlayer', 'LGS', 'Trade', 'Pack Pull', 'MoonPay', 'Other']
}
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
  "wallet_address": "0xuser...wallet",
  "auto_add_portfolio": true
}
```

**Response:**
```json
{
  "intent_id": "pi_abc123",
  "idempotency_key": "ik_xyz789",
  "widget_params": {
    "apiKey": "pk_live_...",
    "contractAddress": "0xcontract...",
    "tokenId": "12345",
    "listingId": "0x1234...5678",
    "walletAddress": "0xuser...wallet",
    "baseCurrencyCode": "USD",
    "externalTransactionId": "pi_abc123",
    "redirectURL": "https://wonderstracker.com/checkout/complete?intent=pi_abc123"
  },
  "pricing": {
    "listing_price_usd": 12.99,
    "estimated_fees_usd": 1.50,
    "affiliate_fee_usd": 0.50,
    "total_usd": 14.99
  },
  "card": {
    "id": 123,
    "name": "Dragonmaster Cai",
    "treatment": "Legendary"
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

MoonPay webhook endpoint.

**Headers:**
- `Moonpay-Signature`: Webhook signature

**Webhook Actions:**
1. Verify signature
2. Update PurchaseIntent status
3. If `status == completed`:
   - Create PurchaseTransaction
   - If `auto_add_portfolio`: Create PortfolioCard
   - Send success notification (WebSocket/polling)

### GET /api/v1/checkout/intent/{intent_id}/status

Poll for purchase status.

**Response:**
```json
{
  "intent_id": "pi_abc123",
  "status": "portfolio_added",
  "transaction": {
    "moonpay_transaction_id": "tx_...",
    "payment_method": "apple_pay",
    "total_usd": 14.99,
    "tracker_url": "https://buy.moonpay.com/transaction_receipt/..."
  },
  "portfolio": {
    "card_id": 456,
    "card_name": "Dragonmaster Cai",
    "view_url": "/portfolio?highlight=456"
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
      "card": { "id": 123, "name": "Dragonmaster Cai", "image_url": "..." },
      "marketplace": "opensea",
      "payment_method": "apple_pay",
      "total_usd": 14.99,
      "status": "completed",
      "completed_at": "2025-01-09T12:00:00Z",
      "portfolio_card_id": 456,
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
    treatment?: string
  }
  card: {
    id: number
    name: string
    product_type?: string
  }
  variant?: 'primary' | 'compact' | 'icon-only'
  showApplePayBadge?: boolean
}

// Renders:
// - "Buy Now $12.99" button
// - Apple Pay badge if available
// - Handles MoonPay SDK initialization
// - Shows loading state during checkout
```

### CheckoutStatusModal

```tsx
// Location: frontend/app/components/checkout/CheckoutStatusModal.tsx

// Shows after MoonPay tab closes or redirect:
// - "Processing..." with spinner
// - "Success! Added to portfolio" with confetti
// - "Failed" with retry option
// - Links to portfolio and receipt
```

### PurchaseHistoryPanel

```tsx
// Location: frontend/app/components/checkout/PurchaseHistoryPanel.tsx

// User profile section showing:
// - All purchases with status
// - Payment method icons (Apple Pay, card, etc.)
// - Links to receipts and portfolio entries
```

### Integration with Existing Components

```tsx
// PriceBox.tsx - Update Buy Now button
{isNftListing ? (
  <BuyNowButton
    listing={currentListing}
    card={card}
    variant="primary"
    showApplePayBadge={true}
  />
) : (
  // Existing external link button
  <a href={buyNowUrl} target="_blank">Buy Now</a>
)}

// ListingsPanel.tsx - Add buy button to each NFT listing row
<ListingRow>
  <SellerInfo />
  <Price />
  {listing.isNft ? (
    <BuyNowButton listing={listing} card={card} variant="compact" />
  ) : (
    <ViewOnPlatformLink listing={listing} />
  )}
</ListingRow>
```

---

## UI/UX Specifications

### Buy Button States

```
Default:
┌─────────────────────────────┐
│  Buy Now from $12.99        │
│  [Apple Pay available]      │
└─────────────────────────────┘

Hover:
┌─────────────────────────────┐
│  Buy Now from $12.99        │  ← bg-brand-600
│  [Apple Pay available]      │
└─────────────────────────────┘

Loading (after click):
┌─────────────────────────────┐
│  [Spinner] Opening...       │
└─────────────────────────────┘

Processing (MoonPay open):
┌─────────────────────────────┐
│  Complete in MoonPay tab →  │
└─────────────────────────────┘
```

### Success Toast

```
┌────────────────────────────────────────────────┐
│ ✓ Purchase complete!                           │
│                                                │
│ Dragonmaster Cai added to your portfolio       │
│                                                │
│ [View Portfolio]  [View Receipt]               │
└────────────────────────────────────────────────┘
```

### Mobile Considerations

- Use full-width buttons on mobile
- newTab opens native browser tab (Apple Pay sheet works)
- Return to app shows success state via polling
- Bottom sheet for checkout status on return

---

## MoonPay Configuration

### Dashboard Setup

1. **API Keys**
   - Publishable key → Frontend: `VITE_MOONPAY_API_KEY`
   - Secret key → Backend: `MOONPAY_SECRET_KEY`

2. **Domain Allowlist**
   - `wonderstracker.com`
   - `wonder-scraper-staging.up.railway.app`

3. **Webhook Configuration**
   - URL: `https://api.wonderstracker.com/api/v1/checkout/webhook`
   - Events: `transaction_created`, `transaction_updated`, `transaction_failed`

4. **Partner/Affiliate Fee**
   - Contact MoonPay partner support
   - Typical: 1-3% of transaction
   - Payout: Monthly to configured address

5. **Redirect URL**
   - `https://wonderstracker.com/checkout/complete`

### Environment Variables

```bash
# Backend (.env)
MOONPAY_SECRET_KEY=sk_live_...
MOONPAY_WEBHOOK_SECRET=whs_...
MOONPAY_AFFILIATE_FEE_PERCENT=2.0

# Frontend (.env)
VITE_MOONPAY_API_KEY=pk_live_...
VITE_MOONPAY_ENVIRONMENT=production
```

---

## Security Considerations

1. **URL Signing** - All widget URLs signed server-side
2. **Webhook Verification** - Verify `Moonpay-Signature` header
3. **Idempotency** - Prevent duplicate purchases
4. **Rate Limiting** - 10 intents/min, 20 signs/min per user
5. **Wallet Validation** - Validate addresses before passing to MoonPay

---

## Error Handling

| Error | User Message | Action |
|-------|--------------|--------|
| Listing sold | "This item has been sold" | Show similar listings |
| KYC required | "Verification needed" | Continue in MoonPay |
| Payment declined | "Payment unsuccessful" | Show retry option |
| Portfolio add failed | "Added but portfolio sync failed" | Manual add option |
| Webhook timeout | (none - background retry) | Retry 3x with backoff |

---

## Testing Plan

### Unit Tests
- [ ] URL signing produces valid signatures
- [ ] Webhook signature verification
- [ ] Intent state machine transitions
- [ ] Portfolio card creation from purchase

### Integration Tests
- [ ] Full purchase flow (MoonPay sandbox)
- [ ] Webhook → Portfolio add flow
- [ ] Apple Pay detection

### E2E Tests (Staging)
- [ ] Buy button appears for NFT listings
- [ ] MoonPay opens in new tab
- [ ] Success toast appears after completion
- [ ] Card appears in portfolio
- [ ] Purchase appears in history

---

## Rollout Plan

### Phase 1: Internal (Week 1)
- Deploy to staging with sandbox keys
- Team testing with test cards
- Verify portfolio integration

### Phase 2: Beta (Week 2)
- Enable for 10% of users (feature flag)
- Monitor conversions and errors
- Collect feedback

### Phase 3: GA (Week 3)
- Enable for all users
- Switch to production MoonPay keys
- Announce feature

---

## Dependencies

| Dependency | Type | Status |
|------------|------|--------|
| MoonPay Partner Account | External | Apply at moonpay.com/partners |
| `@moonpay/moonpay-js` | npm | Ready |
| OpenSea API | External | Existing |
| Blokpax API | External | Existing |
| Portfolio system | Internal | Existing |

---

## Open Questions

1. **Wallet source**: Prompt to enter vs. connect wallet button?
2. **Minimum purchase**: MoonPay min ~$30 - bundle low-value NFTs?
3. **Supported chains**: Ethereum only or include Polygon/Arbitrum?
4. **Failed purchases**: Show in portfolio as "pending" or hide?

---

## References

- [MoonPay Web SDK](https://dev.moonpay.com/docs/on-ramp-web-sdk)
- [MoonPay NFT Widget](https://dev.moonpay.com/v1.0/docs/integrating-the-widget)
- [MoonPay URL Signing](https://dev.moonpay.com/docs/on-ramp-enhance-security-using-signed-urls)
- [MoonPay Webhooks](https://dev.moonpay.com/reference/reference-webhooks-signature)
- [MoonPay Partner FAQ](https://dev.moonpay.com/v1.0/docs/faqs)
- [Apple Pay in MoonPay](https://dev.moonpay.com/docs/on-ramp-web-sdk) (newTab/newWindow required)
