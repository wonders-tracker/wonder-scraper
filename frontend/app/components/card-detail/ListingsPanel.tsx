/**
 * ListingsPanel - Slide-out modal for viewing external listings
 *
 * Features:
 * - Triggered by 'View X Listings' button
 * - Paginated list of external listings
 * - Each listing shows: seller, price, platform (eBay/Blokpax), condition
 * - Click-through links to external sites
 * - Close button and click-outside-to-close
 * - Loading and empty states
 *
 * @see tasks.json E2-U2
 */

import { useEffect, useRef, useCallback, useState } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/lib/utils'
import { Button } from '../ui/button'
import { TreatmentBadge } from '../TreatmentBadge'
import {
  X,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Package,
  ShoppingCart,
  Star,
  AlertCircle
} from 'lucide-react'

// Platform types
export type ListingPlatform = 'ebay' | 'blokpax' | 'other'

// Individual listing type
export type Listing = {
  id: string
  seller: string
  sellerRating?: number
  sellerSales?: number
  price: number
  shippingPrice?: number
  platform: ListingPlatform
  condition?: string
  treatment?: string
  url: string
  imageUrl?: string
  title?: string
  endDate?: string
  quantity?: number
}

// Platform config for icons/colors
const PLATFORM_CONFIG: Record<ListingPlatform, {
  name: string
  bgColor: string
  textColor: string
  borderColor: string
}> = {
  ebay: {
    name: 'eBay',
    bgColor: 'bg-yellow-500/10',
    textColor: 'text-yellow-500',
    borderColor: 'border-yellow-500/20'
  },
  blokpax: {
    name: 'Blokpax',
    bgColor: 'bg-purple-500/10',
    textColor: 'text-purple-500',
    borderColor: 'border-purple-500/20'
  },
  other: {
    name: 'Other',
    bgColor: 'bg-gray-500/10',
    textColor: 'text-gray-500',
    borderColor: 'border-gray-500/20'
  }
}

// Props for the panel
export type ListingsPanelProps = {
  /** Whether the panel is open */
  isOpen: boolean
  /** Callback to close the panel */
  onClose: () => void
  /** Card name for the header */
  cardName: string
  /** Total number of listings */
  totalListings: number
  /** Current page of listings */
  listings: Listing[]
  /** Whether listings are loading */
  isLoading?: boolean
  /** Current page number (1-indexed) */
  currentPage: number
  /** Total number of pages */
  totalPages: number
  /** Callback when page changes */
  onPageChange: (page: number) => void
  /** Items per page */
  pageSize?: number
  /** Error message if any */
  error?: string
  /** Callback when listing is clicked (for analytics) */
  onListingClick?: (listing: Listing) => void
}

