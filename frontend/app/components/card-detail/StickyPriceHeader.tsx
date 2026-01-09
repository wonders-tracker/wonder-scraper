/**
 * StickyPriceHeader - Mobile sticky header showing price info
 *
 * Appears when scrolling past the price box on mobile.
 * Shows: Card name, price, "View Listings" button
 *
 * Features:
 * - Compact height (48-56px)
 * - Smooth show/hide animation
 * - Z-index above content, below modals
 * - Only visible on mobile (md:hidden)
 *
 * @see tasks.json E6-U2
 */

import { useState, useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'
import { formatPrice } from '@/lib/formatters'
import { ChevronRight } from 'lucide-react'

export type StickyPriceHeaderProps = {
  /** Card name */
  cardName: string
  /** Primary price to display */
  price?: number | null
  /** Price label (e.g., "Floor", "Ask") */
  priceLabel?: string
  /** Callback when "View Listings" is clicked */
  onViewListings?: () => void
  /** Whether to show the header (based on scroll position) */
  isVisible?: boolean
  /** Additional className */
  className?: string
}

export function StickyPriceHeader({
  cardName,
  price,
  priceLabel = 'Floor',
  onViewListings,
  isVisible = false,
  className,
}: StickyPriceHeaderProps) {
  return (
    <div
      className={cn(
        // Positioning
        'fixed top-0 left-0 right-0 z-40',
        // Visibility - only on mobile
        'md:hidden',
        // Styling
        'bg-background/95 backdrop-blur-sm border-b border-border',
        'shadow-lg shadow-black/10',
        // Animation
        'transition-transform duration-300 ease-in-out',
        isVisible ? 'translate-y-0' : '-translate-y-full',
        className
      )}
      aria-hidden={!isVisible}
    >
      <div className="flex items-center justify-between px-4 py-3 max-w-[1400px] mx-auto">
        {/* Left: Card name and price */}
        <div className="flex-1 min-w-0 pr-4">
          <h2 className="text-sm font-bold text-foreground truncate">
            {cardName}
          </h2>
          <div className="flex items-center gap-2 text-xs">
            <span className="text-muted-foreground">{priceLabel}:</span>
            <span className="font-mono font-bold text-brand-300">
              {price != null ? formatPrice(price) : '---'}
            </span>
          </div>
        </div>

        {/* Right: View Listings button */}
        {onViewListings && (
          <button
            onClick={onViewListings}
            className={cn(
              'flex items-center gap-1 px-4 py-2',
              'bg-brand-500 hover:bg-brand-600 text-white',
              'rounded font-bold text-xs uppercase tracking-wider',
              'transition-colors touch-manipulation min-h-[44px]',
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2'
            )}
          >
            Listings
            <ChevronRight className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  )
}

/**
 * Hook to track when an element scrolls out of view
 *
 * @param ref - Ref to the element to observe
 * @param threshold - How much of element must be visible (0-1)
 * @returns Whether the element is out of view (scrolled past)
 */
export function useScrollPast(
  ref: React.RefObject<HTMLElement>,
  threshold = 0
): boolean {
  const [isScrolledPast, setIsScrolledPast] = useState(false)

  useEffect(() => {
    const element = ref.current
    if (!element) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        // Element is "scrolled past" when it's not intersecting
        // and the boundingClientRect.bottom is above viewport
        setIsScrolledPast(
          !entry.isIntersecting && entry.boundingClientRect.bottom < 0
        )
      },
      {
        threshold,
        rootMargin: '0px',
      }
    )

    observer.observe(element)
    return () => observer.disconnect()
  }, [ref, threshold])

  return isScrolledPast
}

/**
 * Wrapper component that handles scroll detection
 */
export function StickyPriceHeaderWithScroll({
  priceBoxRef,
  ...props
}: Omit<StickyPriceHeaderProps, 'isVisible'> & {
  priceBoxRef: React.RefObject<HTMLElement>
}) {
  const isScrolledPast = useScrollPast(priceBoxRef)
  return <StickyPriceHeader {...props} isVisible={isScrolledPast} />
}
