/**
 * CardHero - Left column card display for detail page
 *
 * Enhanced with WebGL shader effects for different card treatments.
 * Uses @paper-design/shaders-react for real-time GPU effects.
 * Features: zoom on hover, fallback image, treatment-based shader effects.
 *
 * @see tasks.json E1-U2
 */

import { useState, useRef, useCallback, Suspense, lazy } from 'react'
import { cn } from '@/lib/utils'
import { Tooltip } from '../ui/tooltip'
import { ImageOff, User as ArtistIcon } from 'lucide-react'

// Lazy load shader components for code splitting
const MeshGradient = lazy(() =>
  import('@paper-design/shaders-react').then(m => ({ default: m.MeshGradient }))
)
const NeuroNoise = lazy(() =>
  import('@paper-design/shaders-react').then(m => ({ default: m.NeuroNoise }))
)
const GrainGradient = lazy(() =>
  import('@paper-design/shaders-react').then(m => ({ default: m.GrainGradient }))
)

// Treatment tiers for shader effects
const ULTRA_RARE_TREATMENTS = ['Formless Foil', 'OCM Serialized', 'Serialized', '1/1', 'Legendary']
const RARE_TREATMENTS = ['Stonefoil', 'Starfoil', 'Full Art Foil', 'Animated', 'Preslab TAG 10']
const UNCOMMON_TREATMENTS = ['Classic Foil', 'Full Art', 'Prerelease', 'Promo', 'Proof/Sample']

type TreatmentTier = 'ultra-rare' | 'rare' | 'uncommon' | 'common'

function getTreatmentTier(treatment?: string): TreatmentTier {
  if (!treatment) return 'common'
  if (ULTRA_RARE_TREATMENTS.includes(treatment)) return 'ultra-rare'
  if (RARE_TREATMENTS.includes(treatment)) return 'rare'
  if (UNCOMMON_TREATMENTS.includes(treatment)) return 'uncommon'
  return 'common'
}

// =============================================
// RARITY-BASED VISUAL EFFECTS (BASE LAYER)
// =============================================

type Rarity = 'Mythic' | 'Legendary' | 'Epic' | 'Rare' | 'Uncommon' | 'Common'

type RarityEffectConfig = {
  glowColor: string       // CSS color for glow
  glowIntensity: 'none' | 'subtle' | 'medium' | 'strong'
  shimmer: boolean
  shimmerSpeed: 'normal' | 'slow'
  holo: boolean           // Rainbow holo effect (Mythic/Legendary only)
  cornerAccents: boolean
  accentColor: string     // CSS color for corner accents
}

const RARITY_EFFECTS: Record<Rarity, RarityEffectConfig> = {
  Mythic: {
    glowColor: 'rgba(251, 191, 36, 0.35)',  // amber-400
    glowIntensity: 'strong',
    shimmer: true,
    shimmerSpeed: 'normal',
    holo: true,
    cornerAccents: true,
    accentColor: '#fbbf24',  // amber-400
  },
  Legendary: {
    glowColor: 'rgba(251, 146, 60, 0.3)',   // orange-400
    glowIntensity: 'strong',
    shimmer: true,
    shimmerSpeed: 'normal',
    holo: true,
    cornerAccents: true,
    accentColor: '#fb923c',  // orange-400
  },
  Epic: {
    glowColor: 'rgba(192, 132, 252, 0.25)', // purple-400
    glowIntensity: 'medium',
    shimmer: true,
    shimmerSpeed: 'slow',
    holo: false,
    cornerAccents: true,
    accentColor: '#c084fc',  // purple-400
  },
  Rare: {
    glowColor: 'rgba(96, 165, 250, 0.2)',   // blue-400
    glowIntensity: 'medium',
    shimmer: true,
    shimmerSpeed: 'slow',
    holo: false,
    cornerAccents: false,
    accentColor: '',
  },
  Uncommon: {
    glowColor: 'rgba(125, 211, 168, 0.15)', // brand-300
    glowIntensity: 'subtle',
    shimmer: false,
    shimmerSpeed: 'slow',
    holo: false,
    cornerAccents: false,
    accentColor: '',
  },
  Common: {
    glowColor: '',
    glowIntensity: 'none',
    shimmer: false,
    shimmerSpeed: 'slow',
    holo: false,
    cornerAccents: false,
    accentColor: '',
  },
}