export function ListingsPanel({
  isOpen,
  onClose,
  cardName,
  totalListings,
  listings,
  isLoading = false,
  currentPage,
  totalPages,
  onPageChange,
  pageSize = 10,
  error,
  onListingClick
}: ListingsPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  const [isAnimating, setIsAnimating] = useState(false)
  const [shouldRender, setShouldRender] = useState(false)

  // Handle animation timing
  useEffect(() => {
    if (isOpen) {
      setShouldRender(true)
      // Small delay to allow DOM to update before animation
      requestAnimationFrame(() => {
        setIsAnimating(true)
      })
    } else {
      setIsAnimating(false)
      // Wait for animation to complete before removing from DOM
      const timer = setTimeout(() => {
        setShouldRender(false)
      }, 300) // Match animation duration
      return () => clearTimeout(timer)
    }
  }, [isOpen])

  // Handle click outside to close
  const handleBackdropClick = useCallback((e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }, [onClose])

  // Handle escape key
  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  // Lock body scroll when open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
      return () => {
        document.body.style.overflow = ''
      }
    }
  }, [isOpen])

  // Focus trap
  useEffect(() => {
    if (!isOpen || !panelRef.current) return

    const focusableElements = panelRef.current.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
    const firstElement = focusableElements[0] as HTMLElement
    const lastElement = focusableElements[focusableElements.length - 1] as HTMLElement

    const handleTabKey = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return

      if (e.shiftKey) {
        if (document.activeElement === firstElement) {
          e.preventDefault()
          lastElement?.focus()
        }
      } else {
        if (document.activeElement === lastElement) {
          e.preventDefault()
          firstElement?.focus()
        }
      }
    }

    document.addEventListener('keydown', handleTabKey)
    firstElement?.focus()

    return () => document.removeEventListener('keydown', handleTabKey)
  }, [isOpen, listings])

  if (!shouldRender || typeof document === 'undefined') return null

  const content = (
    <div
      className={cn(
        "fixed inset-0 z-50 flex justify-end",
        "transition-colors duration-300",
        isAnimating ? "bg-black/50" : "bg-transparent"
      )}
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="listings-panel-title"
    >
      {/* Panel */}
      <div
        ref={panelRef}
        className={cn(
          "relative w-full max-w-lg h-full bg-card border-l border-border shadow-2xl",
          "flex flex-col overflow-hidden",
          "transition-transform duration-300 ease-out",
          isAnimating ? "translate-x-0" : "translate-x-full"
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div>
            <h2 id="listings-panel-title" className="text-lg font-bold uppercase tracking-tight">
              {totalListings.toLocaleString()} Listings
            </h2>
            <p className="text-sm text-muted-foreground truncate max-w-[300px]">
              {cardName}
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label="Close listings panel"
          >
            <X className="w-5 h-5" />
          </Button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <ListingsPanelLoading pageSize={pageSize} />
          ) : error ? (
            <ListingsPanelError message={error} onRetry={() => onPageChange(currentPage)} />
          ) : listings.length === 0 ? (
            <ListingsPanelEmpty />
          ) : (
            <div className="divide-y divide-border">
              {listings.map((listing) => (
                <ListingItem
                  key={listing.id}
                  listing={listing}
                  onClick={onListingClick}
                />
              ))}
            </div>
          )}
        </div>

        {/* Pagination Footer */}
        {totalPages > 1 && !isLoading && !error && listings.length > 0 && (
          <div className="flex items-center justify-between p-4 border-t border-border bg-card">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPageChange(currentPage - 1)}
              disabled={currentPage <= 1}
              leftIcon={<ChevronLeft className="w-4 h-4" />}
            >
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {currentPage} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPageChange(currentPage + 1)}
              disabled={currentPage >= totalPages}
              rightIcon={<ChevronRight className="w-4 h-4" />}
            >
              Next
            </Button>
          </div>
        )}
      </div>
    </div>
  )

  return createPortal(content, document.body)
}

// Individual listing item
type ListingItemProps = {
  listing: Listing
  onClick?: (listing: Listing) => void
}

