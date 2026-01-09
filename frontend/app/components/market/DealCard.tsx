/**
 * DealCard - Minimal card for displaying active deals below floor price
 */

import { cn } from '@/lib/utils'
import { ExternalLink } from 'lucide-react'

type DealCardProps = {
  cardName: string
  cardImageUrl?: string | null
  treatment?: string | null
  price: number
  floorPrice: number
  dealPercent: number
  platform: string
  listingFormat?: 'auction' | 'buy_it_now' | 'best_offer' | null
  bidCount?: number
  isStale?: boolean
  url: string
  onLinkClick?: () => void
  className?: string
}

export function DealCard({
  cardName,
  cardImageUrl,
  treatment,
  price,
  floorPrice,
  dealPercent,
  platform,
  listingFormat,
  bidCount,
  isStale,
  url,
  onLinkClick,
  className,
}: DealCardProps) {
  const isAuction = listingFormat === 'auction' || (bidCount && bidCount > 0)
  const savings = floorPrice - price

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={onLinkClick}
      className={cn(
        'group relative block bg-card rounded-xl overflow-hidden',
        'border border-border hover:border-emerald-500/40 transition-all duration-200',
        'hover:shadow-lg hover:shadow-emerald-500/5',
        isStale && 'opacity-50',
        className
      )}
    >
      {/* Card Image */}
      <div className="relative aspect-[3/4] bg-muted">
        {cardImageUrl ? (
          <img
            src={cardImageUrl}
            alt={cardName}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-muted-foreground/30">
            <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
        )}

        {/* Discount Badge - Top Left */}
        <div className={cn(
          'absolute top-2 left-2 px-2 py-1 rounded-md text-xs font-bold',
          isAuction
            ? 'bg-amber-500 text-black'
            : 'bg-emerald-500 text-black'
        )}>
          {Math.round(dealPercent)}% OFF
        </div>

        {/* Platform Badge - Top Right */}
        <div className="absolute top-2 right-2 px-2 py-1 rounded-md bg-black/60 text-[10px] text-white/80 uppercase tracking-wide">
          {platform}
        </div>

        {/* Hover overlay */}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
          <ExternalLink className="w-6 h-6 text-white opacity-0 group-hover:opacity-100 transition-opacity drop-shadow-lg" />
        </div>
      </div>

      {/* Card Info */}
      <div className="p-3">
        {/* Name + Treatment */}
        <h4 className="text-sm font-medium truncate" title={cardName}>
          {cardName}
        </h4>
        {treatment && (
          <span className="text-[11px] text-muted-foreground">
            {treatment}
          </span>
        )}

        {/* Pricing */}
        <div className="mt-2 flex items-baseline justify-between gap-2">
          <div className="flex items-baseline gap-2">
            <span className="text-lg font-mono font-bold text-emerald-400">
              ${price.toFixed(2)}
            </span>
            <span className="text-xs text-muted-foreground line-through">
              ${floorPrice.toFixed(2)}
            </span>
          </div>
          <span className="text-[11px] text-emerald-400/80">
            −${savings.toFixed(2)}
          </span>
        </div>

        {/* Auction indicator */}
        {isAuction && bidCount ? (
          <div className="mt-1.5 text-[10px] text-amber-400">
            {bidCount} bid{bidCount !== 1 ? 's' : ''}
          </div>
        ) : null}
      </div>
    </a>
  )
}
