/**
 * PricePoints - TCGPlayer-inspired key market metrics display
 *
 * Displays essential price points and market indicators:
 * - Market Price (FMP) with calculation tooltip
 * - Most Recent Sale (price and date)
 * - Volatility indicator (visual slider bar)
 * - Listed Median (from active listings)
 * - Current Quantity (inventory count)
 * - Sellers (seller count)
 *
 * @see tasks.json E3-U1
 */

import { cn } from '@/lib/utils'
import { Tooltip } from '../ui/tooltip'
import { formatPrice, formatNumber, formatDate } from '@/lib/formatters'
import {
  Package,
  Users,
  Info,
  Activity,
  Clock,
  DollarSign,
  BarChart3
} from 'lucide-react'

/** Volatility level for styling */
export type VolatilityLevel = 'low' | 'medium' | 'high'

export type PricePointsProps = {
  /** Fair Market Price (calculated weighted average) */
  marketPrice?: number | null
  /** Most recent sale price */
  recentSalePrice?: number | null
  /** Date of most recent sale */
  recentSaleDate?: Date | string | null
  /** Price volatility level */
  volatility?: VolatilityLevel | null
  /** Volatility percentage (optional, for display) */
  volatilityPercent?: number | null
  /** Median price of active listings */
  listedMedian?: number | null
  /** Current inventory count */
  quantity?: number | null
  /** Number of unique sellers */
  sellerCount?: number | null
  /** Whether data is loading */
  isLoading?: boolean
  /** Additional className */
  className?: string
}

/** Volatility styling configuration */
const volatilityConfig: Record<VolatilityLevel, { color: string; label: string; position: number }> = {
  low: {
    color: 'bg-green-500',
    label: 'Low',
    position: 16.67 // 1/6 of the way
  },
  medium: {
    color: 'bg-yellow-500',
    label: 'Med',
    position: 50 // middle
  },
  high: {
    color: 'bg-red-500',
    label: 'High',
    position: 83.33 // 5/6 of the way
  }
}

/** Tooltip content for each metric */
const tooltipContent = {
  marketPrice: 'Fair Market Price is calculated using a MAD-trimmed weighted average of recent sales, excluding outliers for accuracy.',
  recentSale: 'The most recent completed sale for this card, including date and price.',
  volatility: 'Price volatility measures how much the price fluctuates. Low = stable pricing, High = frequent price swings.',
  listedMedian: 'The median (middle) price of all currently active listings for this card.',
  quantity: 'Total number of listings currently available across all platforms.',
  sellers: 'Number of unique sellers with active listings for this card.'
}

/**
 * Volatility Slider - Minimal visual bar with triangle markers
 */
function VolatilitySlider({
  level,
  isLoading
}: {
  level?: VolatilityLevel | null
  isLoading?: boolean
}) {
  if (isLoading) {
    return (
      <div className="h-6 w-full bg-muted animate-pulse rounded" role="status" aria-label="Loading volatility" />
    )
  }

  const config = level ? volatilityConfig[level] : null
  const position = config?.position ?? 50

  return (
    <div className="w-full" role="img" aria-label={`Price volatility: ${config?.label ?? 'Unknown'}`}>
      {/* Triangle markers row */}
      <div className="relative h-3 mb-0.5">
        {/* Low marker */}
        <div className="absolute left-[16.67%] -translate-x-1/2 text-muted-foreground/50" style={{ fontSize: '8px' }}>
          ▼
        </div>
        {/* Med marker */}
        <div className="absolute left-1/2 -translate-x-1/2 text-muted-foreground/50" style={{ fontSize: '8px' }}>
          ▼
        </div>
        {/* High marker */}
        <div className="absolute left-[83.33%] -translate-x-1/2 text-muted-foreground/50" style={{ fontSize: '8px' }}>
          ▼
        </div>
      </div>

      {/* Slider track */}
      <div className="relative h-1.5 rounded-full bg-muted-foreground/20">
        {/* Filled portion up to indicator */}
        <div
          className="absolute left-0 top-0 h-full rounded-full bg-brand-500/70 transition-all duration-300"
          style={{ width: `${position}%` }}
        />

        {/* Indicator dot */}
        <div
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 transition-all duration-300"
          style={{ left: `${position}%` }}
        >
          <div className="w-2.5 h-2.5 rounded-full bg-brand-500 border border-background" />
        </div>
      </div>
    </div>
  )
}

/**
 * Metric label with tooltip
 */
function MetricLabel({
  icon: Icon,
  label,
  tooltipText
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  tooltipText: string
}) {
  return (
    <div className="flex items-center gap-1.5 mb-0.5">
      <Icon className="w-3 h-3 text-muted-foreground" aria-hidden="true" />
      <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
        {label}
      </span>
      <Tooltip content={tooltipText}>
        <button
          type="button"
          className="inline-flex items-center justify-center focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded"
          aria-label={`More information about ${label}`}
        >
          <Info className="w-3 h-3 text-muted-foreground cursor-help hover:text-foreground transition-colors" aria-hidden="true" />
        </button>
      </Tooltip>
    </div>
  )
}

