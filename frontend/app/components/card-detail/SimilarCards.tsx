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
import { cn } from '@/lib/utils'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { ProductCard, ProductCardSkeleton } from '../ui/product-card'

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
              <ProductCardSkeleton key={i} />
            ))
          ) : (
            // Actual cards
            cards.map((card) => (
              <div key={card.id} className="snap-start" role="listitem">
                <ProductCard
                  id={card.id}
                  name={card.name}
                  treatment={showTreatment ? card.treatment : undefined}
                  price={card.floor_price ?? card.lowest_ask}
                  listingsCount={card.inventory}
                  imageUrl={card.image_url}
                />
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
          <ProductCardSkeleton key={i} />
        ))}
      </div>
      <span className="sr-only">Loading similar cards...</span>
    </div>
  )
}
