import * as React from "react"
import { cn } from "@/lib/utils"
import { ChevronRight, TrendingUp, TrendingDown, Minus } from "lucide-react"
import { formatPrice, formatPercent, getPriceChangeClasses } from "@/lib/formatters"
import { getTreatmentStyle } from "@/lib/treatments"

export interface MobileCardItem {
  id: string | number
  name: string
  subtitle?: string
  treatment?: string
  price?: number | null
  priceChange?: number | null
  secondaryValue?: string
  imageUrl?: string
  onClick?: () => void
}

interface MobileCardListProps {
  items: MobileCardItem[]
  isLoading?: boolean
  emptyState?: React.ReactNode
  className?: string
  showChevron?: boolean
}

/**
 * Mobile-friendly card list view as alternative to tables
 * Use on screens < 768px (md breakpoint)
 */
export function MobileCardList({
  items,
  isLoading,
  emptyState,
  className,
  showChevron = true,
}: MobileCardListProps) {
  if (isLoading) {
    return (
      <div className={cn("space-y-3", className)}>
        {Array.from({ length: 5 }).map((_, i) => (
          <MobileCardSkeleton key={i} />
        ))}
      </div>
    )
  }

  if (items.length === 0 && emptyState) {
    return <>{emptyState}</>
  }

  return (
    <div className={cn("space-y-2", className)} role="list">
      {items.map((item) => (
        <MobileCardItem key={item.id} item={item} showChevron={showChevron} />
      ))}
    </div>
  )
}

function MobileCardItem({
  item,
  showChevron,
}: {
  item: MobileCardItem
  showChevron: boolean
}) {
  const treatmentStyle = getTreatmentStyle(item.treatment)
  const isClickable = !!item.onClick

  const PriceChangeIcon = !item.priceChange || item.priceChange === 0
    ? Minus
    : item.priceChange > 0
    ? TrendingUp
    : TrendingDown

  const content = (
    <>
      {/* Left: Image or treatment indicator */}
      {item.imageUrl ? (
        <img
          src={item.imageUrl}
          alt=""
          className="w-12 h-12 rounded object-cover flex-shrink-0"
        />
      ) : (
        <div
          className={cn(
            "w-12 h-12 rounded flex items-center justify-center flex-shrink-0",
            treatmentStyle.bg,
            treatmentStyle.border,
            "border"
          )}
          aria-hidden="true"
        >
          <span className={cn("text-micro font-medium", treatmentStyle.text)}>
            {item.treatment?.charAt(0) || "—"}
          </span>
        </div>
      )}

      {/* Center: Name and subtitle */}
      <div className="flex-1 min-w-0 px-3">
        <p className="text-sm font-medium text-foreground truncate">
          {item.name}
        </p>
        {item.subtitle && (
          <p className="text-caption text-muted-foreground truncate">
            {item.subtitle}
          </p>
        )}
        {item.treatment && (
          <span
            className={cn(
              "inline-block mt-1 px-1.5 py-0.5 rounded text-micro font-medium",
              treatmentStyle.bg,
              treatmentStyle.text
            )}
          >
            {item.treatment}
          </span>
        )}
      </div>

      {/* Right: Price and change */}
      <div className="text-right flex-shrink-0">
        {item.price !== undefined && (
          <p className="text-sm font-mono font-semibold text-foreground">
            {formatPrice(item.price)}
          </p>
        )}
        {item.priceChange !== undefined && (
          <p
            className={cn(
              "text-caption font-medium flex items-center justify-end gap-0.5",
              getPriceChangeClasses(item.priceChange)
            )}
          >
            <PriceChangeIcon className="w-3 h-3" aria-hidden="true" />
            {formatPercent(item.priceChange)}
          </p>
        )}
        {item.secondaryValue && (
          <p className="text-caption text-muted-foreground">
            {item.secondaryValue}
          </p>
        )}
      </div>

      {/* Chevron for clickable items */}
      {isClickable && showChevron && (
        <ChevronRight
          className="w-4 h-4 text-muted-foreground flex-shrink-0 ml-1"
          aria-hidden="true"
        />
      )}
    </>
  )

  if (isClickable) {
    return (
      <button
        onClick={item.onClick}
        className={cn(
          "w-full flex items-center p-3 bg-card border border-border rounded-lg",
          "hover:bg-accent/50 transition-colors",
          "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
          "text-left"
        )}
        role="listitem"
      >
        {content}
      </button>
    )
  }

  return (
    <div
      className="flex items-center p-3 bg-card border border-border rounded-lg"
      role="listitem"
    >
      {content}
    </div>
  )
}

function MobileCardSkeleton() {
  return (
    <div className="flex items-center p-3 bg-card border border-border rounded-lg animate-pulse">
      <div className="w-12 h-12 rounded bg-muted flex-shrink-0" />
      <div className="flex-1 px-3 space-y-2">
        <div className="h-4 bg-muted rounded w-3/4" />
        <div className="h-3 bg-muted rounded w-1/2" />
      </div>
      <div className="space-y-2">
        <div className="h-4 bg-muted rounded w-16" />
        <div className="h-3 bg-muted rounded w-12 ml-auto" />
      </div>
    </div>
  )
}

/**
 * Responsive wrapper that shows table on desktop, cards on mobile
 */
export function ResponsiveDataView({
  mobileItems,
  desktopContent,
  isLoading,
  emptyState,
  breakpoint = "md",
}: {
  mobileItems: MobileCardItem[]
  desktopContent: React.ReactNode
  isLoading?: boolean
  emptyState?: React.ReactNode
  breakpoint?: "sm" | "md" | "lg"
}) {
  const breakpointClasses = {
    sm: { mobile: "sm:hidden", desktop: "hidden sm:block" },
    md: { mobile: "md:hidden", desktop: "hidden md:block" },
    lg: { mobile: "lg:hidden", desktop: "hidden lg:block" },
  }

  const classes = breakpointClasses[breakpoint]

  return (
    <>
      {/* Mobile: Card list */}
      <div className={classes.mobile}>
        <MobileCardList
          items={mobileItems}
          isLoading={isLoading}
          emptyState={emptyState}
        />
      </div>

      {/* Desktop: Table or other content */}
      <div className={classes.desktop}>{desktopContent}</div>
    </>
  )
}
