import { clsx } from 'clsx'
import { Tooltip } from './ui/tooltip'

interface SellerBadgeProps {
  sellerName: string | null | undefined
  feedbackScore?: number | null
  feedbackPercent?: number | null
  showDetails?: boolean
  size?: 'xs' | 'sm' | 'md'
  className?: string
}

/**
 * Get color class based on feedback percentage.
 * Green: >= 98% (trusted seller)
 * Yellow: 95-98% (caution)
 * Red: < 95% (high risk)
 */
function getFeedbackColor(percent: number | null | undefined): string {
  if (percent === null || percent === undefined) return 'text-gray-500'
  if (percent >= 98) return 'text-green-500'
  if (percent >= 95) return 'text-yellow-500'
  return 'text-red-500'
}

/**
 * Get color class based on feedback score (number of reviews).
 * Green: >= 100 (established seller)
 * Yellow: 10-99 (newer seller)
 * Red: < 10 (very new/risky)
 */
function getScoreColor(score: number | null | undefined): string {
  if (score === null || score === undefined) return 'text-gray-500'
  if (score >= 100) return 'text-green-500'
  if (score >= 10) return 'text-yellow-500'
  return 'text-red-500'
}

const SIZE_CLASSES = {
  xs: 'text-[10px]',
  sm: 'text-xs',
  md: 'text-sm',
}

export function SellerBadge({
  sellerName,
  feedbackScore,
  feedbackPercent,
  showDetails = true,
  size = 'xs',
  className,
}: SellerBadgeProps) {
  // Handle null/undefined/empty seller
  if (!sellerName) {
    return (
      <span className={clsx('text-gray-500', SIZE_CLASSES[size], className)}>
        —
      </span>
    )
  }

  // Handle "seller_unknown" (historical unrecoverable listings)
  if (sellerName === 'seller_unknown') {
    return (
      <Tooltip content="Seller data unavailable for historical listings">
        <span className={clsx('text-gray-500 italic', SIZE_CLASSES[size], className)}>
          Unknown
        </span>
      </Tooltip>
    )
  }

  const hasDetails = feedbackScore !== null && feedbackScore !== undefined &&
                     feedbackPercent !== null && feedbackPercent !== undefined

  // Build tooltip content
  const tooltipContent = hasDetails
    ? `${sellerName}\n${feedbackScore.toLocaleString()} reviews • ${feedbackPercent.toFixed(1)}% positive`
    : sellerName

  // Simple display without details
  if (!showDetails || !hasDetails) {
    return (
      <Tooltip content={tooltipContent}>
        <span className={clsx('font-medium truncate max-w-[120px] inline-block', SIZE_CLASSES[size], className)}>
          {sellerName}
        </span>
      </Tooltip>
    )
  }

  // Full display with score and percent
  return (
    <Tooltip content={tooltipContent}>
      <span className={clsx('inline-flex items-center gap-1', SIZE_CLASSES[size], className)}>
        <span className="font-medium truncate max-w-[100px]">{sellerName}</span>
        <span className="text-gray-500">
          (<span className={getScoreColor(feedbackScore)}>{feedbackScore}</span>
          <span className="mx-0.5">•</span>
          <span className={getFeedbackColor(feedbackPercent)}>{feedbackPercent?.toFixed(0)}%</span>)
        </span>
      </span>
    </Tooltip>
  )
}

export default SellerBadge
