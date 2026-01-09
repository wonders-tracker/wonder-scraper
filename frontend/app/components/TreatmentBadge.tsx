import { clsx } from 'clsx'
import { Link } from '@tanstack/react-router'

export type Treatment =
  // Single card treatments
  | 'Classic Paper'
  | 'Classic Foil'
  | 'Stonefoil'
  | 'Formless Foil'
  | 'OCM Serialized'
  | 'Prerelease'
  | 'Promo'
  | 'Proof/Sample'
  | 'Error/Errata'
  // Legacy/alternate names
  | 'Starfoil'
  | 'Full Art'
  | 'Full Art Foil'
  | 'Serialized'
  // Graded/Preslab treatments (Blokpax TAG graded)
  | 'Preslab TAG'
  | 'Preslab TAG 8'
  | 'Preslab TAG 9'
  | 'Preslab TAG 10'
  // Sealed product treatments
  | 'Factory Sealed'
  | 'Sealed'
  | 'New'
  | 'Unopened'
  | 'Open Box'
  | 'Used'
  | 'Mixed'
  | 'All Sealed'
  | 'All Raw'
  // NFT treatments
  | 'Standard'
  | 'Animated'
  | 'Legendary'
  | '1/1'
  | 'Character Proof'
  | 'Set Proof'
  | 'Other'

interface TreatmentBadgeProps {
  treatment: string
  size?: 'xs' | 'sm' | 'md'
  className?: string
  /** If true, badge links to /browse?treatment=X */
  linkToBrowse?: boolean
}

// Treatment tiers for rarity (affects animation)
const ULTRA_RARE_TREATMENTS = ['Formless Foil', 'OCM Serialized', 'Serialized', '1/1', 'Legendary']
const RARE_TREATMENTS = ['Stonefoil', 'Starfoil', 'Full Art Foil', 'Animated', 'Preslab TAG 10']
const UNCOMMON_TREATMENTS = ['Classic Foil', 'Full Art', 'Prerelease', 'Promo', 'Proof/Sample', 'Error/Errata']