// Special effects for NFT/Proof items (cyan theme to match OpenSea/blockchain aesthetic)
const NFT_EFFECTS: RarityEffectConfig = {
  glowColor: 'rgba(34, 211, 238, 0.3)',    // cyan-400
  glowIntensity: 'strong',
  shimmer: true,
  shimmerSpeed: 'normal',
  holo: true,
  cornerAccents: true,
  accentColor: '#22d3ee',  // cyan-400
}

function getRarityEffects(rarityName?: string, isNFT?: boolean): RarityEffectConfig {
  // NFTs always get special effects
  if (isNFT) return NFT_EFFECTS

  const rarity = (rarityName as Rarity) || 'Common'
  return RARITY_EFFECTS[rarity] || RARITY_EFFECTS.Common
}

export type CardHeroProps = {
  card: {
    id: number
    name: string
    set_name: string
    rarity_id: number
    rarity_name?: string
    product_type?: string
    card_type?: string
    orbital?: string
    orbital_color?: string
    card_number?: string
    cardeio_image_url?: string
    /** Card text/description (flavor text or rules text) */
    card_text?: string
    /** Artist credit */
    artist?: string
  }
  /** Currently selected treatment for shader effect */
  selectedTreatment?: string
  /** Enable WebGL-style shader effects (CSS-based for performance) */
  enableShaderEffects?: boolean
  /** Additional className for the container */
  className?: string
}

