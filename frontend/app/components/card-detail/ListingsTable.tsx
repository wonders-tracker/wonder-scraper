/**
 * ListingsTable - Full paginated listings table with seller details
 *
 * Features:
 * - Columns: Seller, Condition/Treatment, Price, Shipping, Platform, Action
 * - Sortable columns (price, date)
 * - Pagination (10/25/50 per page options)
 * - Row count header ("Showing 1-10 of 200")
 * - Alternating row colors for readability
 *
 * @see tasks.json E4-U1
 */

import { useState, useMemo } from 'react'
import { cn } from '@/lib/utils'
import { formatPrice, formatDate } from '@/lib/formatters'
import { SellerBadge } from '../SellerBadge'
import { TreatmentBadge } from '../TreatmentBadge'
import { Button } from '../ui/button'
import { Tooltip } from '../ui/tooltip'
import {
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  Package
} from 'lucide-react'

// Re-export Listing type from ListingsPanel for consistency
export type { Listing, ListingPlatform } from './ListingsPanel'
import type { Listing, ListingPlatform } from './ListingsPanel'

// Platform config for badges
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

// Pagination state
export type PaginationState = {
  page: number
  pageSize: number
}

// Sort state
export type SortState = {
  key: SortKey
  direction: 'asc' | 'desc'
}

// Sortable column keys
export type SortKey = 'price' | 'date' | 'seller' | 'shipping'

// Page size options
export const PAGE_SIZE_OPTIONS = [10, 25, 50] as const
export type PageSizeOption = typeof PAGE_SIZE_OPTIONS[number]

// Props for the table
export type ListingsTableProps = {
  /** Array of listing data */
  data: Listing[]
  /** Total number of listings (for pagination display) */
  totalCount: number
  /** Current pagination state */
  pagination: PaginationState
  /** Callback when pagination changes */
  onPaginationChange: (pagination: PaginationState) => void
  /** Current sort state */
  sort: SortState
  /** Callback when sort changes */
  onSortChange: (sort: SortState) => void
  /** Whether data is loading */
  isLoading?: boolean
  /** Callback when row action is clicked (for analytics) */
  onRowAction?: (listing: Listing) => void
  /** Additional className */
  className?: string
}

/**
 * Sort icon component
 */
function SortIcon({ dir }: { dir?: 'asc' | 'desc' }) {
  if (!dir) return <ChevronsUpDown className="w-3 h-3 text-muted-foreground" aria-hidden="true" />
  if (dir === 'asc') return <ChevronUp className="w-3 h-3 text-brand-400" aria-hidden="true" />
  return <ChevronDown className="w-3 h-3 text-brand-400" aria-hidden="true" />
}

/**
 * Platform badge component
 */
function PlatformBadge({ platform }: { platform: ListingPlatform }) {
  const config = PLATFORM_CONFIG[platform]
  return (
    <span
      className={cn(
        'inline-flex items-center px-1.5 py-0.5 text-[10px] font-semibold uppercase rounded border',
        config.bgColor,
        config.textColor,
        config.borderColor
      )}
      role="text"
      aria-label={`Platform: ${config.name}`}
    >
      {config.name}
    </span>
  )
}

