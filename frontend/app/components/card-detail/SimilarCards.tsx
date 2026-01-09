/**
 * SimilarCards - Horizontal carousel for related cards
 *
 * Displays variants (same card, different treatments) and similar cards
 * (same rarity from same set) in a scrollable carousel.
 *
 * Features:
 * - CSS scroll-snap for smooth snapping
 * - Arrow navigation buttons
 * - Touch swipe support on mobile
 * - Card shows: image, name, price, listings count
 * - Click navigates to card detail page
 *
 * @see tasks.json E5-U1
 */

import { useRef, useState, useEffect, useCallback } from 'react'
import { Link } from '@tanstack/react-router'
import { cn } from '@/lib/utils'
import { formatPrice } from '@/lib/formatters'
import { ChevronLeft, ChevronRight, Package } from 'lucide-react'
import { TreatmentBadge } from '../TreatmentBadge'

export type SimilarCard = {
  id: number
  name: string
  slug?: string
  treatment?: string
  floor_price?: number | null
  lowest_ask?: number | null
  inventory?: number | null
  image_url?: string | null
  rarity_name?: string
  set_name?: string
}

export type SimilarCardsProps = {
  /** Title for the section */
  title: string
  /** Array of similar/variant cards */
  cards: SimilarCard[]
  /** Whether data is loading */
  isLoading?: boolean
  /** Additional className */
  className?: string
  /** Show treatment badge on cards */
  showTreatment?: boolean
}

/**
 * Individual card in the carousel
 */
function CarouselCard({
  card,
  showTreatment = false,
}: {
  card: SimilarCard
  showTreatment?: boolean
}) {
  const price = card.floor_price ?? card.lowest_ask
  const hasImage = !!card.image_url

  return (
    <Link
      to="/cards/$cardId"
      params={{ cardId: String(card.id) }}
      className={cn(
        'flex-shrink-0 w-[140px] sm:w-[160px] group',
        'bg-card border border-border rounded-lg overflow-hidden',
        'hover:border-brand-500/50 hover:shadow-lg hover:shadow-brand-500/10',
        'transition-all duration-200',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background'
      )}
    >
      {/* Card Image */}
      <div className="aspect-[2.5/3.5] bg-muted relative overflow-hidden">
        {hasImage ? (
          <img
            src={card.image_url!}
            alt={card.name}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-muted-foreground">
            <Package className="w-8 h-8" />
          </div>
        )}
        {/* Treatment badge overlay */}
        {showTreatment && card.treatment && (
          <div className="absolute bottom-1 left-1">
            <TreatmentBadge treatment={card.treatment} size="xs" />
          </div>
        )}
      </div>

      {/* Card Info */}
      <div className="p-2 space-y-1">
        <h4 className="text-xs font-medium text-foreground line-clamp-2 leading-tight min-h-[2rem]">
          {card.name}
        </h4>
        <div className="flex items-baseline justify-between gap-1">
          <span className="text-sm font-mono font-bold text-brand-300">
            {price != null ? formatPrice(price) : '---'}
          </span>
          {card.inventory != null && card.inventory > 0 && (
            <span className="text-[10px] text-muted-foreground">
              {card.inventory} listed
            </span>
          )}
        </div>
      </div>
    </Link>
  )
}

/**
 * Loading skeleton for carousel cards
 */
function CarouselCardSkeleton() {
  return (
    <div className="flex-shrink-0 w-[140px] sm:w-[160px] bg-card border border-border rounded-lg overflow-hidden animate-pulse">
      <div className="aspect-[2.5/3.5] bg-muted" />
      <div className="p-2 space-y-2">
        <div className="h-3 bg-muted rounded w-full" />
        <div className="h-3 bg-muted rounded w-2/3" />
        <div className="flex justify-between">
          <div className="h-4 bg-muted rounded w-14" />
          <div className="h-3 bg-muted rounded w-10" />
        </div>
      </div>
    </div>
  )
}

