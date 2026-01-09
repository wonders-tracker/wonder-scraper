/**
 * PriceBox - Right column pricing display and actions
 *
 * Enhanced with treatment selector dropdown, price source indicators,
 * shipping estimates, seller count badges, portfolio/watchlist actions,
 * and price comparison by platform.
 *
 * @see tasks.json E2-U1, E2-U3, E2-U4
 */

import { ReactNode, useMemo, useState } from 'react'
import { cn } from '@/lib/utils'
import { Tooltip } from '../ui/tooltip'
import { SimpleDropdown } from '../ui/dropdown'
import { Button } from '../ui/button'
import { TreatmentBadge, getTreatmentTextColor } from '../TreatmentBadge'
import { PlatformIcon } from '../ui/platform-badge'
import {
  ChevronDown,
  ExternalLink,
  Info,
  Truck,
  Users,
  TrendingUp,
  Package,
  Heart,
  Plus,
  Check,
  Clock,
  Bell
} from 'lucide-react'


/** Treatment option for the dropdown selector */
export type TreatmentOption = {
  value: string
  label: string
  floorPrice?: number
  listingCount?: number
  disabled?: boolean
}

/** Price source types */
export type PriceSource = 'floor' | 'fmp' | 'lowest_ask' | 'recent_sale'

/** Platform price comparison data */
export type PlatformPrice = {
  platform: 'ebay' | 'blokpax'
  lowestPrice: number
  listingCount: number
  lastUpdated?: string
  searchUrl?: string
}

/** Product details for display */
export type ProductDetails = {
  cardNumber?: string
  rarity?: string
  cardType?: string
  orbital?: string
  orbitalColor?: string
  setName?: string
}

export type PriceBoxProps = {
  card: {
    id: number
    name: string
    floor_price?: number
    lowest_ask?: number
    latest_price?: number
    fair_market_price?: number
    vwap?: number
    volume_30d?: number
    max_price?: number
    inventory?: number
    seller_count?: number
    floor_by_variant?: Record<string, number>
    lowest_ask_by_variant?: Record<string, number>
    /** Product type - Single, Box, Pack, Bundle, etc. */
    product_type?: string
  }
  /** Currently selected treatment filter */
  treatmentFilter: string
  /** Callback when treatment filter changes */
  onTreatmentChange?: (treatment: string) => void
  /** Available treatment options for the dropdown */
  treatmentOptions?: TreatmentOption[]
  /** Fair market price from pricing API */
  pricingFMP?: number
  /** Whether user is logged in */
  isLoggedIn: boolean
  /** Callback for opening portfolio modal */
  onAddToPortfolio: () => void
  /** Persistent added state: 'owned' | 'wanted' | null */
  addedToPortfolio?: 'owned' | 'wanted' | null
  /** Callback for viewing listings */
  onViewListings?: () => void
  /** Slot for MetaVote component (only for singles) */
  metaVoteSlot?: ReactNode
  /** Whether pricing data is loading */
  isLoading?: boolean
  /** Additional className */
  className?: string
  /** Whether card is in user's watchlist */
  isInWatchlist?: boolean
  /** Callback for toggling watchlist */
  onToggleWatchlist?: () => void
  /** Whether watchlist action is in progress */
  watchlistLoading?: boolean
  /** Price comparison by platform */
  platformPrices?: PlatformPrice[]
  /** Product details for display in compact form */
  productDetails?: ProductDetails
  /** Callback for opening price alert modal */
  onSetPriceAlert?: () => void
  /** Volatility level: 0-1 scale (0=low, 0.5=med, 1=high) */
  volatility?: number
  /** Filtered 30D volume (overrides card.volume_30d when treatment selected) */
  filteredVolume30d?: number
  /** Filtered max price (overrides card.max_price when treatment selected) */
  filteredMaxPrice?: number | null
  /** Filtered seller count (overrides card.seller_count when treatment selected) */
  filteredSellerCount?: number
  /** Filtered listings count (overrides card.inventory when treatment selected) */
  filteredListingsCount?: number
  /** Lowest buy now price for the CTA button */
  lowestBuyNowPrice?: number | null
  /** Buy now URL (eBay, Blokpax, etc.) */
  buyNowUrl?: string
  /** Filtered market price/FMP (overrides pricingFMP when treatment selected) */
  filteredMarketPrice?: number | null
  /** Highest ask price (fallback for highest sale) */
  highestAsk?: number | null
  /** Price range [min, max] from active listings (fallback for market price) */
  priceRange?: [number, number] | null
  /** Sales price range [min, max] from sold listings - for NFT items */
  salesPriceRange?: [number, number] | null
  /** Number of sales - used to determine single price vs range display */
  salesCount?: number
}