// Color schemes for each treatment
const TREATMENT_STYLES: Record<string, { bg: string; border: string; text: string; gradient?: string }> = {
  // === ULTRA RARE (shimmer animation) ===
  'Formless Foil': {
    bg: 'bg-gradient-to-r from-fuchsia-950 via-purple-900 to-fuchsia-950',
    border: 'border-fuchsia-500/40',
    text: 'text-fuchsia-300',
    gradient: 'linear-gradient(90deg, rgba(192,38,211,0.15) 0%, rgba(168,85,247,0.3) 25%, rgba(236,72,153,0.35) 50%, rgba(168,85,247,0.3) 75%, rgba(192,38,211,0.15) 100%)',
  },
  'OCM Serialized': {
    bg: 'bg-gradient-to-r from-amber-950 via-yellow-900 to-amber-950',
    border: 'border-yellow-500/40',
    text: 'text-yellow-300',
    gradient: 'linear-gradient(90deg, rgba(180,83,9,0.15) 0%, rgba(234,179,8,0.3) 25%, rgba(253,224,71,0.35) 50%, rgba(234,179,8,0.3) 75%, rgba(180,83,9,0.15) 100%)',
  },
  'Serialized': {
    bg: 'bg-gradient-to-r from-amber-950 via-yellow-900 to-amber-950',
    border: 'border-yellow-500/40',
    text: 'text-yellow-300',
    gradient: 'linear-gradient(90deg, rgba(180,83,9,0.15) 0%, rgba(234,179,8,0.3) 25%, rgba(253,224,71,0.35) 50%, rgba(234,179,8,0.3) 75%, rgba(180,83,9,0.15) 100%)',
  },
  '1/1': {
    bg: 'bg-gradient-to-r from-rose-950 via-red-900 to-rose-950',
    border: 'border-rose-400/40',
    text: 'text-rose-300',
    gradient: 'linear-gradient(90deg, rgba(159,18,57,0.15) 0%, rgba(225,29,72,0.3) 25%, rgba(251,113,133,0.35) 50%, rgba(225,29,72,0.3) 75%, rgba(159,18,57,0.15) 100%)',
  },
  'Legendary': {
    bg: 'bg-gradient-to-r from-orange-950 via-orange-800 to-orange-950',
    border: 'border-orange-400/40',
    text: 'text-orange-300',
    gradient: 'linear-gradient(90deg, rgba(124,45,18,0.15) 0%, rgba(234,88,12,0.3) 25%, rgba(251,146,60,0.35) 50%, rgba(234,88,12,0.3) 75%, rgba(124,45,18,0.15) 100%)',
  },

  // === RARE (subtle shimmer) ===
  'Stonefoil': {
    bg: 'bg-gradient-to-r from-slate-800 via-stone-700 to-slate-800',
    border: 'border-stone-400/40',
    text: 'text-stone-200',
    gradient: 'linear-gradient(90deg, rgba(68,64,60,0.15) 0%, rgba(168,162,158,0.25) 25%, rgba(214,211,209,0.3) 50%, rgba(168,162,158,0.25) 75%, rgba(68,64,60,0.15) 100%)',
  },
  'Starfoil': {
    bg: 'bg-gradient-to-r from-violet-950 via-purple-800 to-violet-950',
    border: 'border-violet-400/40',
    text: 'text-violet-300',
    gradient: 'linear-gradient(90deg, rgba(76,29,149,0.15) 0%, rgba(139,92,246,0.25) 25%, rgba(196,181,253,0.3) 50%, rgba(139,92,246,0.25) 75%, rgba(76,29,149,0.15) 100%)',
  },
  'Full Art Foil': {
    bg: 'bg-gradient-to-r from-brand-900 via-teal-800 to-brand-900',
    border: 'border-brand-300/40',
    text: 'text-brand-200',
    gradient: 'linear-gradient(90deg, rgba(6,78,59,0.15) 0%, rgba(20,184,166,0.25) 25%, rgba(94,234,212,0.3) 50%, rgba(20,184,166,0.25) 75%, rgba(6,78,59,0.15) 100%)',
  },
  'Animated': {
    bg: 'bg-gradient-to-r from-cyan-950 via-sky-800 to-cyan-950',
    border: 'border-cyan-400/40',
    text: 'text-cyan-300',
    gradient: 'linear-gradient(90deg, rgba(8,51,68,0.15) 0%, rgba(6,182,212,0.25) 25%, rgba(103,232,249,0.3) 50%, rgba(6,182,212,0.25) 75%, rgba(8,51,68,0.15) 100%)',
  },

  // === GRADED / PRESLAB (TAG graded singles from Blokpax) ===
  'Preslab TAG 10': {
    bg: 'bg-gradient-to-r from-amber-900 via-yellow-700 to-amber-900',
    border: 'border-amber-400/50',
    text: 'text-amber-200',
    gradient: 'linear-gradient(90deg, rgba(180,83,9,0.15) 0%, rgba(253,224,71,0.3) 25%, rgba(254,240,138,0.35) 50%, rgba(253,224,71,0.3) 75%, rgba(180,83,9,0.15) 100%)',
  },
  'Preslab TAG 9': {
    bg: 'bg-brand-900/80',
    border: 'border-brand-400/50',
    text: 'text-brand-200',
  },
  'Preslab TAG 8': {
    bg: 'bg-sky-950/80',
    border: 'border-sky-500/50',
    text: 'text-sky-300',
  },
  'Preslab TAG': {
    bg: 'bg-teal-950/80',
    border: 'border-teal-500/50',
    text: 'text-teal-300',
  },

  // === UNCOMMON (no animation) ===
  'Classic Foil': {
    bg: 'bg-sky-950/80',
    border: 'border-sky-600/50',
    text: 'text-sky-300',
  },
  'Full Art': {
    bg: 'bg-indigo-950/80',
    border: 'border-indigo-600/50',
    text: 'text-indigo-300',
  },
  'Prerelease': {
    bg: 'bg-pink-950/80',
    border: 'border-pink-600/50',
    text: 'text-pink-300',
  },
  'Promo': {
    bg: 'bg-rose-950/80',
    border: 'border-rose-600/50',
    text: 'text-rose-300',
  },
  'Proof/Sample': {
    bg: 'bg-amber-950/80',
    border: 'border-amber-600/50',
    text: 'text-amber-300',
  },
  'Error/Errata': {
    bg: 'bg-red-950/80',
    border: 'border-red-600/50',
    text: 'text-red-300',
  },

  // === COMMON (no animation) ===
  'Classic Paper': {
    bg: 'bg-zinc-800/60',
    border: 'border-zinc-600/40',
    text: 'text-zinc-400',
  },

  // === SEALED PRODUCTS ===
  'Factory Sealed': {
    bg: 'bg-brand-900/80',
    border: 'border-brand-400/50',
    text: 'text-brand-200',
  },
  'Sealed': {
    bg: 'bg-brand-900/70',
    border: 'border-brand-400/50',
    text: 'text-brand-300',
  },
  'New': {
    bg: 'bg-teal-950/70',
    border: 'border-teal-600/50',
    text: 'text-teal-400',
  },
  'Unopened': {
    bg: 'bg-cyan-950/70',
    border: 'border-cyan-600/50',
    text: 'text-cyan-400',
  },
  'Open Box': {
    bg: 'bg-orange-950/70',
    border: 'border-orange-600/50',
    text: 'text-orange-400',
  },
  'Used': {
    bg: 'bg-neutral-800/70',
    border: 'border-neutral-600/50',
    text: 'text-neutral-400',
  },

  // === NFT ===
  'Standard': {
    bg: 'bg-blue-950/70',
    border: 'border-blue-600/50',
    text: 'text-blue-400',
  },
  'Character Proof': {
    bg: 'bg-purple-950/70',
    border: 'border-purple-600/50',
    text: 'text-purple-400',
  },
  'Set Proof': {
    bg: 'bg-violet-950/70',
    border: 'border-violet-600/50',
    text: 'text-violet-400',
  },

  // === FALLBACK ===
  'Other': {
    bg: 'bg-gray-800/60',
    border: 'border-gray-600/40',
    text: 'text-gray-400',
  },
  'Mixed': {
    bg: 'bg-gray-800/60',
    border: 'border-gray-600/40',
    text: 'text-gray-400',
  },
  'All Sealed': {
    bg: 'bg-brand-900/60',
    border: 'border-brand-400/40',
    text: 'text-brand-300',
  },
  'All Raw': {
    bg: 'bg-zinc-800/60',
    border: 'border-zinc-600/40',
    text: 'text-zinc-400',
  },
}

