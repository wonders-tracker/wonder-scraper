/**
 * ThreeMonthSnapshot - TCGPlayer-inspired 3-month market stats
 *
 * Displays key market metrics for the selected time period:
 * - Low/High sale prices with dates
 * - Total sold count
 * - Average daily sold calculation
 * - "View More Data" link
 *
 * @see tasks.json E3-U3
 */

import { cn } from '@/lib/utils'
import { formatPrice } from '@/lib/formatters'
import { TrendingDown, TrendingUp, Activity, Calendar } from 'lucide-react'

export type ThreeMonthSnapshotProps = {
  /** Lowest sale price in period */
  lowPrice?: number | null
  /** Date of lowest sale */
  lowDate?: string | null
  /** Highest sale price in period */
  highPrice?: number | null
  /** Date of highest sale */
  highDate?: string | null
  /** Total number of sales in period */
  totalSold?: number | null
  /** Average sales per day */
  avgDailySold?: number | null
  /** Label for time period (e.g., "3 Month") */
  periodLabel?: string
  /** Callback for "View More Data" click */
  onViewMore?: () => void
  /** Whether data is loading */
  isLoading?: boolean
  /** Additional className */
  className?: string
}

/**
 * Format date for display (e.g., "Jan 15")
 */
function formatShortDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '---'
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return '---'
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export function ThreeMonthSnapshot({
  lowPrice,
  lowDate,
  highPrice,
  highDate,
  totalSold,
  avgDailySold,
  periodLabel = '3 Month',
  onViewMore,
  isLoading = false,
  className
}: ThreeMonthSnapshotProps) {
  if (isLoading) {
    return <ThreeMonthSnapshotSkeleton className={className} />
  }

  const hasData = totalSold != null && totalSold > 0

  return (
    <div className={cn('border border-border rounded bg-card', className)}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-widest flex items-center gap-2">
          <Calendar className="w-3.5 h-3.5 text-muted-foreground" />
          {periodLabel} Snapshot
        </h3>
        {onViewMore && (
          <button
            onClick={onViewMore}
            className="text-[10px] text-brand-400 hover:text-brand-300 hover:underline transition-colors"
          >
            View More Data →
          </button>
        )}
      </div>

      {/* Stats Grid */}
      {hasData ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4">
          {/* Low */}
          <div className="space-y-1">
            <div className="flex items-center gap-1.5">
              <TrendingDown className="w-3 h-3 text-rose-400" />
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Low</span>
            </div>
            <div className="text-lg font-mono font-bold text-rose-400">
              {lowPrice != null ? formatPrice(lowPrice) : '---'}
            </div>
            <div className="text-[10px] text-muted-foreground">
              {formatShortDate(lowDate)}
            </div>
          </div>

          {/* High */}
          <div className="space-y-1">
            <div className="flex items-center gap-1.5">
              <TrendingUp className="w-3 h-3 text-brand-300" />
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider">High</span>
            </div>
            <div className="text-lg font-mono font-bold text-brand-300">
              {highPrice != null ? formatPrice(highPrice) : '---'}
            </div>
            <div className="text-[10px] text-muted-foreground">
              {formatShortDate(highDate)}
            </div>
          </div>

          {/* Total Sold */}
          <div className="space-y-1">
            <div className="flex items-center gap-1.5">
              <Activity className="w-3 h-3 text-muted-foreground" />
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Total Sold</span>
            </div>
            <div className="text-lg font-mono font-bold text-foreground">
              {totalSold?.toLocaleString() ?? '---'}
            </div>
            <div className="text-[10px] text-muted-foreground">
              in period
            </div>
          </div>

          {/* Avg Daily */}
          <div className="space-y-1">
            <div className="flex items-center gap-1.5">
              <Calendar className="w-3 h-3 text-muted-foreground" />
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Avg Daily</span>
            </div>
            <div className="text-lg font-mono font-bold text-foreground">
              {avgDailySold != null ? avgDailySold.toFixed(1) : '---'}
            </div>
            <div className="text-[10px] text-muted-foreground">
              sales/day
            </div>
          </div>
        </div>
      ) : (
        <div className="p-8 text-center text-muted-foreground">
          <div className="text-sm">No sales data available</div>
          <div className="text-xs mt-1">for this time period</div>
        </div>
      )}
    </div>
  )
}

/**
 * Loading skeleton for ThreeMonthSnapshot
 */
export function ThreeMonthSnapshotSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn('border border-border rounded bg-card animate-pulse', className)}
      role="status"
      aria-busy="true"
      aria-label="Loading market snapshot"
    >
      {/* Header skeleton */}
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <div className="h-4 w-32 bg-muted rounded" />
        <div className="h-3 w-24 bg-muted rounded" />
      </div>

      {/* Stats grid skeleton */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="space-y-2">
            <div className="h-3 w-12 bg-muted rounded" />
            <div className="h-6 w-16 bg-muted rounded" />
            <div className="h-2 w-10 bg-muted rounded" />
          </div>
        ))}
      </div>

      <span className="sr-only">Loading market snapshot data...</span>
    </div>
  )
}
