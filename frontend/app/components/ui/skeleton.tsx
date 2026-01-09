/**
 * Skeleton - Reusable loading placeholder component
 *
 * Provides consistent skeleton styling across all components.
 * Uses `animate-pulse` for subtle loading animation.
 */

import { cn } from '@/lib/utils'

export type SkeletonProps = {
  className?: string
}

/**
 * Base skeleton element - animated placeholder
 */
export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        'animate-pulse rounded bg-muted',
        className
      )}
    />
  )
}

/**
 * Text skeleton - single line of text
 */
export function SkeletonText({
  className,
  width = 'w-24'
}: SkeletonProps & { width?: string }) {
  return (
    <Skeleton className={cn('h-4', width, className)} />
  )
}

/**
 * Heading skeleton - larger text placeholder
 */
export function SkeletonHeading({
  className,
  size = 'md'
}: SkeletonProps & { size?: 'sm' | 'md' | 'lg' | 'xl' }) {
  const heights = {
    sm: 'h-5',
    md: 'h-6',
    lg: 'h-8',
    xl: 'h-10'
  }
  return (
    <Skeleton className={cn(heights[size], 'w-48', className)} />
  )
}

/**
 * Button skeleton - placeholder for buttons
 */
export function SkeletonButton({
  className,
  size = 'md'
}: SkeletonProps & { size?: 'sm' | 'md' | 'lg' }) {
  const sizes = {
    sm: 'h-8 w-20',
    md: 'h-10 w-24',
    lg: 'h-12 w-32'
  }
  return (
    <Skeleton className={cn(sizes[size], 'rounded', className)} />
  )
}

/**
 * Avatar/image skeleton - circular or square image placeholder
 */
export function SkeletonImage({
  className,
  size = 'md',
  rounded = false
}: SkeletonProps & { size?: 'sm' | 'md' | 'lg' | 'xl'; rounded?: boolean }) {
  const sizes = {
    sm: 'h-8 w-8',
    md: 'h-12 w-12',
    lg: 'h-24 w-24',
    xl: 'h-48 w-48'
  }
  return (
    <Skeleton
      className={cn(
        sizes[size],
        rounded ? 'rounded-full' : 'rounded',
        className
      )}
    />
  )
}

/**
 * Chart skeleton - placeholder for chart/graph areas
 */
export function SkeletonChart({
  className,
  height = 'h-[300px]'
}: SkeletonProps & { height?: string }) {
  return (
    <div className={cn('w-full relative', height, className)}>
      <Skeleton className="absolute inset-0 rounded" />
      {/* Fake axis lines for visual hint */}
      <div className="absolute bottom-4 left-12 right-4 h-px bg-border/30" />
      <div className="absolute bottom-4 left-12 top-4 w-px bg-border/30" />
      {/* Fake data hint */}
      <div className="absolute inset-12 flex items-end justify-around gap-1 opacity-20">
        <Skeleton className="w-3 h-[20%]" />
        <Skeleton className="w-3 h-[35%]" />
        <Skeleton className="w-3 h-[45%]" />
        <Skeleton className="w-3 h-[30%]" />
        <Skeleton className="w-3 h-[55%]" />
        <Skeleton className="w-3 h-[40%]" />
        <Skeleton className="w-3 h-[50%]" />
        <Skeleton className="w-3 h-[65%]" />
        <Skeleton className="w-3 h-[45%]" />
        <Skeleton className="w-3 h-[35%]" />
      </div>
    </div>
  )
}

/**
 * Table row skeleton - placeholder for table data
 */
export function SkeletonTableRow({
  className,
  columns = 5
}: SkeletonProps & { columns?: number }) {
  return (
    <tr className={cn('animate-pulse', className)}>
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <Skeleton className="h-4 w-full max-w-[120px]" />
        </td>
      ))}
    </tr>
  )
}

/**
 * Multiple table rows skeleton
 */
export function SkeletonTableRows({
  rows = 5,
  columns = 5,
  className
}: SkeletonProps & { rows?: number; columns?: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonTableRow key={i} columns={columns} className={className} />
      ))}
    </>
  )
}

/**
 * Card skeleton - placeholder for card-like content
 */
export function SkeletonCard({
  className,
  hasImage = true,
  lines = 3
}: SkeletonProps & { hasImage?: boolean; lines?: number }) {
  return (
    <div className={cn('border border-border rounded-lg p-4 space-y-3', className)}>
      {hasImage && (
        <Skeleton className="h-32 w-full rounded" />
      )}
      <div className="space-y-2">
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton
            key={i}
            className={cn(
              'h-4',
              i === 0 ? 'w-3/4' : i === lines - 1 ? 'w-1/2' : 'w-full'
            )}
          />
        ))}
      </div>
    </div>
  )
}

/**
 * Home page table skeleton - matches market table structure
 */
