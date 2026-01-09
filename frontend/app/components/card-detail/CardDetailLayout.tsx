/**
 * CardDetailLayout - TCGPlayer-inspired two-column responsive layout
 *
 * Desktop: 40% left (card hero) | 60% right (price box)
 * Tablet: 50/50 split
 * Mobile: Single column stack
 *
 * @see tasks.json E1-U1
 */

import { ReactNode, useState, useCallback } from 'react'
import { cn } from '@/lib/utils'
import { ChevronDown, ChevronRight, ExternalLink } from 'lucide-react'

type CardDetailLayoutProps = {
  /** Left column: Card image and product details */
  hero: ReactNode
  /** Right column: Price box with actions */
  priceBox: ReactNode
  /** Below fold: Market data, chart, listings */
  children: ReactNode
  /** Optional breadcrumb/navigation */
  navigation?: ReactNode
  /** Additional className */
  className?: string
}

export function CardDetailLayout({
  hero,
  priceBox,
  children,
  navigation,
  className
}: CardDetailLayoutProps) {
  return (
    <div className={cn("min-h-screen bg-background text-foreground font-mono", className)}>
      <main className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-6 pb-24 md:pb-8">
        {/* Navigation / Breadcrumbs */}
        {navigation && (
          <nav className="mb-6" aria-label="Breadcrumb">
            {navigation}
          </nav>
        )}

        {/* Hero Section - Two Column */}
        {/* Mobile (<768px): stack, Tablet+ (>=768px): side by side */}
        <div className="grid grid-cols-1 md:grid-cols-[minmax(250px,320px)_1fr] lg:grid-cols-[minmax(300px,380px)_1fr] xl:grid-cols-[400px_1fr] gap-4 md:gap-6 lg:gap-8 mb-8 items-start md:items-stretch">
          {/* Left Column - Card Hero - constrained width */}
          <div className="w-full max-w-[320px] md:max-w-none mx-auto md:mx-0">
            {hero}
          </div>

          {/* Right Column - Price Box */}
          <div className="w-full flex flex-col min-h-0">
            {priceBox}
          </div>
        </div>

        {/* Below Fold Content - Full Width */}
        {/* Consistent section spacing: 32px desktop, 24px mobile */}
        <div className="space-y-6 md:space-y-8">
          {children}
        </div>
      </main>
    </div>
  )
}

/**
 * Enhanced Section container with collapsible support, loading states, and badges
 *
 * Features:
 * - Consistent section spacing (32px desktop, 24px mobile)
 * - Section headers with optional 'View More' links
 * - Divider lines between major sections
 * - Collapsible sections with animation
 * - Loading skeleton states
 * - Badge support for counts/status
 *
 * @see tasks.json E1-U3
 */
export type SectionProps = {
  title?: string
  subtitle?: string
  /** Action button/link in header */
  action?: ReactNode
  /** Optional 'View More' link URL */
  viewMoreHref?: string
  /** Optional 'View More' link text (default: 'View More') */
  viewMoreText?: string
  /** Callback for 'View More' click */
  onViewMore?: () => void
  children: ReactNode
  className?: string
  /** Remove default padding for edge-to-edge content */
  noPadding?: boolean
  /** Whether section is collapsible */
  collapsible?: boolean
  /** Default collapsed state (only if collapsible) */
  defaultCollapsed?: boolean
  /** Controlled collapsed state */
  isCollapsed?: boolean
  /** Callback when collapse state changes */
  onCollapsedChange?: (collapsed: boolean) => void
  /** Whether content is loading */
  isLoading?: boolean
  /** Custom loading skeleton */
  loadingSkeleton?: ReactNode
  /** Badge content (count, status, etc.) */
  badge?: ReactNode
  /** Section ID for anchor links */
  id?: string
  /** Show divider below section */
  showDivider?: boolean
  /** Header size variant */
  headerSize?: 'sm' | 'md' | 'lg'
}