function ListingItem({ listing, onClick }: ListingItemProps) {
  const platformConfig = PLATFORM_CONFIG[listing.platform]
  const totalPrice = listing.price + (listing.shippingPrice || 0)

  const handleClick = () => {
    onClick?.(listing)
    window.open(listing.url, '_blank', 'noopener,noreferrer')
  }

  // Build accessible label for the listing
  const accessibleLabel = `${listing.title || 'Listing'} from ${listing.seller} on ${platformConfig.name}, $${listing.price.toFixed(2)}${listing.treatment ? `, ${listing.treatment}` : ''}`

  return (
    <div
      className="p-4 hover:bg-muted/50 transition-colors cursor-pointer group"
      onClick={handleClick}
      role="button"
      tabIndex={0}
      aria-label={accessibleLabel}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          handleClick()
        }
      }}
    >
      <div className="flex items-start gap-3">
        {/* Listing Image (optional) */}
        {listing.imageUrl && (
          <div className="w-16 h-16 shrink-0 rounded bg-muted overflow-hidden">
            <img
              src={listing.imageUrl}
              alt=""
              className="w-full h-full object-cover"
              loading="lazy"
            />
          </div>
        )}

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Title row with platform badge */}
          <div className="flex items-start justify-between gap-2 mb-1">
            <div className="flex items-center gap-2 min-w-0">
              {/* Platform badge */}
              <span
                className={cn(
                  "shrink-0 px-1.5 py-0.5 text-[10px] font-semibold uppercase rounded border",
                  platformConfig.bgColor,
                  platformConfig.textColor,
                  platformConfig.borderColor
                )}
              >
                {platformConfig.name}
              </span>
              {/* Treatment */}
              {listing.treatment && (
                <TreatmentBadge treatment={listing.treatment} size="xs" />
              )}
            </div>
            {/* External link indicator */}
            <ExternalLink className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0" aria-hidden="true" />
          </div>

          {/* Seller info */}
          <div className="flex items-center gap-2 text-sm">
            <span className="font-medium truncate">{listing.seller}</span>
            {listing.sellerRating !== undefined && (
              <span className="flex items-center gap-0.5 text-yellow-500 text-xs shrink-0">
                <Star className="w-3 h-3 fill-current" aria-hidden="true" />
                <span className="sr-only">Seller rating:</span>
                {listing.sellerRating}%
              </span>
            )}
            {listing.sellerSales !== undefined && (
              <span className="text-xs text-muted-foreground shrink-0">
                ({listing.sellerSales.toLocaleString()} sales)
              </span>
            )}
          </div>

          {/* Condition */}
          {listing.condition && (
            <div className="text-xs text-muted-foreground mt-0.5">
              {listing.condition}
            </div>
          )}

          {/* Price row */}
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-lg font-mono font-bold">
              ${listing.price.toFixed(2)}
            </span>
            {listing.shippingPrice !== undefined && listing.shippingPrice > 0 && (
              <span className="text-xs text-muted-foreground">
                + ${listing.shippingPrice.toFixed(2)} shipping
              </span>
            )}
            {listing.shippingPrice === 0 && (
              <span className="text-xs text-green-500 font-medium">
                Free shipping
              </span>
            )}
          </div>

          {/* Total price if shipping exists */}
          {listing.shippingPrice !== undefined && listing.shippingPrice > 0 && (
            <div className="text-xs text-muted-foreground mt-0.5">
              Total: ${totalPrice.toFixed(2)}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// Loading state
function ListingsPanelLoading({ pageSize }: { pageSize: number }) {
  return (
    <div className="divide-y divide-border">
      {Array.from({ length: pageSize }).map((_, i) => (
        <div key={i} className="p-4 animate-pulse">
          <div className="flex items-start gap-3">
            <div className="w-16 h-16 shrink-0 rounded bg-muted" />
            <div className="flex-1 space-y-2">
              <div className="flex items-center gap-2">
                <div className="h-4 w-12 bg-muted rounded" />
                <div className="h-4 w-16 bg-muted rounded" />
              </div>
              <div className="h-4 w-32 bg-muted rounded" />
              <div className="h-3 w-24 bg-muted rounded" />
              <div className="h-5 w-20 bg-muted rounded" />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// Empty state
function ListingsPanelEmpty() {
  return (
    <div className="flex flex-col items-center justify-center h-64 text-center px-4" role="status" aria-live="polite">
      <Package className="w-12 h-12 text-muted-foreground mb-4" aria-hidden="true" />
      <h3 className="text-lg font-semibold mb-2">No Listings Found</h3>
      <p className="text-sm text-muted-foreground max-w-[280px]">
        There are currently no listings available for this card. Check back later or try a different treatment.
      </p>
    </div>
  )
}

// Error state
function ListingsPanelError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 text-center px-4" role="alert" aria-live="assertive">
      <AlertCircle className="w-12 h-12 text-destructive mb-4" aria-hidden="true" />
      <h3 className="text-lg font-semibold mb-2">Error Loading Listings</h3>
      <p className="text-sm text-muted-foreground max-w-[280px] mb-4">
        {message || 'Something went wrong while loading the listings.'}
      </p>
      <Button variant="outline" onClick={onRetry}>
        Try Again
      </Button>
    </div>
  )
}

// Export compound component parts for flexibility
export const ListingsPanelComponents = {
  Item: ListingItem,
  Loading: ListingsPanelLoading,
  Empty: ListingsPanelEmpty,
  Error: ListingsPanelError
}

export default ListingsPanel
