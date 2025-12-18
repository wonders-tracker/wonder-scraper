# TASK-007: Order Book Depth Chart Component

**Epic:** EPIC-001 Order Book Floor Price Estimation
**Phase:** 3 - Frontend Visualization
**Estimate:** 10-14 hours
**Dependencies:** TASK-005 (API endpoints)

## Objective

Build a React component that visualizes order book depth as a horizontal bar chart, highlighting the deepest bucket (floor estimate).

## Acceptance Criteria

- [ ] Displays price buckets as horizontal bars
- [ ] Bar width proportional to listing count
- [ ] Deepest bucket highlighted with distinct color
- [ ] Shows price range labels and listing counts
- [ ] Responsive on mobile (320px+)
- [ ] Loading and empty states handled
- [ ] Accessible (ARIA labels, keyboard navigation)

## Design

```
Order Book Depth
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
$5-10    ██ (2)
$10-15   ████ (4)
$15-20   ██████ (6)
$20-25   ████████████████████ (12) ← Floor
$25-30   ██████████ (8)
$30-35   ████ (4)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
         ↑ Deepest bucket = estimated floor
```

## Units of Work

### U1: Create Component Skeleton (2h)
**File:** `frontend/app/components/OrderBookDepthChart.tsx`

```typescript
interface BucketInfo {
  min_price: number
  max_price: number
  count: number
  midpoint: number
}

interface OrderBookDepthChartProps {
  buckets: BucketInfo[]
  deepestBucket: BucketInfo
  floorEstimate: number
  confidence: number
  isLoading?: boolean
}

export function OrderBookDepthChart({
  buckets,
  deepestBucket,
  floorEstimate,
  confidence,
  isLoading = false
}: OrderBookDepthChartProps) {
  // ...
}
```

### U2: Implement Bar Chart with Recharts (4h)
- Use `BarChart` from recharts (already in project)
- Horizontal layout (`layout="vertical"`)
- Price range on Y-axis
- Listing count determines bar width
- Custom tooltip showing price range and count

```typescript
<ResponsiveContainer width="100%" height={buckets.length * 40}>
  <BarChart
    data={buckets}
    layout="vertical"
    margin={{ top: 10, right: 30, left: 60, bottom: 10 }}
  >
    <XAxis type="number" />
    <YAxis
      dataKey="label"
      type="category"
      tick={{ fontSize: 11 }}
    />
    <Bar
      dataKey="count"
      fill="#7dd3a8"
      radius={[0, 4, 4, 0]}
    />
  </BarChart>
</ResponsiveContainer>
```

### U3: Add Deepest Bucket Highlighting (2h)
- Custom cell renderer to highlight deepest bucket
- Distinct color (brand green vs muted gray)
- Add "← Floor" label next to deepest bar
- Glow effect on deepest bucket

```typescript
<Bar dataKey="count">
  {buckets.map((bucket, index) => (
    <Cell
      key={index}
      fill={isDeepest(bucket) ? '#7dd3a8' : '#4a4a4a'}
      stroke={isDeepest(bucket) ? '#7dd3a8' : 'none'}
      strokeWidth={isDeepest(bucket) ? 2 : 0}
    />
  ))}
</Bar>
```

### U4: Implement Responsive Design (3h)
- Desktop: Full horizontal bars with labels
- Tablet: Slightly compressed
- Mobile (<768px): Stacked vertical layout
- Use CSS media queries or Tailwind breakpoints
- Test on 320px, 768px, 1024px viewports

### U5: Add Loading and Empty States (2h)
- Loading: Skeleton bars with pulse animation
- Empty: "No active listings" message with icon
- Error: "Unable to load order book" with retry button

```typescript
if (isLoading) {
  return <OrderBookSkeleton />
}

if (!buckets || buckets.length === 0) {
  return (
    <div className="text-center py-8 text-muted-foreground">
      <Package className="w-8 h-8 mx-auto mb-2 opacity-50" />
      <p>No active listings</p>
    </div>
  )
}
```

### U6: Add Accessibility (1h)
- ARIA labels for chart and bars
- `role="img"` with descriptive `aria-label`
- Keyboard-navigable tooltip
- Screen reader description of floor estimate

## Component API

```typescript
// Props
interface OrderBookDepthChartProps {
  buckets: BucketInfo[]
  deepestBucket: BucketInfo
  floorEstimate: number
  confidence: number
  totalListings: number
  isLoading?: boolean
  className?: string
}

// Usage
<OrderBookDepthChart
  buckets={orderBook.buckets}
  deepestBucket={orderBook.deepest_bucket}
  floorEstimate={orderBook.floor_estimate}
  confidence={orderBook.confidence}
  totalListings={orderBook.total_listings}
/>
```

## Files Changed

- **New:** `frontend/app/components/OrderBookDepthChart.tsx`
- **New:** `frontend/app/components/OrderBookSkeleton.tsx`

## Testing

Manual tests:
- [ ] 5 buckets - normal display
- [ ] 20 buckets - scrollable or paginated
- [ ] 1 bucket - single bar displays
- [ ] Mobile viewport - responsive layout
- [ ] Deepest bucket highlighted
- [ ] Tooltip shows on hover

## Notes

- Use existing color palette from `frontend/app/globals.css`
- Match style of existing charts (PriceHistoryChart)
- Consider dark mode compatibility
