/**
 * ProductListItem - TCGPlayer-style horizontal product card
 *
 * Layout:
 * [Image] | [Name, Set, Rarity] | [Listings Count] | [Price] | [Market Price]
 */

import { Link } from '@tanstack/react-router'
import { cn } from '@/lib/utils'
import { RarityBadge } from './rarity-badge'

export type ProductListItemProps = {
  id: number
  slug?: string
  name: string
  setName?: string
  cardNumber?: string
  rarity?: string
  price?: number | null
  marketPrice?: number | null
  listingsCount?: number | null
  imageUrl?: string | null
  productType?: string
  className?: string
}

export function ProductListItem({
  id,
  slug,
  name,
  setName,
  cardNumber,
  rarity,
  price,
  marketPrice,
  listingsCount,
  imageUrl,
  productType,
  className,
}: ProductListItemProps) {
  const displayPrice = price ?? marketPrice
  const hasListings = listingsCount != null && listingsCount > 0

  return (
    <Link
      to="/cards/$cardId"
      params={{ cardId: slug || String(id) }}
      className={cn(
        "flex items-center gap-4 p-3 rounded-lg border border-border bg-card",
        "hover:border-primary/50 hover:bg-muted/30 transition-all",
        "group",
        className
      )}
    >
      {/* Card Image */}
      <div className="shrink-0 w-16 h-[88px] rounded overflow-hidden bg-muted border border-border">
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={name}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-muted-foreground">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
        )}
      </div>

      {/* Card Info */}
      <div className="flex-1 min-w-0">
        <h3 className="font-bold text-sm group-hover:text-primary transition-colors truncate">
          {name}
        </h3>
        <div className="text-xs text-muted-foreground mt-0.5">
          {setName && <span>{setName}</span>}
          {cardNumber && <span>, #{cardNumber}</span>}
        </div>
        {rarity && (
          <RarityBadge rarity={rarity} size="sm" className="mt-1" />
        )}
        {productType && productType !== 'Single' && (
          <span className="inline-block ml-2 text-[10px] font-bold uppercase text-cyan-400">
            {productType}
          </span>
        )}
      </div>

      {/* Listings Count */}
      <div className="hidden sm:block text-right shrink-0 min-w-[100px]">
        {hasListings ? (
          <div className="text-xs text-muted-foreground">
            {listingsCount} listings from
          </div>
        ) : (
          <div className="text-xs text-muted-foreground/50">
            No listings
          </div>
        )}
      </div>

      {/* Price Section */}
      <div className="text-right shrink-0 min-w-[80px]">
        {displayPrice != null && displayPrice > 0 ? (
          <>
            <div className="text-lg font-bold text-brand-300">
              ${displayPrice.toFixed(2)}
            </div>
            {marketPrice != null && marketPrice !== price && (
              <div className="text-[10px] text-muted-foreground">
                Market: <span className="text-primary">${marketPrice.toFixed(2)}</span>
              </div>
            )}
          </>
        ) : (
          <div className="text-sm text-muted-foreground">—</div>
        )}
      </div>
    </Link>
  )
}

/**
 * Skeleton loader for ProductListItem
 */
export function ProductListItemSkeleton() {
  return (
    <div className="flex items-center gap-4 p-3 rounded-lg border border-border bg-card animate-pulse">
      <div className="shrink-0 w-16 h-[88px] rounded bg-muted" />
      <div className="flex-1 min-w-0 space-y-2">
        <div className="h-4 w-32 bg-muted rounded" />
        <div className="h-3 w-24 bg-muted rounded" />
        <div className="h-3 w-16 bg-muted rounded" />
      </div>
      <div className="hidden sm:block w-24 h-4 bg-muted rounded" />
      <div className="w-16 h-6 bg-muted rounded" />
    </div>
  )
}
