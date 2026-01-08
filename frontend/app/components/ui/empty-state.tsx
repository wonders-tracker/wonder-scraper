import * as React from "react"
import { cn } from "@/lib/utils"
import {
  Package,
  Search,
  TrendingUp,
  Wallet,
  AlertCircle,
  FolderOpen,
  type LucideIcon
} from "lucide-react"

// Preset icons for common empty states
const presetIcons: Record<string, LucideIcon> = {
  cards: Package,
  search: Search,
  market: TrendingUp,
  portfolio: Wallet,
  error: AlertCircle,
  folder: FolderOpen,
}

export interface EmptyStateProps {
  /** Icon to display - can be a preset name or custom ReactNode */
  icon?: keyof typeof presetIcons | React.ReactNode
  /** Main heading */
  title: string
  /** Description text */
  description?: string
  /** Call-to-action button or element */
  action?: React.ReactNode
  /** Additional className */
  className?: string
  /** Size variant */
  size?: "sm" | "md" | "lg"
}

export function EmptyState({
  icon = "folder",
  title,
  description,
  action,
  className,
  size = "md",
}: EmptyStateProps) {
  const sizeClasses = {
    sm: {
      container: "py-8",
      iconWrapper: "w-10 h-10 mb-3",
      icon: "w-5 h-5",
      title: "text-sm font-medium",
      description: "text-xs max-w-xs",
    },
    md: {
      container: "py-12",
      iconWrapper: "w-14 h-14 mb-4",
      icon: "w-7 h-7",
      title: "text-base font-semibold",
      description: "text-sm max-w-sm",
    },
    lg: {
      container: "py-16",
      iconWrapper: "w-16 h-16 mb-5",
      icon: "w-8 h-8",
      title: "text-lg font-bold",
      description: "text-base max-w-md",
    },
  }

  const sizes = sizeClasses[size]

  // Resolve icon
  const IconComponent = typeof icon === "string" ? presetIcons[icon] : null
  const iconElement = IconComponent ? (
    <IconComponent className={cn(sizes.icon, "text-muted-foreground")} />
  ) : (
    icon
  )

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center px-4",
        sizes.container,
        className
      )}
      role="status"
      aria-live="polite"
    >
      <div
        className={cn(
          "rounded-full bg-muted flex items-center justify-center",
          sizes.iconWrapper
        )}
        aria-hidden="true"
      >
        {iconElement}
      </div>
      <h3 className={cn(sizes.title, "text-foreground mb-1")}>{title}</h3>
      {description && (
        <p className={cn(sizes.description, "text-muted-foreground mb-4")}>
          {description}
        </p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

// Pre-built empty states for common scenarios
export function NoResultsState({
  searchTerm,
  onClear,
}: {
  searchTerm?: string
  onClear?: () => void
}) {
  return (
    <EmptyState
      icon="search"
      title="No results found"
      description={
        searchTerm
          ? `No items match "${searchTerm}". Try adjusting your search or filters.`
          : "Try adjusting your search or filters."
      }
      action={
        onClear && (
          <button
            onClick={onClear}
            className="text-sm text-primary hover:underline focus:outline-none focus:ring-2 focus:ring-ring rounded"
          >
            Clear filters
          </button>
        )
      }
    />
  )
}

export function EmptyPortfolioState({ onAdd }: { onAdd?: () => void }) {
  return (
    <EmptyState
      icon="portfolio"
      title="Your portfolio is empty"
      description="Start tracking your collection by adding cards from the dashboard or card detail pages."
      action={
        onAdd && (
          <button
            onClick={onAdd}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-primary text-primary-foreground rounded-md hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
          >
            Browse Cards
          </button>
        )
      }
    />
  )
}

export function EmptyMarketDataState() {
  return (
    <EmptyState
      icon="market"
      title="No market data available"
      description="Market data will appear here once listings and sales are tracked."
      size="sm"
    />
  )
}

export function ErrorState({
  title = "Something went wrong",
  description = "An error occurred while loading this content. Please try again.",
  onRetry,
}: {
  title?: string
  description?: string
  onRetry?: () => void
}) {
  return (
    <EmptyState
      icon="error"
      title={title}
      description={description}
      action={
        onRetry && (
          <button
            onClick={onRetry}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
          >
            Try Again
          </button>
        )
      }
    />
  )
}
