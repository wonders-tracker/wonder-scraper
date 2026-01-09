/**
 * ProductCard - Consistent card component for product listings
 *
 * A reusable card component that ensures consistent sizing across all
 * card grids and carousels. Prevents layout shift from varying content.
 *
 * Features:
 * - Fixed dimensions for consistent grid layouts
 * - Image with fixed aspect ratio
 * - Text truncation with consistent height
 * - Hover animations
 * - Rarity and product type badges
 * - Accessible link behavior
 */

import { Link, useNavigate } from '@tanstack/react-router'
import { cn } from '@/lib/utils'
import { formatPrice } from '@/lib/formatters'
import { Package } from 'lucide-react'
import { useState } from 'react'

// Clickable filter chip - navigates to browse with filter
function FilterChip({
  label,
  filterKey,
  filterValue,
  colorClass,
}: {
  label: string
  filterKey: 'rarity' | 'productType' | 'treatment' | 'set'
  filterValue: string
  colorClass?: string
}) {
  const navigate = useNavigate()

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    navigate({
      to: '/browse',
      search: { [filterKey]: filterValue },
    })
  }

  return (
    <button
      onClick={handleClick}
      className={cn(
        'font-medium hover:underline focus:outline-none focus-visible:underline',
        colorClass
      )}
      title={`Browse all ${filterValue}`}
    >
      {label}
    </button>
  )
}

// Rarity colors
const RARITY_COLORS: Record<string, string> = {
  mythic: 'text-amber-400',
  legendary: 'text-orange-400',
  epic: 'text-purple-400',
  rare: 'text-blue-400',
  uncommon: 'text-green-400',
  common: 'text-zinc-400',
}

export type ProductCardProps = {
  id: number
  name: string
  slug?: string
  treatment?: string
  /** Set name (e.g., "Alpha") */
  setName?: string | null
  /** Floor price or lowest sale price */
  price?: number | null
  /** Number of active listings */
  listingsCount?: number | null
  /** Card image URL */
  imageUrl?: string | null
  /** Rarity name (Mythic, Legendary, etc) */
  rarity?: string | null
  /** Product type (Single, Box, Pack, etc) */
  productType?: string | null
  /** Card size variant */
  size?: 'sm' | 'md'
  /** Show "Buy Now" badge for hot deals */
  showBuyNow?: boolean
  /** Deal discount percentage (negative = below market) */
  dealPercent?: number | null
  /** Additional className */
  className?: string
}

/**
 * Fixed-dimension product card for consistent grid layouts
 */
