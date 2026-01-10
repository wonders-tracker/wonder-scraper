/**
 * PlatformBadge - Consistent platform display for listings
 *
 * Eliminates 25+ lines of duplicate platform color logic across the codebase.
 * Supports eBay, Blokpax, OpenSea, and can be extended for other platforms.
 *
 * Usage:
 * <PlatformBadge platform="ebay" />                    // Text badge (default)
 * <PlatformBadge platform="blokpax" variant="icon" />  // Small icon only
 * <PlatformBadge platform="opensea" size="sm" />       // Small size
 */

import { cn } from '@/lib/utils'

export type Platform = 'ebay' | 'blokpax' | 'opensea' | 'tcgplayer'

// Platform color configuration - single source of truth
// Uses actual brand colors where appropriate
const PLATFORM_COLORS = {
  ebay: {
    // eBay's actual brand red
    bg: 'bg-[#e53238]/10',
    text: 'text-[#e53238]',
    border: 'border-[#e53238]/20',
    solid: 'bg-[#e53238] text-white',
    iconLetter: 'e',
  },
  blokpax: {
    // Cyan for Blokpax (matches their branding)
    bg: 'bg-cyan-500/10',
    text: 'text-cyan-400',
    border: 'border-cyan-500/20',
    solid: 'bg-cyan-500 text-white',
    iconLetter: 'B',
  },
  opensea: {
    // Blue for OpenSea
    bg: 'bg-blue-500/10',
    text: 'text-blue-400',
    border: 'border-blue-500/20',
    solid: 'bg-blue-500 text-white',
    iconLetter: 'O',
  },
  tcgplayer: {
    // Purple for TCGPlayer
    bg: 'bg-purple-500/10',
    text: 'text-purple-400',
    border: 'border-purple-500/20',
    solid: 'bg-purple-500 text-white',
    iconLetter: 'T',
  },
} as const

// Fallback for unknown platforms
const FALLBACK_COLORS = {
  bg: 'bg-muted',
  text: 'text-muted-foreground',
  border: 'border-border',
  solid: 'bg-muted text-foreground',
  iconLetter: '?',
}

export interface PlatformBadgeProps {
  /** The platform name */
  platform: string | null | undefined
  /** Display variant */
  variant?: 'badge' | 'icon' | 'solid'
  /** Size preset */
  size?: 'xs' | 'sm' | 'md'
  /** Show border */
  bordered?: boolean
  /** Additional classes */
  className?: string
}

const sizeStyles = {
  xs: 'text-[8px] px-1 py-0.5 rounded',
  sm: 'text-[10px] px-1.5 py-0.5 rounded',
  md: 'text-xs px-2 py-1 rounded-md',
}

const iconSizeStyles = {
  xs: 'w-4 h-4 text-[8px] rounded',
  sm: 'w-5 h-5 text-[10px] rounded',
  md: 'w-6 h-6 text-xs rounded-md',
}

export function PlatformBadge({
  platform,
  variant = 'badge',
  size = 'sm',
  bordered = false,
  className,
}: PlatformBadgeProps) {
  if (!platform) return null

  // Normalize platform name
  const normalizedPlatform = platform.toLowerCase() as Platform
  const colors = PLATFORM_COLORS[normalizedPlatform] || FALLBACK_COLORS

  // Icon variant - small square with letter
  if (variant === 'icon') {
    return (
      <div
        className={cn(
          'flex items-center justify-center font-bold',
          iconSizeStyles[size],
          colors.bg,
          colors.text,
          className
        )}
        title={platform}
      >
        {colors.iconLetter || platform.charAt(0).toUpperCase()}
      </div>
    )
  }

  // Solid variant - filled background
  if (variant === 'solid') {
    return (
      <span
        className={cn(
          'inline-block font-bold uppercase',
          sizeStyles[size],
          colors.solid,
          className
        )}
      >
        {platform}
      </span>
    )
  }

  // Default badge variant - transparent background with colored text
  return (
    <span
      className={cn(
        'inline-block font-bold uppercase',
        sizeStyles[size],
        colors.bg,
        colors.text,
        bordered && 'border',
        bordered && colors.border,
        className
      )}
    >
      {platform}
    </span>
  )
}

/**
 * PlatformIcon - Compact icon variant (convenience wrapper)
 */
export function PlatformIcon({
  platform,
  size = 'sm',
  className,
}: Pick<PlatformBadgeProps, 'platform' | 'size' | 'className'>) {
  return (
    <PlatformBadge
      platform={platform}
      variant="icon"
      size={size}
      className={className}
    />
  )
}

/**
 * Get platform color classes directly (for custom usage)
 */
export function getPlatformColors(platform: string | null | undefined) {
  if (!platform) return FALLBACK_COLORS
  const normalized = platform.toLowerCase() as Platform
  return PLATFORM_COLORS[normalized] || FALLBACK_COLORS
}

/**
 * Get just the text color class for a platform
 */
export function getPlatformTextColor(platform: string | null | undefined): string {
  return getPlatformColors(platform).text
}

export { PLATFORM_COLORS }