export function SimilarCards({
  title,
  cards,
  isLoading = false,
  className,
  showTreatment = false,
}: SimilarCardsProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [canScrollLeft, setCanScrollLeft] = useState(false)
  const [canScrollRight, setCanScrollRight] = useState(false)

  // Check scroll position to show/hide arrows
  const checkScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return

    const { scrollLeft, scrollWidth, clientWidth } = el
    setCanScrollLeft(scrollLeft > 0)
    setCanScrollRight(scrollLeft + clientWidth < scrollWidth - 1)
  }, [])

  // Set up scroll listeners
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return

    checkScroll()
    el.addEventListener('scroll', checkScroll, { passive: true })
    window.addEventListener('resize', checkScroll)

    return () => {
      el.removeEventListener('scroll', checkScroll)
      window.removeEventListener('resize', checkScroll)
    }
  }, [checkScroll, cards])

  // Scroll by one "page" (container width minus some overlap)
  const scroll = (direction: 'left' | 'right') => {
    const el = scrollRef.current
    if (!el) return

    const scrollAmount = el.clientWidth - 80 // Keep some overlap
    el.scrollBy({
      left: direction === 'left' ? -scrollAmount : scrollAmount,
      behavior: 'smooth',
    })
  }

  // Don't render if no cards and not loading
  if (!isLoading && cards.length === 0) {
    return null
  }

  return (
    <div className={cn('relative', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-bold uppercase tracking-widest text-foreground">
          {title}
        </h3>
        {/* Desktop navigation arrows */}
        <div className="hidden sm:flex items-center gap-1">
          <button
            onClick={() => scroll('left')}
            disabled={!canScrollLeft}
            className={cn(
              'p-1.5 rounded border border-border bg-card',
              'hover:bg-muted transition-colors',
              'disabled:opacity-30 disabled:cursor-not-allowed',
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500'
            )}
            aria-label="Scroll left"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button
            onClick={() => scroll('right')}
            disabled={!canScrollRight}
            className={cn(
              'p-1.5 rounded border border-border bg-card',
              'hover:bg-muted transition-colors',
              'disabled:opacity-30 disabled:cursor-not-allowed',
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500'
            )}
            aria-label="Scroll right"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Carousel container */}
      <div className="relative">
        {/* Gradient fade edges (desktop only) */}
        {canScrollLeft && (
          <div
            className="hidden sm:block absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-background to-transparent z-10 pointer-events-none"
            aria-hidden="true"
          />
        )}
        {canScrollRight && (
          <div
            className="hidden sm:block absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-background to-transparent z-10 pointer-events-none"
            aria-hidden="true"
          />
        )}

        {/* Scrollable row */}
        <div
          ref={scrollRef}
          className={cn(
            'flex gap-3 overflow-x-auto',
            'scroll-smooth snap-x snap-mandatory',
            'pb-2', // Padding for shadow overflow
            // Hide scrollbar on all browsers
            'scrollbar-none',
            '[&::-webkit-scrollbar]:hidden',
            '[-ms-overflow-style:none]',
            '[scrollbar-width:none]'
          )}
          role="list"
          aria-label={title}
        >
          {isLoading ? (
            // Loading skeletons
            Array.from({ length: 6 }).map((_, i) => (
              <CarouselCardSkeleton key={i} />
            ))
          ) : (
            // Actual cards
            cards.map((card) => (
              <div key={card.id} className="snap-start" role="listitem">
                <CarouselCard card={card} showTreatment={showTreatment} />
              </div>
            ))
          )}
        </div>
      </div>

      {/* Mobile swipe hint */}
      <div className="sm:hidden text-center mt-2">
        <span className="text-[10px] text-muted-foreground">
          ← Swipe to see more →
        </span>
      </div>
    </div>
  )
}

/**
 * Loading skeleton for entire SimilarCards section
 */
export function SimilarCardsSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn('animate-pulse', className)}
      role="status"
      aria-busy="true"
      aria-label="Loading similar cards"
    >
      <div className="flex items-center justify-between mb-3">
        <div className="h-4 w-32 bg-muted rounded" />
        <div className="hidden sm:flex gap-1">
          <div className="w-8 h-8 bg-muted rounded" />
          <div className="w-8 h-8 bg-muted rounded" />
        </div>
      </div>
      <div className="flex gap-3 overflow-hidden">
        {Array.from({ length: 6 }).map((_, i) => (
          <CarouselCardSkeleton key={i} />
        ))}
      </div>
      <span className="sr-only">Loading similar cards...</span>
    </div>
  )
}