/**
 * Loading skeleton for a metric value
 */
function MetricSkeleton() {
  return <div className="h-7 w-20 bg-muted animate-pulse rounded" role="status" aria-label="Loading" />
}

/**
 * Metric value display
 */
function MetricValue({
  value,
  highlight = false
}: {
  value?: React.ReactNode
  highlight?: boolean
}) {
  return (
    <div
      className={cn(
        'text-xl font-mono font-bold',
        highlight ? 'text-brand-300' : 'text-foreground'
      )}
      aria-live="polite"
    >
      {value ?? <span className="text-muted-foreground">---</span>}
    </div>
  )
}

export function PricePoints({
  marketPrice,
  recentSalePrice,
  recentSaleDate,
  volatility,
  listedMedian,
  quantity,
  sellerCount,
  isLoading = false,
  className
}: PricePointsProps) {
  return (
    <div className={cn('space-y-4', className)}>
      {/* Top row: Market Price + Recent Sale */}
      <div className="grid grid-cols-2 gap-4">
        {/* Market Price (FMP) */}
        <div>
          <MetricLabel
            icon={DollarSign}
            label="Market Price"
            tooltipText={tooltipContent.marketPrice}
          />
          {isLoading ? (
            <MetricSkeleton />
          ) : (
            <MetricValue
              value={marketPrice != null ? formatPrice(marketPrice) : undefined}
              highlight
            />
          )}
        </div>

        {/* Most Recent Sale */}
        <div>
          <MetricLabel
            icon={Clock}
            label="Recent Sale"
            tooltipText={tooltipContent.recentSale}
          />
          {isLoading ? (
            <MetricSkeleton />
          ) : (
            <div className="flex flex-col" aria-live="polite">
              <MetricValue value={recentSalePrice != null ? formatPrice(recentSalePrice) : undefined} />
              {recentSaleDate && (
                <span className="text-xs text-muted-foreground">
                  {formatDate(recentSaleDate, { format: 'relative' })}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Volatility Slider - Full width */}
      <div>
        <MetricLabel
          icon={Activity}
          label="Volatility"
          tooltipText={tooltipContent.volatility}
        />
        <VolatilitySlider level={volatility} isLoading={isLoading} />
      </div>

      {/* Bottom row: Listed Median, Quantity, Sellers */}
      <div className="grid grid-cols-3 gap-4">
        {/* Listed Median */}
        <div>
          <MetricLabel
            icon={BarChart3}
            label="Listed Median"
            tooltipText={tooltipContent.listedMedian}
          />
          {isLoading ? (
            <MetricSkeleton />
          ) : (
            <MetricValue value={listedMedian != null ? formatPrice(listedMedian) : undefined} />
          )}
        </div>

        {/* Current Quantity */}
        <div>
          <MetricLabel
            icon={Package}
            label="Quantity"
            tooltipText={tooltipContent.quantity}
          />
          {isLoading ? (
            <MetricSkeleton />
          ) : (
            <MetricValue value={quantity != null ? formatNumber(quantity) : undefined} />
          )}
        </div>

        {/* Sellers */}
        <div>
          <MetricLabel
            icon={Users}
            label="Sellers"
            tooltipText={tooltipContent.sellers}
          />
          {isLoading ? (
            <MetricSkeleton />
          ) : (
            <MetricValue value={sellerCount != null ? formatNumber(sellerCount) : undefined} />
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * Loading skeleton for PricePoints
 */
export function PricePointsSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn('space-y-4 animate-pulse', className)}
      role="status"
      aria-busy="true"
      aria-label="Loading price metrics"
    >
      {/* Top row skeleton */}
      <div className="grid grid-cols-2 gap-4">
        {[0, 1].map((i) => (
          <div key={i}>
            <div className="flex items-center gap-1.5 mb-0.5">
              <div className="w-3 h-3 bg-muted rounded" />
              <div className="h-2.5 w-16 bg-muted rounded" />
              <div className="w-3 h-3 bg-muted rounded" />
            </div>
            <div className="h-7 w-20 bg-muted rounded" />
          </div>
        ))}
      </div>

      {/* Volatility slider skeleton */}
      <div>
        <div className="flex items-center gap-1.5 mb-0.5">
          <div className="w-3 h-3 bg-muted rounded" />
          <div className="h-2.5 w-16 bg-muted rounded" />
          <div className="w-3 h-3 bg-muted rounded" />
        </div>
        <div className="h-6 w-full bg-muted rounded" />
      </div>

      {/* Bottom row skeleton */}
      <div className="grid grid-cols-3 gap-4">
        {[0, 1, 2].map((i) => (
          <div key={i}>
            <div className="flex items-center gap-1.5 mb-0.5">
              <div className="w-3 h-3 bg-muted rounded" />
              <div className="h-2.5 w-16 bg-muted rounded" />
              <div className="w-3 h-3 bg-muted rounded" />
            </div>
            <div className="h-7 w-20 bg-muted rounded" />
          </div>
        ))}
      </div>

      <span className="sr-only">Loading price information, please wait...</span>
    </div>
  )
}