export function ProductCard({
  id,
  name,
  setName,
  price,
  listingsCount,
  imageUrl,
  rarity,
  productType,
  size = 'sm',
  showBuyNow = false,
  dealPercent,
  className,
}: ProductCardProps) {
  const [imageError, setImageError] = useState(false)
  const hasImage = !!imageUrl && !imageError

  // Size variants - slightly wider to fit more text
  const sizeClasses = {
    sm: 'w-[160px] sm:w-[180px]',
    md: 'w-[180px] sm:w-[200px]',
  }

  // Get rarity color
  const rarityColor = rarity ? RARITY_COLORS[rarity.toLowerCase()] || 'text-zinc-400' : undefined

  // Show product type only if not Single
  const showProductType = productType && productType !== 'Single'

  // Show deal badge if discount is significant (more than 5% below market)
  const showDealBadge = dealPercent != null && dealPercent <= -5

  return (
    <Link
      to="/cards/$cardId"
      params={{ cardId: String(id) }}
      className={cn(
        // Fixed width based on size
        sizeClasses[size],
        'flex flex-col flex-shrink-0',
        // Card styling
        'bg-card border border-border rounded-lg overflow-hidden',
        // Hover effects
        'hover:border-brand-500/50 hover:shadow-lg hover:shadow-brand-500/10',
        'transition-all duration-200',
        // Focus styling
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500',
        'focus-visible:ring-offset-2 focus-visible:ring-offset-background',
        'group',
        className
      )}
    >
      {/* Card Image - Fixed aspect ratio */}
      <div className="aspect-[2.5/3.5] bg-muted relative overflow-hidden flex-shrink-0">
        {hasImage ? (
          <img
            src={imageUrl!}
            alt={name}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-muted-foreground">
            <Package className="w-8 h-8" />
          </div>
        )}

        {/* Listings count badge - top right */}
        {listingsCount != null && listingsCount > 0 && (
          <div
            className="absolute top-1.5 right-1.5 min-w-[24px] h-6 px-2 rounded-full bg-card border border-border flex items-center justify-center"
            title={`${listingsCount} listed`}
          >
            <span className="text-xs font-bold text-foreground tabular-nums">
              {listingsCount > 99 ? '99+' : listingsCount}
            </span>
          </div>
        )}

        {/* Product type badge - top left (only for non-Singles) */}
        {showProductType && (
          <div className="absolute top-1.5 left-1.5 px-2 py-0.5 rounded bg-black/70 backdrop-blur-sm">
            <span className="text-[10px] font-bold text-white uppercase">{productType}</span>
          </div>
        )}

        {/* Deal badge - bottom left */}
        {showDealBadge && (
          <div className="absolute bottom-1.5 left-1.5 px-2 py-0.5 rounded bg-emerald-600/90 backdrop-blur-sm">
            <span className="text-[10px] font-bold text-white">
              {Math.abs(Math.round(dealPercent!))}% OFF
            </span>
          </div>
        )}
      </div>

      {/* Card Info */}
      <div className="p-2.5 flex flex-col gap-0.5">
        {/* Name */}
        <h4 className="text-sm font-semibold text-foreground line-clamp-2 leading-snug min-h-[36px]">
          {name}
        </h4>

        {/* Price - right after name */}
        <span className="text-lg font-mono font-bold text-brand-300">
          {price != null ? formatPrice(price) : '---'}
        </span>

        {/* Rarity · Set · Type - combined line (clickable to browse) */}
        <div className="flex items-center gap-1 text-xs text-muted-foreground truncate">
          {rarity && (
            <FilterChip
              label={rarity}
              filterKey="rarity"
              filterValue={rarity}
              colorClass={rarityColor}
            />
          )}
          {rarity && setName && <span>·</span>}
          {setName && (
            <FilterChip
              label={setName}
              filterKey="set"
              filterValue={setName}
            />
          )}
          {showProductType && (setName || rarity) && <span>·</span>}
          {showProductType && (
            <FilterChip
              label={productType!}
              filterKey="productType"
              filterValue={productType!}
            />
          )}
        </div>

        {/* Buy Now badge for hot deals - matches PriceBox button style */}
        {showBuyNow && (
          <div className="mt-1.5 py-1.5 px-2 rounded-lg bg-brand-700 text-center">
            <span className="text-xs font-bold text-white uppercase tracking-wide">
              Buy Now
            </span>
          </div>
        )}
      </div>
    </Link>
  )
}

/**
 * Loading skeleton for ProductCard
 */
export function ProductCardSkeleton({
  size = 'sm',
  className,
}: {
  size?: 'sm' | 'md'
  className?: string
}) {
  const sizeClasses = {
    sm: 'w-[160px] sm:w-[180px]',
    md: 'w-[180px] sm:w-[200px]',
  }

  return (
    <div
      className={cn(
        sizeClasses[size],
        'flex-shrink-0 bg-card border border-border rounded-lg overflow-hidden animate-pulse',
        className
      )}
    >
      {/* Image skeleton */}
      <div className="aspect-[2.5/3.5] bg-muted" />

      {/* Text skeleton */}
      <div className="p-2.5 flex flex-col gap-0.5">
        <div className="space-y-1 min-h-[36px]">
          <div className="h-3.5 bg-muted rounded w-full" />
          <div className="h-3.5 bg-muted rounded w-2/3" />
        </div>
        <div className="h-5 bg-muted rounded w-16" />
        <div className="h-3 bg-muted rounded w-24" />
      </div>
    </div>
  )
}
