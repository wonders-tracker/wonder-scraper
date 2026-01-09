/**
 * ProductsGallery - Tabbed carousel gallery for home page
 *
 * Displays product cards in a horizontal carousel with tabs:
 * - Best Sellers: sorted by volume (highest sales)
 * - Popular Singles: sorted by inventory (most listings)
 * - Product Types: filtered by type (Singles, Boxes, Packs, Bundles)
 */

import { useState, useMemo, useRef, useCallback, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { BarChart3, Clock, Flame, ChevronLeft, ChevronRight } from 'lucide-react'
import { ProductCard, ProductCardSkeleton } from '../ui/product-card'

type GalleryTab = 'bestsellers' | 'recent' | 'deals'

type GalleryCard = {
  id: number
  slug?: string
  name: string
  set_name?: string
  floor_price?: number
  lowest_ask?: number
  volume?: number
  inventory?: number
  product_type?: string
  image_url?: string
  last_treatment?: string
  latest_price?: number
  price_delta?: number
  floor_delta?: number
  rarity_name?: string
}

type ProductsGalleryProps = {
  cards: GalleryCard[]
  isLoading?: boolean
  className?: string
}

// Tab button styles - rounded pills with bold text
const TAB_BASE = 'flex items-center gap-2 px-5 py-2.5 text-sm font-bold rounded-full border transition-all whitespace-nowrap'
const TAB_ACTIVE = 'bg-white text-zinc-900 border-white/20 shadow-md'
const TAB_INACTIVE = 'bg-transparent text-muted-foreground border-transparent hover:text-foreground hover:bg-white/5'

const CARDS_TO_SHOW = 12

export function ProductsGallery({ cards, isLoading = false, className }: ProductsGalleryProps) {
  const [activeTab, setActiveTab] = useState<GalleryTab>('bestsellers')
  const scrollRef = useRef<HTMLDivElement>(null)
  const [canScrollLeft, setCanScrollLeft] = useState(false)
  const [canScrollRight, setCanScrollRight] = useState(false)

  // Compute sorted cards for each view
  // Best Sellers: highest volume (most sales)
  const bestsellers = useMemo(
    () => [...cards].sort((a, b) => (b.volume ?? 0) - (a.volume ?? 0)).slice(0, CARDS_TO_SHOW),
    [cards]
  )

  // Recent Sales: cards with any price activity
  // Shows cards that have sales data (floor_price or latest_price)
  const recentSales = useMemo(
    () => [...cards]
      .filter((c) => (c.floor_price ?? c.latest_price ?? 0) > 0)
      .sort((a, b) => {
        // Sort by price_delta (most movement first) then by volume
        const aDelta = Math.abs(a.price_delta ?? 0)
        const bDelta = Math.abs(b.price_delta ?? 0)
        if (bDelta !== aDelta) return bDelta - aDelta
        return (b.volume ?? 0) - (a.volume ?? 0)
      })
      .slice(0, CARDS_TO_SHOW),
    [cards]
  )

  // Hot Deals: cards with active listings priced below market value
  // Only shows cards that are available to buy NOW (inventory > 0)
  // Prioritizes cards where lowest_ask < floor_price (actual deals)
  const hotDeals = useMemo(
    () => {
      // Calculate deal score for each card
      const dealsWithScore = cards
        .filter((c) => {
          // Must have active listings (not stale)
          if (!c.inventory || c.inventory <= 0) return false
          // Must have a lowest ask price
          if (!c.lowest_ask || c.lowest_ask <= 0) return false
          return true
        })
        .map((c) => {
          // Compare lowest_ask to floor_price or latest_price
          const referencePrice = c.floor_price ?? c.latest_price ?? c.lowest_ask
          // Deal score: how much below reference price (negative = good deal)
          // A card listed at $8 when floor is $10 has score -20 (20% discount)
          const discountPercent = referencePrice && referencePrice > 0
            ? ((c.lowest_ask! - referencePrice) / referencePrice) * 100
            : 0
          return { card: c, discountPercent }
        })
        // Filter for actual deals (priced at or below reference)
        .filter((item) => item.discountPercent <= 5) // Allow up to 5% above (close to floor)
        .sort((a, b) => {
          // Best deals first (most negative discount)
          return a.discountPercent - b.discountPercent
        })

      return dealsWithScore.slice(0, CARDS_TO_SHOW)
    },
    [cards]
  )

  // Get deal percent for a card (used in Hot Deals tab)
  const getDealPercent = (cardId: number): number | null => {
    const deal = hotDeals.find((d) => d.card.id === cardId)
    return deal ? deal.discountPercent : null
  }

  // Extract just the card data for display (hotDeals has discount info too)
  const displayCards =
    activeTab === 'bestsellers'
      ? bestsellers
      : activeTab === 'recent'
        ? recentSales
        : hotDeals.map((d) => d.card)

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
  }, [checkScroll, displayCards])

  // Reset scroll when tab changes
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollLeft = 0
    }
  }, [activeTab])

  // Scroll by one "page"
  const scroll = (direction: 'left' | 'right') => {
    const el = scrollRef.current
    if (!el) return
    const scrollAmount = el.clientWidth - 80
    el.scrollBy({
      left: direction === 'left' ? -scrollAmount : scrollAmount,
      behavior: 'smooth',
    })
  }

  if (!isLoading && cards.length === 0) {
    return null
  }

  return (
    <div className={cn('mb-8', className)}>
      {/* Header with tabs and nav arrows */}
      <div className="flex items-center justify-between mb-4">
        {/* Tabs */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab('bestsellers')}
            className={cn(TAB_BASE, activeTab === 'bestsellers' ? TAB_ACTIVE : TAB_INACTIVE)}
          >
            <BarChart3 className="w-4 h-4" />
            Best Sellers
          </button>
          <button
            onClick={() => setActiveTab('recent')}
            className={cn(TAB_BASE, activeTab === 'recent' ? TAB_ACTIVE : TAB_INACTIVE)}
          >
            <Clock className="w-4 h-4" />
            Recent Sales
          </button>
          <button
            onClick={() => setActiveTab('deals')}
            className={cn(TAB_BASE, activeTab === 'deals' ? TAB_ACTIVE : TAB_INACTIVE)}
          >
            <Flame className="w-4 h-4" />
            Hot Deals
          </button>
        </div>

        {/* Navigation arrows (desktop only) */}
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

      {/* Carousel */}
      <div className="relative">
        {/* Gradient fade edges */}
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
            'pb-2',
            'scrollbar-none',
            '[&::-webkit-scrollbar]:hidden',
            '[-ms-overflow-style:none]',
            '[scrollbar-width:none]'
          )}
        >
          {isLoading ? (
            Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="snap-start">
                <ProductCardSkeleton />
              </div>
            ))
          ) : displayCards.length > 0 ? (
            displayCards.map((card) => (
              <div key={card.id} className="snap-start">
                <ProductCard
                  id={card.id}
                  slug={card.slug}
                  name={card.name}
                  setName={card.set_name}
                  price={
                    // Hot Deals: show lowest_ask (buy-now price)
                    // Others: show floor_price or latest sale
                    activeTab === 'deals'
                      ? card.lowest_ask
                      : (card.floor_price ?? card.latest_price)
                  }
                  listingsCount={card.inventory}
                  imageUrl={card.image_url}
                  treatment={card.last_treatment}
                  rarity={card.rarity_name}
                  productType={card.product_type}
                  showBuyNow={activeTab === 'deals'}
                  dealPercent={activeTab === 'deals' ? getDealPercent(card.id) : null}
                />
              </div>
            ))
          ) : (
            <div className="flex items-center justify-center w-full py-8 text-muted-foreground text-sm">
              No cards found
            </div>
          )}
        </div>
      </div>

      {/* Mobile swipe hint */}
      <div className="sm:hidden text-center mt-2">
        <span className="text-xs text-muted-foreground">← Swipe to see more →</span>
      </div>
    </div>
  )
}

/**
 * Loading skeleton for ProductsGallery
 */
export function ProductsGallerySkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('mb-6 animate-pulse', className)}>
      {/* Tab skeleton */}
      <div className="flex items-center gap-1 mb-3">
        <div className="h-8 w-28 bg-muted rounded" />
        <div className="h-8 w-32 bg-muted rounded" />
        <div className="h-8 w-28 bg-muted rounded" />
      </div>
      {/* Cards skeleton */}
      <div className="flex gap-3 overflow-hidden">
        {Array.from({ length: 8 }).map((_, i) => (
          <ProductCardSkeleton key={i} />
        ))}
      </div>
    </div>
  )
}