export function Section({
  title,
  subtitle,
  action,
  viewMoreHref,
  viewMoreText = 'View More',
  onViewMore,
  children,
  className,
  noPadding = false,
  collapsible = false,
  defaultCollapsed = false,
  isCollapsed: controlledCollapsed,
  onCollapsedChange,
  isLoading = false,
  loadingSkeleton,
  badge,
  id,
  showDivider = false,
  headerSize = 'sm'
}: SectionProps) {
  // Internal collapsed state (uncontrolled mode)
  const [internalCollapsed, setInternalCollapsed] = useState(defaultCollapsed)

  // Use controlled or uncontrolled collapsed state
  const isCollapsed = controlledCollapsed !== undefined ? controlledCollapsed : internalCollapsed

  const handleToggleCollapse = useCallback(() => {
    const newCollapsed = !isCollapsed
    if (controlledCollapsed === undefined) {
      setInternalCollapsed(newCollapsed)
    }
    onCollapsedChange?.(newCollapsed)
  }, [isCollapsed, controlledCollapsed, onCollapsedChange])

  const headerSizeClasses = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base'
  }[headerSize]

  const hasHeader = title || action || viewMoreHref || onViewMore || badge

  return (
    <section
      id={id}
      className={cn(
        "border border-border rounded-lg bg-card",
        showDivider && "mb-6 md:mb-8 pb-6 md:pb-8 border-b border-b-border/50",
        className
      )}
    >
      {hasHeader && (
        <div
          className={cn(
            "flex items-center justify-between px-4 py-3 border-b border-border",
            collapsible && "cursor-pointer select-none hover:bg-muted/30 transition-colors"
          )}
          onClick={collapsible ? handleToggleCollapse : undefined}
          onKeyDown={collapsible ? (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              handleToggleCollapse()
            }
          } : undefined}
          role={collapsible ? 'button' : undefined}
          tabIndex={collapsible ? 0 : undefined}
          aria-expanded={collapsible ? !isCollapsed : undefined}
          aria-controls={collapsible ? `section-content-${id || title}` : undefined}
        >
          <div className="flex items-center gap-3">
            {/* Collapse indicator */}
            {collapsible && (
              <span className="text-muted-foreground transition-transform duration-200">
                {isCollapsed ? (
                  <ChevronRight className="w-4 h-4" />
                ) : (
                  <ChevronDown className="w-4 h-4" />
                )}
              </span>
            )}

            <div>
              {title && (
                <h3 className={cn(
                  "font-bold uppercase tracking-widest",
                  headerSizeClasses
                )}>
                  {title}
                </h3>
              )}
              {subtitle && (
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  {subtitle}
                </p>
              )}
            </div>

            {/* Badge */}
            {badge && (
              <span className="px-2 py-0.5 text-[10px] font-semibold bg-muted rounded-full">
                {badge}
              </span>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3" onClick={(e) => e.stopPropagation()}>
            {action && (
              <div className="text-xs">
                {action}
              </div>
            )}

            {/* View More link */}
            {(viewMoreHref || onViewMore) && (
              viewMoreHref ? (
                <a
                  href={viewMoreHref}
                  className="flex items-center gap-1 text-xs text-brand-300 hover:text-brand-400 transition-colors"
                  onClick={(e) => {
                    e.stopPropagation()
                    onViewMore?.()
                  }}
                >
                  {viewMoreText}
                  <ExternalLink className="w-3 h-3" />
                </a>
              ) : (
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onViewMore?.()
                  }}
                  className="flex items-center gap-1 text-xs text-brand-300 hover:text-brand-400 transition-colors"
                >
                  {viewMoreText}
                  <ChevronRight className="w-3 h-3" />
                </button>
              )
            )}
          </div>
        </div>
      )}

      {/* Collapsible content wrapper */}
      <div
        id={collapsible ? `section-content-${id || title}` : undefined}
        className={cn(
          "overflow-hidden transition-all duration-300 ease-in-out",
          isCollapsed ? "max-h-0 opacity-0" : "max-h-[5000px] opacity-100"
        )}
      >
        <div className={noPadding ? '' : 'p-4'}>
          {isLoading ? (
            loadingSkeleton || <SectionLoadingSkeleton />
          ) : (
            children
          )}
        </div>
      </div>
    </section>
  )
}

/**
 * Default loading skeleton for sections
 */
export function SectionLoadingSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      <div className="h-4 bg-muted rounded w-3/4" />
      <div className="h-4 bg-muted rounded w-1/2" />
      <div className="h-4 bg-muted rounded w-2/3" />
      <div className="h-20 bg-muted rounded" />
    </div>
  )
}

/**
 * Two-column section for side-by-side content (e.g., chart + price points)
 */
type TwoColumnSectionProps = {
  left: ReactNode
  right: ReactNode
  /** Ratio of left column (default: equal split) */
  ratio?: '1:1' | '2:1' | '1:2' | '3:2' | '2:3'
  className?: string
  /** Gap size */
  gap?: 'sm' | 'md' | 'lg'
}

export function TwoColumnSection({
  left,
  right,
  ratio = '1:1',
  className,
  gap = 'md'
}: TwoColumnSectionProps) {
  const gridClass = {
    '1:1': 'lg:grid-cols-2',
    '2:1': 'lg:grid-cols-[2fr_1fr]',
    '1:2': 'lg:grid-cols-[1fr_2fr]',
    '3:2': 'lg:grid-cols-[3fr_2fr]',
    '2:3': 'lg:grid-cols-[2fr_3fr]',
  }[ratio]

  const gapClass = {
    sm: 'gap-4',
    md: 'gap-6',
    lg: 'gap-8'
  }[gap]

  return (
    <div className={cn(
      "grid grid-cols-1",
      gridClass,
      gapClass,
      className
    )}>
      {left}
      {right}
    </div>
  )
}

/**
 * Divider component for visual separation between sections
 */
export function SectionDivider({ className }: { className?: string }) {
  return (
    <div className={cn("h-px bg-border my-6 md:my-8", className)} />
  )
}