export function PriceBox({
  card,
  treatmentFilter,
  onTreatmentChange,
  treatmentOptions = [],
  pricingFMP,
  isLoggedIn,
  onAddToPortfolio,
  addedToPortfolio,
  onViewListings,
  metaVoteSlot,
  isLoading = false,
  className,
  isInWatchlist = false,
  onToggleWatchlist,
  watchlistLoading = false,
  platformPrices = [],
  productDetails,
  onSetPriceAlert,
  volatility,
  filteredVolume30d,
  filteredMaxPrice,
  filteredSellerCount,
  filteredListingsCount,
  lowestBuyNowPrice,
  buyNowUrl,
  filteredMarketPrice,
  highestAsk,
  priceRange,
  salesPriceRange,
  salesCount = 0
}: PriceBoxProps) {
  // Track action feedback states
  const [showAddedFeedback, setShowAddedFeedback] = useState(false)

  // Handle add to portfolio with feedback
  const handleAddToPortfolio = () => {
    onAddToPortfolio()
    setShowAddedFeedback(true)
    setTimeout(() => setShowAddedFeedback(false), 2000)
  }

  // Handle watchlist toggle with login check
  const handleWatchlistToggle = () => {
    if (!isLoggedIn) {
      // Could trigger login modal here
      return
    }
    onToggleWatchlist?.()
  }
  // Get variant-specific price and determine source
  const priceInfo = useMemo(() => {
    const variantKey = treatmentFilter === 'all' ? null :
      treatmentFilter.startsWith('subtype:') ? treatmentFilter.replace('subtype:', '') : treatmentFilter
    const variantFloor = variantKey ? card.floor_by_variant?.[variantKey] : null
    const variantAsk = variantKey ? card.lowest_ask_by_variant?.[variantKey] : null

    // Determine price and source
    if (variantFloor) {
      return { price: variantFloor, source: 'floor' as PriceSource }
    }
    if (variantAsk) {
      return { price: variantAsk, source: 'lowest_ask' as PriceSource }
    }
    if (card.floor_price) {
      return { price: card.floor_price, source: 'floor' as PriceSource }
    }
    if (card.lowest_ask && card.lowest_ask > 0) {
      return { price: card.lowest_ask, source: 'lowest_ask' as PriceSource }
    }
    if (card.latest_price) {
      return { price: card.latest_price, source: 'recent_sale' as PriceSource }
    }
    return { price: null, source: 'floor' as PriceSource }
  }, [treatmentFilter, card])

  // Format treatment options for dropdown
  const dropdownOptions = useMemo(() => {
    if (treatmentOptions.length === 0) {
      return [{ value: 'all', label: 'All Treatments' }]
    }

    return [
      { value: 'all', label: 'All Treatments' },
      ...treatmentOptions.map(opt => ({
        value: opt.value,
        label: opt.floorPrice
          ? `${opt.label} - $${opt.floorPrice.toFixed(2)}`
          : opt.label,
        disabled: opt.disabled
      }))
    ]
  }, [treatmentOptions])

  // Price source label
  const priceSourceLabel = {
    floor: 'Floor Price',
    fmp: 'Market Price',
    lowest_ask: 'Lowest Ask',
    recent_sale: 'Recent Sale'
  }[priceInfo.source]

  // Get treatment display name
  const treatmentDisplayName = treatmentFilter === 'all'
    ? null
    : treatmentFilter.startsWith('subtype:')
      ? treatmentFilter.replace('subtype:', '')
      : treatmentFilter

  // Seller count (use filtered value if available, otherwise card data)
  const sellerCount = filteredSellerCount !== undefined
    ? filteredSellerCount
    : (card.seller_count || Math.min(card.inventory || 0, 50))

  // Listings count (use filtered value if available)
  const listingsCount = filteredListingsCount !== undefined
    ? filteredListingsCount
    : (card.inventory || 0)

  // Volume 30D (use filtered value if available)
  const volume30d = filteredVolume30d !== undefined
    ? filteredVolume30d
    : (card.volume_30d || 0)

  // Max price (use filtered value if available)
  const maxPrice = filteredMaxPrice !== undefined
    ? filteredMaxPrice
    : card.max_price

  // Market price/FMP (use filtered value if available)
  const marketPrice = filteredMarketPrice !== undefined
    ? filteredMarketPrice
    : (pricingFMP || card.vwap)

  // Detect sealed/non-single products for conditional UI
  const isSealed = card.product_type && card.product_type !== 'Single'

  // For sealed products with no 30D sales but has max_price, they have historical sales
  const hasHistoricalSales = volume30d === 0 && maxPrice && maxPrice > 0

  return (
    <div className={cn(
      "border border-border rounded-lg bg-card",
      "w-full flex flex-col",
      "min-w-[280px]",
      className
    )}>
      {/* Price Section - flex-1 to fill available space */}
      <div className="p-4 space-y-4 flex-1">
        {/* Main Price Display with Treatment Selector in upper right */}
        <div>
          <div className="flex items-start justify-between gap-4 mb-2">
            <div className="flex items-center gap-2">
              <span className="text-xs md:text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                {priceSourceLabel}
              </span>
              {treatmentDisplayName && (
              <span className={cn(
                "text-xs md:text-sm font-bold uppercase",
                getTreatmentTextColor(treatmentDisplayName)
              )}>
                ({treatmentDisplayName})
              </span>
            )}
            <Tooltip content={`Price based on ${priceSourceLabel.toLowerCase()} across all active listings`}>
              <span role="img" aria-label="More information about price source">
                <Info className="w-3 h-3 text-muted-foreground cursor-help" aria-hidden="true" />
              </span>
            </Tooltip>
            </div>

            {/* Treatment Selector - Upper Right */}
            {treatmentOptions.length > 0 && onTreatmentChange && (
              <SimpleDropdown
                value={treatmentFilter}
                onChange={onTreatmentChange}
                options={dropdownOptions}
                placeholder="All Treatments"
                size="md"
                className="min-w-[160px]"
                triggerClassName="rounded-lg bg-muted/50 border-border/50 hover:bg-muted font-medium"
              />
            )}
          </div>

          {isLoading ? (
            <div className="h-12 w-32 bg-muted animate-pulse rounded" />
          ) : (
            <div className="text-4xl md:text-5xl font-mono font-bold tracking-tight">
              {priceInfo.price !== null ? (
                `$${priceInfo.price.toFixed(2)}`
              ) : (
                <span className="text-muted-foreground">---</span>
              )}
            </div>
          )}
        </div>

        {/* Shipping Estimate */}
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Truck className="w-4 h-4" aria-hidden="true" />
          <span>+ shipping varies</span>
          <Tooltip content="Shipping costs vary by seller and location. Check individual listings for exact rates.">
            <span role="img" aria-label="More information about shipping">
              <Info className="w-3 h-3 cursor-help" aria-hidden="true" />
            </span>
          </Tooltip>
        </div>

        {/* Secondary Metrics - Horizontal on tablet+, 2x2 grid on mobile */}
        <div className="pt-3 border-t border-border/50">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
            {/* Market Price or Price Range - contextual for sealed products */}
            <div>
              <div className="flex items-center gap-1 mb-1">
                <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
                  {marketPrice ? 'Market Price'
                    : salesPriceRange ? 'Sales Range'
                    : salesCount === 1 ? 'Last Sale'
                    : priceRange ? 'Listing Range'
                    : isSealed ? 'Listing Price'
                    : 'Market Price'}
                </span>
                <Tooltip content={
                  marketPrice ? "Weighted algorithm based on recent sales"
                    : salesPriceRange ? `Price range from ${salesCount} sales`
                    : salesCount === 1 ? "Price from single recorded sale"
                    : priceRange ? "Price range from active listings"
                    : isSealed ? "Based on current listings (no sales data yet)"
                    : "Price range from active listings"
                }>
                  <Info className="w-3 h-3 text-muted-foreground cursor-help" aria-hidden="true" />
                </Tooltip>
              </div>
              {isLoading ? (
                <div className="h-5 w-16 bg-muted animate-pulse rounded" />
              ) : isLoggedIn ? (
                <span className={cn(
                  "font-mono font-bold",
                  // Use muted color when showing listing-based price (no sales data)
                  !marketPrice && !salesPriceRange && salesCount === 0 ? "text-muted-foreground" : "text-brand-300"
                )}>
                  {marketPrice ? (
                    `$${marketPrice.toFixed(2)}`
                  ) : salesPriceRange ? (
                    `$${salesPriceRange[0].toFixed(0)}-${salesPriceRange[1].toFixed(0)}`
                  ) : salesCount === 1 && card.latest_price ? (
                    `$${card.latest_price.toFixed(2)}`
                  ) : priceRange ? (
                    `$${priceRange[0].toFixed(0)}-${priceRange[1].toFixed(0)}`
                  ) : isSealed && listingsCount > 0 ? (
                    'See listings'
                  ) : '---'}
                </span>
              ) : (
                <Tooltip content="Log in to see FMP">
                  <span className="font-mono font-bold blur-sm text-brand-300/50 cursor-help">$XX.XX</span>
                </Tooltip>
              )}
            </div>

            {/* 30D Volume - Shows contextual messaging for sealed products */}
            <div>
              <div className="flex items-center gap-1 mb-1">
                <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
                  {volume30d === 0 && isSealed ? 'Sales' : '30D Volume'}
                </span>
                <Tooltip content={
                  volume30d === 0 && isSealed
                    ? "Sealed products often have sparse sales data"
                    : "Number of sales in the last 30 days"
                }>
                  <Info className="w-3 h-3 text-muted-foreground cursor-help" aria-hidden="true" />
                </Tooltip>
              </div>
              {isLoading ? (
                <div className="h-5 w-10 bg-muted animate-pulse rounded" />
              ) : (
                <span className={cn("font-mono font-bold", volume30d === 0 && "text-muted-foreground")}>
                  {volume30d > 0 ? (
                    volume30d.toLocaleString()
                  ) : hasHistoricalSales ? (
                    'Low volume'
                  ) : isSealed ? (
                    'No recorded sales'
                  ) : (
                    'No sales'
                  )}
                </span>
              )}
            </div>

            {/* Highest Sale or Highest Ask - contextual for sealed products */}
            <div>
              <div className="flex items-center gap-1 mb-1">
                <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
                  {maxPrice ? 'Highest Sale'
                    : highestAsk ? 'Highest Ask'
                    : isSealed && listingsCount > 0 ? 'Top Listing'
                    : 'Highest Sale'}
                </span>
                <Tooltip content={
                  maxPrice ? "Highest recorded sale price"
                    : highestAsk ? "Highest current asking price"
                    : isSealed ? "No recorded sales for this product yet"
                    : "Highest recorded sale price"
                }>
                  <Info className="w-3 h-3 text-muted-foreground cursor-help" aria-hidden="true" />
                </Tooltip>
              </div>
              {isLoading ? (
                <div className="h-5 w-16 bg-muted animate-pulse rounded" />
              ) : (
                <span className={cn(
                  "font-mono font-bold",
                  !maxPrice && !highestAsk && "text-muted-foreground"
                )}>
                  {maxPrice ? `$${maxPrice.toFixed(2)}`
                    : highestAsk ? `$${highestAsk.toFixed(2)}`
                    : isSealed ? 'N/A'
                    : '---'}
                </span>
              )}
            </div>

            {/* Volatility - only show if available */}
            {volatility !== undefined && volatility !== null && (
              <div>
                <div className="flex items-center gap-1 mb-1">
                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Volatility</span>
                  <Tooltip content="Measures price stability - how much prices vary over time">
                    <Info className="w-3 h-3 text-muted-foreground cursor-help" aria-hidden="true" />
                  </Tooltip>
                </div>
                {isLoading ? (
                  <div className="h-5 w-20 bg-muted animate-pulse rounded" />
                ) : (
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      "text-sm font-bold",
                      volatility < 0.33 && "text-green-500",
                      volatility >= 0.33 && volatility < 0.66 && "text-yellow-500",
                      volatility >= 0.66 && "text-red-500"
                    )}>
                      {volatility < 0.33 ? 'Low' : volatility < 0.66 ? 'Medium' : 'High'}
                    </span>
                    {/* Mini volatility bar */}
                    <div className="relative w-12 h-1.5 bg-muted rounded-full overflow-hidden">
                      <div
                        className={cn(
                          "absolute left-0 top-0 h-full rounded-full",
                          volatility < 0.33 && "bg-green-500",
                          volatility >= 0.33 && volatility < 0.66 && "bg-yellow-500",
                          volatility >= 0.66 && "bg-red-500"
                        )}
                        style={{ width: `${Math.max(volatility * 100, 10)}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Seller Count Badge */}
        <div className="flex items-center gap-3 pt-3 border-t border-border/50">
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-blue-500/10 border border-blue-500/20 rounded-full">
            <Users className="w-3.5 h-3.5 text-blue-400" aria-hidden="true" />
            <span className="text-sm font-medium text-blue-400">
              {sellerCount.toLocaleString()} {sellerCount === 1 ? 'seller' : 'sellers'}
            </span>
          </div>
          <span className="text-sm text-muted-foreground">
            {listingsCount.toLocaleString()} listings
          </span>
        </div>

        {/* Meta Vote Slot */}
        {metaVoteSlot}

        {/* Product Details (compact) */}
        {productDetails && (
          <div className="pt-3 border-t border-border/50">
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2 font-medium">
              Product Details
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
              {productDetails.cardNumber && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Card #</span>
                  <span className="font-mono">{productDetails.cardNumber}</span>
                </div>
              )}
              {productDetails.rarity && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Rarity</span>
                  <span className="font-mono">{productDetails.rarity}</span>
                </div>
              )}
              {productDetails.cardType && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Type</span>
                  <span className="font-mono">{productDetails.cardType}</span>
                </div>
              )}
              {productDetails.orbital && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Orbital</span>
                  <span className="font-mono" style={{ color: productDetails.orbitalColor }}>
                    {productDetails.orbital}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Price Comparison by Platform */}
        {platformPrices.length > 0 && (
          <div className="pt-3 border-t border-border/50">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium">
                Compare Prices
              </span>
              {platformPrices[0]?.lastUpdated && (
                <span className="text-[9px] text-muted-foreground flex items-center gap-1">
                  <Clock className="w-3 h-3" aria-hidden="true" />
                  {platformPrices[0].lastUpdated}
                </span>
              )}
            </div>
            <div className="space-y-2">
              {platformPrices.map((pp) => (
                <a
                  key={pp.platform}
                  href={pp.searchUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between p-2 rounded border border-border/50 hover:border-border hover:bg-muted/30 transition-colors group"
                >
                  <div className="flex items-center gap-2">
                    <PlatformIcon platform={pp.platform} />
                    <span className="text-sm capitalize">{pp.platform}</span>
                    <span className="text-xs text-muted-foreground">
                      ({pp.listingCount} listings)
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold">
                      ${pp.lowestPrice.toFixed(2)}
                    </span>
                    <ExternalLink className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" aria-hidden="true" />
                  </div>
                </a>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Actions - mt-auto to push to bottom */}
      <div className="p-4 border-t border-border space-y-2 mt-auto">
        {/* Portfolio Button */}
        {addedToPortfolio ? (
          <div
            className={cn(
              "w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-bold text-sm uppercase tracking-wide",
              addedToPortfolio === 'wanted'
                ? "bg-pink-500/20 text-pink-500 border border-pink-500/30"
                : "bg-green-500/20 text-green-500 border border-green-500/30"
            )}
          >
            {addedToPortfolio === 'wanted' ? <Heart className="w-4 h-4" /> : <Check className="w-4 h-4" />}
            {addedToPortfolio === 'wanted' ? 'Added to Watchlist' : 'Added to Portfolio'}
          </div>
        ) : (
          <Button
            variant="primary"
            size="lg"
            className={cn(
              "w-full uppercase tracking-wide transition-all",
              showAddedFeedback && "bg-green-600 hover:bg-green-600"
            )}
            onClick={handleAddToPortfolio}
            leftIcon={showAddedFeedback ? <Check className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
          >
            {showAddedFeedback ? 'Added!' : 'Add to Portfolio'}
          </Button>
        )}

        {/* Buy Now CTA */}
        {buyNowUrl ? (
          <a
            href={buyNowUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(
              "flex items-center justify-center gap-2 w-full px-4 py-3",
              "bg-brand-700 hover:bg-brand-800 text-white",
              "rounded-lg font-bold text-sm uppercase tracking-wide",
              "transition-colors"
            )}
          >
            Buy Now {lowestBuyNowPrice ? `from $${lowestBuyNowPrice.toFixed(2)}` : ''}
            <ExternalLink className="w-4 h-4" />
          </a>
        ) : (
          <Button
            variant="outline"
            size="lg"
            className="w-full uppercase tracking-wide"
            onClick={onViewListings}
            rightIcon={<ExternalLink className="w-4 h-4" />}
          >
            View {listingsCount.toLocaleString()} Listings
          </Button>
        )}
      </div>
    </div>
  )
}

/**
 * Loading skeleton for PriceBox
 */
export function PriceBoxSkeleton() {
  return (
    <div className="border border-border rounded-lg bg-card animate-pulse">
      {/* Treatment selector skeleton */}
      <div className="p-4 border-b border-border">
        <div className="h-3 w-24 bg-muted rounded mb-2" />
        <div className="h-9 bg-muted rounded" />
      </div>

      {/* Price section skeleton */}
      <div className="p-4 space-y-4">
        <div>
          <div className="h-3 w-20 bg-muted rounded mb-2" />
          <div className="h-12 w-32 bg-muted rounded" />
        </div>

        <div className="h-4 w-28 bg-muted rounded" />

        {/* Compact metrics row skeleton */}
        <div className="pt-3 border-t border-border/50">
          <div className="flex items-center gap-4">
            <div className="h-5 w-20 bg-muted rounded" />
            <div className="h-5 w-12 bg-muted rounded" />
            <div className="h-5 w-16 bg-muted rounded" />
            <div className="h-5 w-10 bg-muted rounded" />
          </div>
        </div>

        <div className="pt-3 border-t border-border/50">
          <div className="h-8 w-32 bg-muted rounded-full" />
        </div>
      </div>

      {/* Actions skeleton */}
      <div className="p-4 border-t border-border space-y-2">
        <div className="h-10 bg-muted rounded" />
        <div className="h-10 bg-muted rounded" />
      </div>
    </div>
  )
}