export function HomeTableSkeleton({
  rows = 10,
  showHeader = true,
  className
}: SkeletonProps & { rows?: number; showHeader?: boolean }) {
  return (
    <div className={cn('animate-pulse', className)}>
      {/* Table header */}
      {showHeader && (
        <div className="flex items-center gap-4 px-4 py-2 border-b border-border bg-muted/30">
          <Skeleton className="h-4 w-8" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-16 ml-auto" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-16" />
        </div>
      )}
      {/* Table rows */}
      <div className="divide-y divide-border/50">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 px-4 py-3">
            {/* Rank */}
            <Skeleton className="h-4 w-6" />
            {/* Name */}
            <div className="flex items-center gap-3 flex-1">
              <Skeleton className="h-10 w-10 rounded" />
              <div className="space-y-1">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-3 w-20" />
              </div>
            </div>
            {/* Price */}
            <Skeleton className="h-5 w-16" />
            {/* Change */}
            <Skeleton className="h-4 w-14" />
            {/* Volume */}
            <Skeleton className="h-4 w-12" />
            {/* Listings */}
            <Skeleton className="h-4 w-10" />
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * Mobile card list skeleton
 */
export function MobileCardListSkeleton({
  count = 8,
  className
}: SkeletonProps & { count?: number }) {
  return (
    <div className={cn('space-y-3 p-3', className)}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 p-3 border border-border rounded-lg animate-pulse">
          {/* Card image */}
          <Skeleton className="h-16 w-12 rounded shrink-0" />
          {/* Card info */}
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <div className="flex items-center gap-2">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-3 w-12" />
            </div>
          </div>
          {/* Price */}
          <div className="text-right space-y-1">
            <Skeleton className="h-5 w-16 ml-auto" />
            <Skeleton className="h-3 w-12 ml-auto" />
          </div>
        </div>
      ))}
    </div>
  )
}

/**
 * Product gallery skeleton - horizontal scroll of cards
 */
export function ProductGallerySkeleton({ className }: SkeletonProps) {
  return (
    <div className={cn('mb-6', className)}>
      {/* Tab buttons */}
      <div className="flex items-center gap-2 mb-3">
        <Skeleton className="h-8 w-28 rounded" />
        <Skeleton className="h-8 w-24 rounded" />
        <Skeleton className="h-8 w-20 rounded" />
      </div>
      {/* Horizontal card scroll */}
      <div className="flex gap-3 overflow-hidden">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="w-[140px] shrink-0 animate-pulse">
            <Skeleton className="aspect-[2.5/3.5] w-full rounded-lg mb-2" />
            <Skeleton className="h-4 w-3/4 mb-1" />
            <Skeleton className="h-5 w-1/2" />
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * Page-level skeleton for card detail page
 * Matches the CardDetailLayout structure
 */
export function CardDetailPageSkeleton() {
  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Back button skeleton */}
        <div className="mb-6">
          <Skeleton className="h-8 w-32" />
        </div>

        {/* Two-column layout */}
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(300px,2fr)_minmax(320px,1fr)] gap-8">
          {/* Left column - Card Hero */}
          <div className="space-y-4">
            {/* Card image */}
            <Skeleton className="aspect-[3/4] w-full max-w-[400px] rounded-lg" />
            {/* Card name */}
            <Skeleton className="h-8 w-3/4" />
            {/* Set name */}
            <Skeleton className="h-5 w-1/2" />
            {/* Product details grid */}
            <div className="grid grid-cols-2 gap-4 pt-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="space-y-1">
                  <Skeleton className="h-3 w-16" />
                  <Skeleton className="h-5 w-24" />
                </div>
              ))}
            </div>
          </div>

          {/* Right column - Price Box */}
          <div>
            <div className="border border-border rounded-lg bg-card">
              {/* Treatment selector */}
              <div className="p-4 border-b border-border">
                <Skeleton className="h-3 w-24 mb-2" />
                <Skeleton className="h-10 w-full" />
              </div>
              {/* Price display */}
              <div className="p-4 space-y-4">
                <div>
                  <Skeleton className="h-3 w-20 mb-2" />
                  <Skeleton className="h-12 w-32" />
                </div>
                <Skeleton className="h-4 w-28" />
                <div className="grid grid-cols-2 gap-4 pt-3 border-t border-border/50">
                  <div className="space-y-1">
                    <Skeleton className="h-3 w-16" />
                    <Skeleton className="h-6 w-12" />
                  </div>
                  <div className="space-y-1">
                    <Skeleton className="h-3 w-20" />
                    <Skeleton className="h-6 w-16" />
                  </div>
                </div>
              </div>
              {/* Actions */}
              <div className="p-4 border-t border-border space-y-2">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            </div>
          </div>
        </div>

        {/* Below-fold sections */}
        <div className="mt-8 space-y-6">
          {/* Price Points */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="border border-border rounded p-4 space-y-2">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-8 w-24" />
              </div>
            ))}
          </div>

          {/* Chart */}
          <div className="border border-border rounded bg-card p-4">
            <div className="flex justify-between items-center mb-4">
              <Skeleton className="h-4 w-32" />
              <div className="flex gap-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-8 w-12" />
                ))}
              </div>
            </div>
            <SkeletonChart height="h-[300px]" />
          </div>

          {/* Table */}
          <div className="border border-border rounded bg-card overflow-hidden">
            <div className="px-6 py-4 border-b border-border">
              <Skeleton className="h-4 w-40" />
            </div>
            <table className="w-full">
              <thead className="bg-muted/30">
                <tr>
                  {Array.from({ length: 5 }).map((_, i) => (
                    <th key={i} className="px-4 py-3">
                      <Skeleton className="h-3 w-16" />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                <SkeletonTableRows rows={5} columns={5} />
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
