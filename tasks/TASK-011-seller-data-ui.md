# TASK-011: Seller Data UI Integration

**Epic:** EPIC-002 Data Quality Improvements
**Priority:** P1
**Status:** Pending
**Owner:** TBD
**Estimate:** 4-6 hours

---

## Objective
Display seller information (name, feedback score, feedback percent) in the frontend UI. This leverages the seller data backfilled in TASK-009 to help buyers assess listing reliability.

## User Impact
- **Buyer confidence:** See seller reputation before clicking through to eBay
- **Fraud detection:** Identify suspicious low-feedback sellers
- **Top sellers:** Discover trusted high-volume sellers

## Tech Scope

### API Changes
The MarketPrice model already includes seller fields. Ensure API responses include:
```json
{
  "seller_name": "rhomscards",
  "seller_feedback_score": 1542,
  "seller_feedback_percent": 99.8
}
```

### Frontend Components

#### 1. Seller Badge Component
Display seller info inline with listings:
```tsx
// components/SellerBadge.tsx
interface SellerBadgeProps {
  sellerName: string | null;
  feedbackScore?: number | null;
  feedbackPercent?: number | null;
}

// Display: "rhomscards (1542 | 99.8%)"
// Or: "seller_unknown" badge for historical listings
```

#### 2. Card Detail Page
Show seller info on each listing in the sales/listings table:
- Seller name (linked to eBay profile if available)
- Feedback score with color coding (green >100, yellow 10-100, red <10)
- Feedback percentage with color coding (green >98%, yellow 95-98%, red <95%)

#### 3. Top Sellers Widget (Optional)
Show top 10 sellers by volume on market page:
```tsx
// Top Sellers (Last 30 Days)
// 1. rhomscards - 156 sales
// 2. can_pirate - 153 sales
// 3. reigns-locker-room - 126 sales
```

### Data Handling
- `seller_unknown`: Display as gray "Unknown Seller" badge
- `null`: Display as "—" or omit
- Empty string: Should not occur (fixed in backfill)

---

## Units of Work

### UOW-011-1: Create SellerBadge Component
**Type:** frontend
**Estimate:** 1.5 hours
**Dependencies:** None

**Exact Action:**
Create reusable SellerBadge component:
```tsx
// frontend/app/components/SellerBadge.tsx

import { cn } from "@/lib/utils";

interface SellerBadgeProps {
  sellerName: string | null;
  feedbackScore?: number | null;
  feedbackPercent?: number | null;
  showDetails?: boolean;
  className?: string;
}

export function SellerBadge({
  sellerName,
  feedbackScore,
  feedbackPercent,
  showDetails = true,
  className,
}: SellerBadgeProps) {
  if (!sellerName || sellerName === "seller_unknown") {
    return (
      <span className={cn("text-gray-400 text-sm", className)}>
        Unknown Seller
      </span>
    );
  }

  const getFeedbackColor = (percent?: number | null) => {
    if (!percent) return "text-gray-500";
    if (percent >= 98) return "text-green-600";
    if (percent >= 95) return "text-yellow-600";
    return "text-red-600";
  };

  const getScoreColor = (score?: number | null) => {
    if (!score) return "text-gray-500";
    if (score >= 100) return "text-green-600";
    if (score >= 10) return "text-yellow-600";
    return "text-red-600";
  };

  return (
    <span className={cn("text-sm", className)}>
      <span className="font-medium">{sellerName}</span>
      {showDetails && feedbackScore !== null && feedbackPercent !== null && (
        <span className="text-gray-500 ml-1">
          (<span className={getScoreColor(feedbackScore)}>{feedbackScore}</span>
          {" | "}
          <span className={getFeedbackColor(feedbackPercent)}>
            {feedbackPercent?.toFixed(1)}%
          </span>)
        </span>
      )}
    </span>
  );
}
```

**Acceptance Checks:**
- [ ] Component renders seller name
- [ ] Shows feedback score and percent when available
- [ ] Color codes based on reputation thresholds
- [ ] Handles null/unknown gracefully

---

### UOW-011-2: Integrate SellerBadge in Card Detail Page
**Type:** frontend
**Estimate:** 2 hours
**Dependencies:** UOW-011-1

**Exact Action:**
Add SellerBadge to the listings/sales tables on card detail page:

1. Update API response type to include seller fields
2. Add SellerBadge column to listings table
3. Add SellerBadge column to sales history table

**Files to modify:**
- `frontend/app/routes/cards.$cardId.tsx`
- `frontend/app/types/api.ts` (if exists)

**Acceptance Checks:**
- [ ] Seller badge appears in listings table
- [ ] Seller badge appears in sales table
- [ ] Unknown sellers show gray badge
- [ ] Responsive on mobile

---

### UOW-011-3: Add Top Sellers Widget (Optional)
**Type:** frontend
**Estimate:** 1.5 hours
**Dependencies:** None (parallel with UOW-011-2)

**Exact Action:**
Create top sellers widget for market overview page:

1. Add API endpoint `/api/v1/market/top-sellers` (or use existing stats endpoint)
2. Create TopSellers component
3. Add to market page sidebar/section

**Acceptance Checks:**
- [ ] Shows top 10 sellers by volume
- [ ] Displays sale count per seller
- [ ] Updates with selected time range

---

## Testing Plan

### Manual Testing
1. Navigate to card detail page
2. Verify seller badges appear on listings
3. Verify color coding matches thresholds
4. Test with cards that have "seller_unknown" listings
5. Test mobile responsiveness

### Visual Regression
- Screenshot comparison before/after for card detail page

---

## Done-When
- [ ] SellerBadge component created and exported
- [ ] Card detail page shows seller info on all listings
- [ ] Color coding implemented for reputation thresholds
- [ ] Unknown sellers handled gracefully
- [ ] Mobile responsive
- [ ] No TypeScript errors

---

## Notes
- Seller data coverage is currently ~60% (backfill in progress)
- Historical listings (25%) marked as "seller_unknown"
- New scrapes automatically capture seller data
