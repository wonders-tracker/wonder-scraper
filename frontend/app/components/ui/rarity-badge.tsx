/**
 * RarityBadge - Consistent rarity display for cards
 *
 * Eliminates 30+ lines of duplicate rarity color logic across the codebase.
 *
 * Usage:
 * <RarityBadge rarity="Mythic" />                    // Text only (default)
 * <RarityBadge rarity="Legendary" variant="solid" /> // Solid pill badge
 * <RarityBadge rarity="Epic" size="sm" />            // Small size
 */

import { cn } from '@/lib/utils'

export type Rarity = 'Mythic' | 'Legendary' | 'Epic' | 'Rare' | 'Uncommon' | 'Common' | 'Sealed'

// Rarity color configuration - single source of truth
const RARITY_COLORS = {
  Mythic: {
    text: 'text-amber-400',
    solid: 'text-amber-900 bg-amber-400',
    glow: 'shadow-amber-500/50',
  },
  Legendary: {
    text: 'text-orange-400',
    solid: 'text-orange-900 bg-orange-400',
    glow: 'shadow-orange-500/50',
  },
  Epic: {
    text: 'text-purple-400',
    solid: 'text-purple-900 bg-purple-400',
    glow: 'shadow-purple-500/50',
  },
  Rare: {
    text: 'text-blue-400',
    solid: 'text-blue-900 bg-blue-400',
    glow: 'shadow-blue-500/50',
  },
  Uncommon: {
    text: 'text-brand-300',
    solid: 'text-brand-800 bg-brand-300',
    glow: 'shadow-brand-500/50',
  },
  Common: {
    text: 'text-muted-foreground',
    solid: 'text-zinc-900 bg-zinc-400',
    glow: '',
  },
  Sealed: {
    text: 'text-cyan-400',
    solid: 'text-cyan-900 bg-cyan-400',
    glow: 'shadow-cyan-500/50',
  },
} as const

export interface RarityBadgeProps {
  /** The rarity name */
  rarity: string | null | undefined
  /** Display variant: 'text' (just colored text) or 'solid' (filled badge) */
  variant?: 'text' | 'solid'
  /** Size preset */
  size?: 'xs' | 'sm' | 'md'
  /** Show glow effect (for premium feel) */
  glow?: boolean
  /** Additional classes */
  className?: string
}

const sizeStyles = {
  xs: 'text-[8px] lg:text-[10px]',
  sm: 'text-[10px]',
  md: 'text-xs',
}

const solidSizeStyles = {
  xs: 'text-[8px] lg:text-[10px] px-1 py-0.5 rounded',
  sm: 'text-[10px] px-1.5 py-0.5 rounded',
  md: 'text-xs px-2 py-1 rounded-md',
}

export function RarityBadge({
  rarity,
  variant = 'text',
  size = 'sm',
  glow = false,
  className,
}: RarityBadgeProps) {
  if (!rarity) return null

  // Normalize rarity name (handle case variations)
  const normalizedRarity = normalizeRarity(rarity)
  const colors = RARITY_COLORS[normalizedRarity] || RARITY_COLORS.Common

  if (variant === 'solid') {
    return (
      <span
        className={cn(
          'inline-block font-bold uppercase',
          solidSizeStyles[size],
          colors.solid,
          glow && colors.glow && 'shadow-md',
          glow && colors.glow,
          className
        )}
      >
        {rarity}
      </span>
    )
  }

  return (
    <span
      className={cn(
        'inline-block font-bold uppercase',
        sizeStyles[size],
        colors.text,
        className
      )}
    >
      {rarity}
    </span>
  )
}

/**
 * Normalize rarity string to our standard format
 */
function normalizeRarity(rarity: string): Rarity {
  const normalized = rarity.charAt(0).toUpperCase() + rarity.slice(1).toLowerCase()
  if (normalized in RARITY_COLORS) {
    return normalized as Rarity
  }
  // Handle edge cases
  if (rarity.toUpperCase() === 'SEALED') return 'Sealed'
  return 'Common'
}

/**
 * Get rarity color classes directly (for custom usage)
 */
export function getRarityColors(rarity: string | null | undefined) {
  if (!rarity) return RARITY_COLORS.Common
  const normalized = normalizeRarity(rarity)
  return RARITY_COLORS[normalized] || RARITY_COLORS.Common
}

/**
 * Get just the text color class for a rarity
 */
export function getRarityTextColor(rarity: string | null | undefined): string {
  return getRarityColors(rarity).text
}

/**
 * Get the solid badge classes for a rarity
 */
export function getRaritySolidClasses(rarity: string | null | undefined): string {
  return getRarityColors(rarity).solid
}

export { RARITY_COLORS }
