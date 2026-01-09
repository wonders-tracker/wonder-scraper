/**
 * MobileStickyActions - Mobile sticky footer with action buttons
 *
 * Appears when scrolling past the price box on mobile.
 * Shows: Add to Portfolio, Buy Now buttons
 *
 * Features:
 * - Fixed to bottom of viewport
 * - Smooth show/hide animation
 * - Only visible on mobile (md:hidden)
 * - Positioned above the global footer
 *
 * @see tasks.json E6-U2
 */

import { cn } from '@/lib/utils'
import { Plus, ExternalLink, Check } from 'lucide-react'
import { Button } from '../ui/button'

export type MobileStickyActionsProps = {
  /** Whether to show the actions (based on scroll position) */
  isVisible?: boolean
  /** Callback for Add to Portfolio */
  onAddToPortfolio: () => void
  /** Whether showing "Added!" feedback */
  showAddedFeedback?: boolean
  /** Buy now URL (eBay, Blokpax, etc.) */
  buyNowUrl?: string
  /** Lowest buy now price */
  lowestBuyNowPrice?: number | null
  /** Listings count (fallback if no buy now URL) */
  listingsCount?: number
  /** Callback for viewing listings (fallback) */
  onViewListings?: () => void
  /** Additional className */
  className?: string
}

export function MobileStickyActions({
  isVisible = false,
  onAddToPortfolio,
  showAddedFeedback = false,
  buyNowUrl,
  lowestBuyNowPrice,
  listingsCount = 0,
  onViewListings,
  className,
}: MobileStickyActionsProps) {
  return (
    <div
      className={cn(
        // Positioning - above global footer (which is fixed at bottom)
        'fixed bottom-14 left-0 right-0 z-40',
        // Visibility - only on mobile
        'md:hidden',
        // Styling
        'bg-background/95 backdrop-blur-sm border-t border-border',
        'shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)]',
        // Animation
        'transition-transform duration-300 ease-in-out',
        isVisible ? 'translate-y-0' : 'translate-y-full',
        className
      )}
      aria-hidden={!isVisible}
    >
      <div className="flex items-center gap-2 px-4 py-3 max-w-[1400px] mx-auto">
        {/* Add to Portfolio Button */}
        <Button
          variant="outline"
          size="md"
          className={cn(
            "flex-1 uppercase tracking-wide text-xs font-bold transition-all min-h-[44px]",
            showAddedFeedback && "bg-green-600 hover:bg-green-600 text-white border-green-600"
          )}
          onClick={onAddToPortfolio}
          leftIcon={showAddedFeedback ? <Check className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
        >
          {showAddedFeedback ? 'Added!' : 'Add to Portfolio'}
        </Button>

        {/* Buy Now CTA */}
        {buyNowUrl ? (
          <a
            href={buyNowUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(
              "flex-1 flex items-center justify-center gap-2 px-4 py-3",
              "bg-brand-700 hover:bg-brand-800 text-white",
              "rounded-lg font-bold text-xs uppercase tracking-wide min-h-[44px]",
              "transition-colors"
            )}
          >
            Buy {lowestBuyNowPrice ? `$${lowestBuyNowPrice.toFixed(0)}` : 'Now'}
            <ExternalLink className="w-4 h-4" />
          </a>
        ) : onViewListings && (
          <Button
            variant="primary"
            size="md"
            className="flex-1 uppercase tracking-wide text-xs font-bold min-h-[44px]"
            onClick={onViewListings}
            rightIcon={<ExternalLink className="w-4 h-4" />}
          >
            {listingsCount > 0 ? `${listingsCount} Listings` : 'View Listings'}
          </Button>
        )}
      </div>
    </div>
  )
}