export function CardHero({
  card,
  selectedTreatment,
  enableShaderEffects = true,
  className
}: CardHeroProps) {
  const [imageLoaded, setImageLoaded] = useState(false)
  const [imageError, setImageError] = useState(false)
  const [isZoomed, setIsZoomed] = useState(false)
  const [mousePosition, setMousePosition] = useState({ x: 0.5, y: 0.5 })
  const imageContainerRef = useRef<HTMLDivElement>(null)

  const isNFT = card.product_type === 'Proof' ||
    card.name?.toLowerCase().includes('proof') ||
    card.name?.toLowerCase().includes('sample')

  const treatmentTier = getTreatmentTier(selectedTreatment)
  const rarityEffects = getRarityEffects(card.rarity_name, isNFT)

  // Render rarity-based overlay effects (base layer - always visible)
  const renderRarityOverlay = () => {
    if (rarityEffects.glowIntensity === 'none') return null

    return (
      <>
        {/* Rarity shimmer overlay - z-10 to appear above image */}
        {rarityEffects.shimmer && (
          <div
            className={cn(
              "absolute inset-0 pointer-events-none z-10 rarity-shimmer-overlay",
              rarityEffects.shimmerSpeed === 'normal' ? 'shimmer-normal' : 'shimmer-slow'
            )}
          />
        )}

        {/* Holographic rainbow for Mythic/Legendary - z-10 to appear above image */}
        {rarityEffects.holo && (
          <div className="absolute inset-0 pointer-events-none z-10 rarity-holo-overlay opacity-70" />
        )}
      </>
    )
  }

  // Handle mouse move for parallax/3D effect
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!imageContainerRef.current || !enableShaderEffects) return

    const rect = imageContainerRef.current.getBoundingClientRect()
    const x = (e.clientX - rect.left) / rect.width
    const y = (e.clientY - rect.top) / rect.height
    setMousePosition({ x, y })
  }, [enableShaderEffects])

  const handleMouseEnter = useCallback(() => {
    setIsZoomed(true)
  }, [])

  const handleMouseLeave = useCallback(() => {
    setIsZoomed(false)
    setMousePosition({ x: 0.5, y: 0.5 })
  }, [])

  // Calculate 3D transform based on mouse position
  const get3DTransform = () => {
    if (!enableShaderEffects || !isZoomed) return {}

    const rotateX = (mousePosition.y - 0.5) * -10 // -5 to 5 degrees
    const rotateY = (mousePosition.x - 0.5) * 10 // -5 to 5 degrees

    return {
      transform: `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(1.05)`,
      transition: 'transform 0.1s ease-out',
    }
  }

  // Render shader overlay based on treatment tier
  // Uses CSS-based foil effects inspired by pokemon-cards-css with WebGL fallback
  const renderShaderOverlay = () => {
    if (!enableShaderEffects || treatmentTier === 'common') return null

    // CSS-based foil gradient that follows mouse position
    const foilGradient = `
      linear-gradient(
        ${115 + mousePosition.x * 20}deg,
        transparent 0%,
        rgba(255,255,255,0.1) 25%,
        rgba(255,255,255,0.3) 50%,
        rgba(255,255,255,0.1) 75%,
        transparent 100%
      )
    `

    // Holographic rainbow gradient for ultra-rare
    const holoGradient = `
      linear-gradient(
        ${125 + mousePosition.x * 40}deg,
        hsl(${mousePosition.x * 360}, 80%, 60%) 0%,
        hsl(${mousePosition.x * 360 + 60}, 80%, 60%) 25%,
        hsl(${mousePosition.x * 360 + 120}, 80%, 60%) 50%,
        hsl(${mousePosition.x * 360 + 180}, 80%, 60%) 75%,
        hsl(${mousePosition.x * 360 + 240}, 80%, 60%) 100%
      )
    `

    // Try WebGL shader, with CSS fallback
    const renderWebGLShader = () => (
      <Suspense fallback={null}>
        {treatmentTier === 'ultra-rare' && (
          <MeshGradient
            style={{ width: '100%', height: '100%' }}
            colors={['#ec4899', '#a855f7', '#3b82f6', '#06b6d4']}
            speed={0.3}
            distortion={0.6}
          />
        )}
        {treatmentTier === 'rare' && (
          <NeuroNoise
            style={{ width: '100%', height: '100%' }}
            colorFront="#a8a29e"
            colorMid="#d6d3d1"
            colorBack="#1c1917"
            scale={1.5}
            speed={0.2}
          />
        )}
        {treatmentTier === 'uncommon' && (
          <GrainGradient
            style={{ width: '100%', height: '100%' }}
            colors={['#38bdf8', '#0ea5e9']}
            colorBack="#0c4a6e"
            noise={0.5}
            speed={0.1}
          />
        )}
      </Suspense>
    )

    return (
      <>
        {/* CSS Foil Shine Layer - z-20 to appear above rarity effects */}
        <div
          className={cn(
            "absolute inset-0 pointer-events-none z-20 transition-opacity duration-300",
            isZoomed ? "opacity-100" : "opacity-0"
          )}
          style={{
            background: treatmentTier === 'ultra-rare' ? holoGradient : foilGradient,
            mixBlendMode: 'overlay',
          }}
        />
        {/* WebGL Shader Layer - z-20 to appear above rarity effects */}
        <div
          className={cn(
            "absolute inset-0 pointer-events-none z-20 transition-opacity duration-500 mix-blend-soft-light",
            isZoomed ? "opacity-50" : "opacity-30"
          )}
        >
          {renderWebGLShader()}
        </div>
      </>
    )
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Card Name Header (h1) */}
      <div className="space-y-1">
        <h1 className="text-2xl md:text-3xl font-black uppercase tracking-tight text-foreground">
          {card.name}
        </h1>
        <p className="text-sm text-muted-foreground">
          {card.set_name}
        </p>
      </div>

      {/* Card Image with Rarity + Treatment Effects */}
      {/* Outer wrapper for corner accents (can't use overflow-hidden) */}
      <div
        className={cn(
          "relative",
          rarityEffects.cornerAccents && "rarity-corner-accent",
        )}
        style={{
          '--accent-color': rarityEffects.accentColor,
        } as React.CSSProperties}
      >
        {/* Inner container for image + effects */}
        <div
          ref={imageContainerRef}
          className={cn(
            "relative aspect-[3/4] rounded-lg overflow-hidden border bg-muted/20 cursor-zoom-in",
            // RARITY-BASED GLOW (base layer - always visible based on card rarity)
            rarityEffects.glowIntensity === 'subtle' && "rarity-glow-subtle",
            rarityEffects.glowIntensity === 'medium' && "rarity-glow-medium",
            rarityEffects.glowIntensity === 'strong' && "rarity-glow-strong",
            // Default border for common (no glow)
            rarityEffects.glowIntensity === 'none' && "border-border",
            // TREATMENT-BASED EFFECTS (override layer - when treatment is selected)
            treatmentTier === 'ultra-rare' && "border-fuchsia-500/40 shadow-lg shadow-fuchsia-500/10",
            treatmentTier === 'rare' && "border-stone-400/40 shadow-lg shadow-stone-400/10",
            treatmentTier === 'uncommon' && "border-sky-500/40",
          )}
          style={{
            '--glow-color': rarityEffects.glowColor,
          } as React.CSSProperties}
          onMouseMove={handleMouseMove}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          role="img"
          aria-label={`Card image for ${card.name}`}
        >
        {/* Loading skeleton */}
        {!imageLoaded && !imageError && card.cardeio_image_url && (
          <div className="absolute inset-0 bg-muted animate-pulse" />
        )}

        {/* Main image */}
        {card.cardeio_image_url && !imageError ? (
          <img
            src={card.cardeio_image_url}
            alt={card.name}
            className={cn(
              "w-full h-full object-contain transition-all duration-300",
              imageLoaded ? "opacity-100" : "opacity-0"
            )}
            style={get3DTransform()}
            loading="eager"
            onLoad={() => setImageLoaded(true)}
            onError={() => setImageError(true)}
          />
        ) : (
          // Fallback for missing images
          <div className="w-full h-full flex flex-col items-center justify-center text-muted-foreground gap-2">
            <ImageOff className="w-12 h-12 opacity-50" aria-hidden="true" />
            <span className="text-xs uppercase tracking-wider">No Image Available</span>
          </div>
        )}

        {/* LAYER 1: Rarity effects (base layer - always visible based on card rarity) */}
        {renderRarityOverlay()}

        {/* LAYER 2: Treatment effects (override layer - on hover when treatment selected) */}
        {renderShaderOverlay()}

        {/* Zoom indicator */}
        {isZoomed && card.cardeio_image_url && !imageError && (
          <div className="absolute bottom-2 right-2 px-2 py-1 bg-black/60 rounded text-[10px] text-white/80 uppercase tracking-wider z-30">
            Zoomed
          </div>
        )}
        </div>
      </div>

      {/* Card Text/Description */}
      {card.card_text && (
        <div className="p-4 border border-border rounded-lg bg-card">
          <h3 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground border-b border-border pb-2 mb-3">
            Card Text
          </h3>
          <p className="text-sm text-foreground/90 leading-relaxed italic">
            "{card.card_text}"
          </p>
        </div>
      )}

      {/* Artist Credit */}
      {card.artist && (
        <div className="flex items-center gap-2 px-4 py-3 border border-border rounded-lg bg-card">
          <ArtistIcon className="w-4 h-4 text-muted-foreground" aria-hidden="true" />
          <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Artist:</span>
          <span className="text-sm font-medium">{card.artist}</span>
        </div>
      )}
    </div>
  )
}

/**
 * Loading skeleton for CardHero
 */
export function CardHeroSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      {/* Title skeleton */}
      <div className="space-y-2">
        <div className="h-8 bg-muted rounded w-3/4" />
        <div className="h-4 bg-muted rounded w-1/2" />
      </div>

      {/* Image skeleton */}
      <div className="aspect-[3/4] bg-muted rounded-lg" />

      {/* Details skeleton */}
      <div className="p-4 border border-border rounded-lg bg-card space-y-3">
        <div className="h-3 bg-muted rounded w-1/3" />
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <div className="h-2 bg-muted rounded w-1/2" />
            <div className="h-4 bg-muted rounded w-3/4" />
          </div>
          <div className="space-y-1">
            <div className="h-2 bg-muted rounded w-1/2" />
            <div className="h-4 bg-muted rounded w-3/4" />
          </div>
          <div className="space-y-1">
            <div className="h-2 bg-muted rounded w-1/2" />
            <div className="h-4 bg-muted rounded w-3/4" />
          </div>
          <div className="space-y-1">
            <div className="h-2 bg-muted rounded w-1/2" />
            <div className="h-4 bg-muted rounded w-3/4" />
          </div>
        </div>
      </div>
    </div>
  )
}