export function ListingsTable({
  data,
  totalCount,
  pagination,
  onPaginationChange,
  sort,
  onSortChange,
  isLoading = false,
  onRowAction,
  className
}: ListingsTableProps) {
  // State for screen reader announcements
  const [announcement, setAnnouncement] = useState<string>('')

  // Handle column header click for sorting
  const handleSort = (key: SortKey) => {
    const newDirection = sort.key === key && sort.direction === 'asc' ? 'desc' : 'asc'
    if (sort.key === key) {
      onSortChange({
        key,
        direction: newDirection
      })
    } else {
      onSortChange({ key, direction: 'asc' })
    }
    // Announce sort change to screen readers
    const directionText = newDirection === 'asc' ? 'ascending' : 'descending'
    setAnnouncement(`Sorted by ${key} in ${directionText} order`)
  }

  // Handle page change
  const handlePageChange = (newPage: number) => {
    onPaginationChange({ ...pagination, page: newPage })
    // Announce page change to screen readers
    setAnnouncement(`Page ${newPage} of ${totalPages}`)
  }

  // Handle page size change
  const handlePageSizeChange = (newPageSize: PageSizeOption) => {
    onPaginationChange({ page: 1, pageSize: newPageSize })
    setAnnouncement(`Showing ${newPageSize} items per page`)
  }

  // Calculate pagination info
  const totalPages = Math.ceil(totalCount / pagination.pageSize)
  const startItem = (pagination.page - 1) * pagination.pageSize + 1
  const endItem = Math.min(pagination.page * pagination.pageSize, totalCount)

  // Handle row click to view listing
  const handleRowAction = (listing: Listing) => {
    onRowAction?.(listing)
    window.open(listing.url, '_blank', 'noopener,noreferrer')
  }

  // Empty state
  if (!isLoading && data.length === 0) {
    return (
      <div className={cn('border border-border rounded bg-card', className)}>
        <div className="flex flex-col items-center justify-center h-64 text-center px-4" role="status">
          <Package className="w-12 h-12 text-muted-foreground mb-4" aria-hidden="true" />
          <h3 className="text-lg font-semibold mb-2">No Listings Found</h3>
          <p className="text-sm text-muted-foreground max-w-[280px]">
            There are currently no listings available. Check back later or adjust your filters.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className={cn('border border-border rounded bg-card', className)}>
      {/* Screen reader announcements for dynamic changes */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {announcement}
      </div>

      {/* Header with row count and page size selector */}
      <div className="px-4 py-3 border-b border-border flex items-center justify-between flex-wrap gap-2">
        <div className="text-sm text-muted-foreground" aria-live="polite" aria-atomic="true">
          {isLoading ? (
            <span className="animate-pulse">Loading...</span>
          ) : (
            <>
              Showing <span className="font-medium text-foreground">{startItem}-{endItem}</span> of{' '}
              <span className="font-medium text-foreground">{totalCount.toLocaleString()}</span>
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="page-size-select" className="text-xs text-muted-foreground">
            Per page:
          </label>
          <select
            id="page-size-select"
            value={pagination.pageSize}
            onChange={(e) => handlePageSizeChange(Number(e.target.value) as PageSizeOption)}
            className="h-7 px-2 text-xs bg-background border border-border rounded focus:outline-none focus:ring-2 focus:ring-brand-500 focus-visible:ring-2 focus-visible:ring-brand-500"
            disabled={isLoading}
            aria-label="Items per page"
          >
            {PAGE_SIZE_OPTIONS.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Mobile scroll hint */}
      <div className="lg:hidden text-[10px] text-muted-foreground text-center py-1.5 border-b border-border/50">
        Scroll horizontally for more
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted-foreground text-xs border-b border-border bg-muted/30">
              {/* Seller column */}
              <th scope="col" className="p-3 min-w-[140px]">
                <button
                  onClick={() => handleSort('seller')}
                  className="flex items-center gap-1 hover:text-foreground transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 rounded px-1"
                  disabled={isLoading}
                  aria-label={`Sort by seller ${sort.key === 'seller' ? (sort.direction === 'asc' ? 'descending' : 'ascending') : 'ascending'}`}
                  aria-sort={sort.key === 'seller' ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'}
                >
                  Seller
                  <SortIcon dir={sort.key === 'seller' ? sort.direction : undefined} />
                </button>
              </th>
              {/* Condition/Treatment column */}
              <th scope="col" className="p-3 min-w-[120px]">
                <span>Condition</span>
              </th>
              {/* Price column */}
              <th scope="col" className="p-3 text-right min-w-[80px]">
                <Tooltip content="Item price before shipping">
                  <button
                    onClick={() => handleSort('price')}
                    className="flex items-center gap-1 justify-end hover:text-foreground transition-colors cursor-help ml-auto focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 rounded px-1"
                    disabled={isLoading}
                    aria-label={`Sort by price ${sort.key === 'price' ? (sort.direction === 'asc' ? 'descending' : 'ascending') : 'ascending'}`}
                    aria-sort={sort.key === 'price' ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'}
                  >
                    Price
                    <SortIcon dir={sort.key === 'price' ? sort.direction : undefined} />
                  </button>
                </Tooltip>
              </th>
              {/* Shipping column */}
              <th scope="col" className="p-3 text-right min-w-[80px]">
                <Tooltip content="Shipping cost">
                  <button
                    onClick={() => handleSort('shipping')}
                    className="flex items-center gap-1 justify-end hover:text-foreground transition-colors cursor-help ml-auto focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 rounded px-1"
                    disabled={isLoading}
                    aria-label={`Sort by shipping ${sort.key === 'shipping' ? (sort.direction === 'asc' ? 'descending' : 'ascending') : 'ascending'}`}
                    aria-sort={sort.key === 'shipping' ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'}
                  >
                    Shipping
                    <SortIcon dir={sort.key === 'shipping' ? sort.direction : undefined} />
                  </button>
                </Tooltip>
              </th>
              {/* Platform column */}
              <th scope="col" className="p-3 min-w-[80px]">
                <span>Platform</span>
              </th>
              {/* Action column */}
              <th scope="col" className="p-3 text-center min-w-[100px]">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              // Loading skeleton rows
              Array.from({ length: pagination.pageSize }).map((_, i) => (
                <tr
                  key={`skeleton-${i}`}
                  className={cn(
                    'border-b border-border/50',
                    i % 2 === 1 && 'bg-muted/20'
                  )}
                >
                  <td className="p-3">
                    <div className="h-4 w-24 bg-muted rounded animate-pulse" />
                  </td>
                  <td className="p-3">
                    <div className="h-5 w-20 bg-muted rounded animate-pulse" />
                  </td>
                  <td className="p-3 text-right">
                    <div className="h-4 w-16 bg-muted rounded animate-pulse ml-auto" />
                  </td>
                  <td className="p-3 text-right">
                    <div className="h-4 w-14 bg-muted rounded animate-pulse ml-auto" />
                  </td>
                  <td className="p-3">
                    <div className="h-5 w-14 bg-muted rounded animate-pulse" />
                  </td>
                  <td className="p-3 text-center">
                    <div className="h-7 w-16 bg-muted rounded animate-pulse mx-auto" />
                  </td>
                </tr>
              ))
            ) : (
              // Data rows
              data.map((listing, i) => {
                const totalPrice = listing.price + (listing.shippingPrice || 0)
                const accessibleLabel = `${listing.seller} - ${listing.treatment || 'Unknown condition'} - ${formatPrice(listing.price)} on ${PLATFORM_CONFIG[listing.platform].name}`

                return (
                  <tr
                    key={listing.id}
                    className={cn(
                      'border-b border-border/50 transition-colors hover:bg-muted/50',
                      i % 2 === 1 && 'bg-muted/20'
                    )}
                    aria-label={accessibleLabel}
                  >
                    {/* Seller */}
                    <td className="p-3">
                      <SellerBadge
                        sellerName={listing.seller}
                        feedbackScore={listing.sellerSales}
                        feedbackPercent={listing.sellerRating}
                        showDetails={true}
                        size="xs"
                      />
                    </td>
                    {/* Condition/Treatment */}
                    <td className="p-3">
                      <div className="flex flex-col gap-1">
                        {listing.treatment && (
                          <TreatmentBadge treatment={listing.treatment} size="xs" />
                        )}
                        {listing.condition && (
                          <span className="text-[10px] text-muted-foreground">
                            {listing.condition}
                          </span>
                        )}
                        {!listing.treatment && !listing.condition && (
                          <span className="text-xs text-muted-foreground">-</span>
                        )}
                      </div>
                    </td>
                    {/* Price */}
                    <td className="p-3 text-right">
                      <span className="font-mono font-bold text-brand-300">
                        {formatPrice(listing.price)}
                      </span>
                    </td>
                    {/* Shipping */}
                    <td className="p-3 text-right">
                      {listing.shippingPrice === undefined ? (
                        <span className="text-muted-foreground text-xs">Varies</span>
                      ) : listing.shippingPrice === 0 ? (
                        <span className="text-green-500 text-xs font-medium">Free</span>
                      ) : (
                        <span className="font-mono text-muted-foreground text-xs">
                          {formatPrice(listing.shippingPrice)}
                        </span>
                      )}
                    </td>
                    {/* Platform */}
                    <td className="p-3">
                      <PlatformBadge platform={listing.platform} />
                    </td>
                    {/* Action */}
                    <td className="p-3 text-center">
                      <Button
                        variant="outline"
                        size="xs"
                        onClick={() => handleRowAction(listing)}
                        rightIcon={<ExternalLink className="w-3 h-3" />}
                        aria-label={`View listing on ${PLATFORM_CONFIG[listing.platform].name}`}
                      >
                        View
                      </Button>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      {totalPages > 1 && !isLoading && (
        <nav aria-label="Listings pagination" className="flex items-center justify-between p-4 border-t border-border bg-muted/20">
          <Button
            variant="outline"
            size="sm"
            onClick={() => handlePageChange(pagination.page - 1)}
            disabled={pagination.page <= 1}
            leftIcon={<ChevronLeft className="w-4 h-4" />}
            aria-label={`Previous page (page ${pagination.page - 1})`}
          >
            Previous
          </Button>
          <div className="flex items-center gap-1" role="group" aria-label="Page numbers">
            {/* Page number buttons */}
            {generatePageNumbers(pagination.page, totalPages).map((pageNum, i) => (
              pageNum === '...' ? (
                <span key={`ellipsis-${i}`} className="px-2 text-muted-foreground" aria-hidden="true">
                  ...
                </span>
              ) : (
                <button
                  key={pageNum}
                  onClick={() => handlePageChange(pageNum as number)}
                  className={cn(
                    'h-8 w-8 text-sm rounded transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1',
                    pagination.page === pageNum
                      ? 'bg-brand-500 text-white font-medium'
                      : 'hover:bg-muted text-muted-foreground hover:text-foreground'
                  )}
                  aria-current={pagination.page === pageNum ? 'page' : undefined}
                  aria-label={`Page ${pageNum}${pagination.page === pageNum ? ' (current)' : ''}`}
                >
                  {pageNum}
                </button>
              )
            ))}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handlePageChange(pagination.page + 1)}
            disabled={pagination.page >= totalPages}
            rightIcon={<ChevronRight className="w-4 h-4" />}
            aria-label={`Next page (page ${pagination.page + 1})`}
          >
            Next
          </Button>
        </nav>
      )}
    </div>
  )
}

/**
 * Generate page numbers with ellipsis for large page counts
 */
function generatePageNumbers(currentPage: number, totalPages: number): (number | '...')[] {
  const pages: (number | '...')[] = []

  if (totalPages <= 7) {
    // Show all pages if 7 or fewer
    for (let i = 1; i <= totalPages; i++) {
      pages.push(i)
    }
  } else {
    // Always show first page
    pages.push(1)

    if (currentPage > 3) {
      pages.push('...')
    }

    // Show pages around current page
    const start = Math.max(2, currentPage - 1)
    const end = Math.min(totalPages - 1, currentPage + 1)

    for (let i = start; i <= end; i++) {
      pages.push(i)
    }

    if (currentPage < totalPages - 2) {
      pages.push('...')
    }

    // Always show last page
    pages.push(totalPages)
  }

  return pages
}

/**
 * Loading skeleton for ListingsTable
 */
export function ListingsTableSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn('border border-border rounded bg-card animate-pulse', className)}
      role="status"
      aria-busy="true"
      aria-label="Loading listings table"
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <div className="h-4 w-40 bg-muted rounded" />
        <div className="h-7 w-20 bg-muted rounded" />
      </div>
      {/* Table skeleton */}
      <div className="p-4 space-y-3">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="flex items-center justify-between gap-4">
            <div className="h-4 w-24 bg-muted rounded" />
            <div className="h-5 w-20 bg-muted rounded" />
            <div className="h-4 w-16 bg-muted rounded" />
            <div className="h-4 w-14 bg-muted rounded" />
            <div className="h-5 w-14 bg-muted rounded" />
            <div className="h-7 w-16 bg-muted rounded" />
          </div>
        ))}
      </div>
      <span className="sr-only">Loading listings data...</span>
    </div>
  )
}

export default ListingsTable
