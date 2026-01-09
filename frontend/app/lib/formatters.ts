/**
 * Formatting utilities
 * Single source of truth for price, date, and number formatting
 */

/**
 * Format a price value
 */
export function formatPrice(
  value: number | null | undefined,
  options: {
    currency?: string
    minimumFractionDigits?: number
    maximumFractionDigits?: number
    compact?: boolean
  } = {}
): string {
  if (value === null || value === undefined) return "—"

  const {
    currency = "USD",
    minimumFractionDigits = 2,
    maximumFractionDigits = 2,
    compact = false,
  } = options

  if (compact && value >= 1000) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      notation: "compact",
      minimumFractionDigits: 0,
      maximumFractionDigits: 1,
    }).format(value)
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits,
    maximumFractionDigits,
  }).format(value)
}

/**
 * Format a price change (delta) with sign
 */
export function formatPriceChange(
  value: number | null | undefined,
  options: { showSign?: boolean; suffix?: string } = {}
): string {
  if (value === null || value === undefined) return "—"

  const { showSign = true, suffix = "" } = options
  const sign = showSign && value > 0 ? "+" : ""

  return `${sign}${value.toFixed(2)}${suffix}`
}

/**
 * Format a percentage value
 */
export function formatPercent(
  value: number | null | undefined,
  options: { showSign?: boolean; decimals?: number } = {}
): string {
  if (value === null || value === undefined) return "—"

  const { showSign = true, decimals = 1 } = options
  const sign = showSign && value > 0 ? "+" : ""

  return `${sign}${value.toFixed(decimals)}%`
}

/**
 * Format a number with thousands separators
 */
export function formatNumber(
  value: number | null | undefined,
  options: { compact?: boolean } = {}
): string {
  if (value === null || value === undefined) return "—"

  const { compact = false } = options

  return new Intl.NumberFormat("en-US", {
    notation: compact ? "compact" : "standard",
  }).format(value)
}

/**
 * Format a date for display
 */
export function formatDate(
  date: Date | string | null | undefined,
  options: {
    format?: "short" | "medium" | "long" | "relative"
  } = {}
): string {
  if (!date) return "—"

  const { format = "medium" } = options
  const d = typeof date === "string" ? new Date(date) : date

  if (isNaN(d.getTime())) return "—"

  if (format === "relative") {
    return formatRelativeTime(d)
  }

  const formatOptionsMap: Record<"short" | "medium" | "long", Intl.DateTimeFormatOptions> = {
    short: { month: "numeric", day: "numeric" },
    medium: { month: "short", day: "numeric", year: "numeric" },
    long: { month: "long", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" },
  }
  const formatOptions = formatOptionsMap[format as "short" | "medium" | "long"]

  return new Intl.DateTimeFormat("en-US", formatOptions).format(d)
}

/**
 * Format relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(date: Date | string): string {
  const d = typeof date === "string" ? new Date(date) : date
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffSeconds = Math.floor(diffMs / 1000)
  const diffMinutes = Math.floor(diffSeconds / 60)
  const diffHours = Math.floor(diffMinutes / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSeconds < 60) return "just now"
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`

  return formatDate(d, { format: "short" })
}

/**
 * Format a time ago string for market data
 */
export function formatTimeAgo(date: Date | string | null | undefined): string {
  if (!date) return "—"
  const d = typeof date === "string" ? new Date(date) : date
  if (isNaN(d.getTime())) return "—"
  return formatRelativeTime(d)
}

/**
 * Get CSS classes for price change (positive = green, negative = red)
 */
export function getPriceChangeClasses(value: number | null | undefined): string {
  if (value === null || value === undefined || value === 0) {
    return "text-muted-foreground"
  }
  return value > 0 ? "text-success" : "text-destructive"
}

/**
 * Get icon direction for price change
 */
export function getPriceChangeDirection(value: number | null | undefined): "up" | "down" | "neutral" {
  if (value === null || value === undefined || value === 0) return "neutral"
  return value > 0 ? "up" : "down"
}

/**
 * Convert a card name to a URL-friendly slug
 * e.g., "Dragonmaster Cai" -> "dragonmaster-cai"
 */
export function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')  // Replace non-alphanumeric with hyphens
    .replace(/^-+|-+$/g, '')       // Trim leading/trailing hyphens
    .replace(/-+/g, '-')           // Collapse multiple hyphens
}