// Size variants
const SIZE_CLASSES = {
  xs: 'text-[10px] px-1.5 py-0.5',
  sm: 'text-xs px-2 py-0.5',
  md: 'text-sm px-2.5 py-1',
}

export function TreatmentBadge({ treatment, size = 'sm', className, linkToBrowse = false }: TreatmentBadgeProps) {
  const style = TREATMENT_STYLES[treatment] || TREATMENT_STYLES['Other']
  const isUltraRare = ULTRA_RARE_TREATMENTS.includes(treatment)
  const isRare = RARE_TREATMENTS.includes(treatment)

  const badgeClasses = clsx(
    'inline-block rounded font-semibold uppercase tracking-wide border',
    SIZE_CLASSES[size],
    style.bg,
    style.border,
    style.text,
    // Apply shimmer animation for rare treatments
    (isUltraRare || isRare) && style.gradient && 'animate-shimmer',
    isRare && !isUltraRare && 'animate-shimmer-slow',
    linkToBrowse && 'hover:opacity-80 transition-opacity cursor-pointer',
    className
  )

  const badgeStyle = (isUltraRare || isRare) && style.gradient
    ? { backgroundImage: style.gradient }
    : undefined

  if (linkToBrowse) {
    return (
      <Link
        to="/browse"
        search={{ treatment }}
        className={badgeClasses}
        style={badgeStyle}
        title={`Browse all ${treatment} cards`}
      >
        {treatment}
      </Link>
    )
  }

  return (
    <span className={badgeClasses} style={badgeStyle}>
      {treatment}
    </span>
  )
}

// Helper to get just the classes (for use in tables where we can't use the component)
export function getTreatmentClasses(treatment: string, size: 'xs' | 'sm' | 'md' = 'sm'): string {
  const style = TREATMENT_STYLES[treatment] || TREATMENT_STYLES['Other']
  const isUltraRare = ULTRA_RARE_TREATMENTS.includes(treatment)
  const isRare = RARE_TREATMENTS.includes(treatment)

  return clsx(
    'inline-block rounded font-semibold uppercase tracking-wide border',
    SIZE_CLASSES[size],
    style.bg,
    style.border,
    style.text,
    (isUltraRare || isRare) && style.gradient && 'animate-shimmer',
    isRare && !isUltraRare && 'animate-shimmer-slow'
  )
}

// Export style info for inline styles
export function getTreatmentStyle(treatment: string): { gradient?: string } | undefined {
  const style = TREATMENT_STYLES[treatment]
  const isUltraRare = ULTRA_RARE_TREATMENTS.includes(treatment)
  const isRare = RARE_TREATMENTS.includes(treatment)

  if ((isUltraRare || isRare) && style?.gradient) {
    return { gradient: style.gradient }
  }
  return undefined
}

// Get just the text color class for a treatment
export function getTreatmentTextColor(treatment: string): string {
  const style = TREATMENT_STYLES[treatment] || TREATMENT_STYLES['Other']
  return style.text
}

export default TreatmentBadge
