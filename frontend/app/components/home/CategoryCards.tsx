/**
 * CategoryCards - Quick navigation carousel
 *
 * Mini image cards for quick access to filtered views, categories, or articles.
 * Similar to TCGPlayer's "Shop Single Cards", "Shop Booster Packs" section.
 */

import { Link } from '@tanstack/react-router'
import { cn } from '@/lib/utils'
import { Layers, Package, Archive, Gift, Gem, TrendingUp, Flame, DollarSign } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

type CategoryCard = {
  id: string
  title: string
  description?: string
  icon: LucideIcon
  href: string
  /** Search params to apply */
  searchParams?: Record<string, string>
  /** Background gradient or color */
  bgClass?: string
  /** Image URL (optional, falls back to icon) */
  imageUrl?: string
}

// Default categories for Wonders Tracker
const DEFAULT_CATEGORIES: CategoryCard[] = [
  {
    id: 'singles',
    title: 'Singles',
    description: 'Individual cards',
    icon: Layers,
    href: '/browse',
    searchParams: { productType: 'Single' },
    bgClass: 'from-blue-600/20 to-blue-900/40',
  },
  {
    id: 'boxes',
    title: 'Booster Boxes',
    description: 'Sealed product',
    icon: Package,
    href: '/browse',
    searchParams: { productType: 'Box' },
    bgClass: 'from-purple-600/20 to-purple-900/40',
  },
  {
    id: 'packs',
    title: 'Booster Packs',
    description: 'Single packs',
    icon: Archive,
    href: '/browse',
    searchParams: { productType: 'Pack' },
    bgClass: 'from-green-600/20 to-green-900/40',
  },
  {
    id: 'bundles',
    title: 'Bundles',
    description: 'Multi-item lots',
    icon: Gift,
    href: '/browse',
    searchParams: { productType: 'Bundle' },
    bgClass: 'from-orange-600/20 to-orange-900/40',
  },
  {
    id: 'mythics',
    title: 'Mythic Cards',
    description: 'Rarest pulls',
    icon: Gem,
    href: '/browse',
    searchParams: { rarity: 'Mythic' },
    bgClass: 'from-amber-500/20 to-amber-900/40',
  },
  {
    id: 'trending',
    title: 'Trending',
    description: 'Price movers',
    icon: TrendingUp,
    href: '/market',
    bgClass: 'from-cyan-600/20 to-cyan-900/40',
  },
  {
    id: 'hot-deals',
    title: 'Hot Deals',
    description: 'Below market',
    icon: Flame,
    href: '/market',
    searchParams: { tab: 'deals' },
    bgClass: 'from-red-600/20 to-red-900/40',
  },
  {
    id: 'floor-prices',
    title: 'Floor Prices',
    description: 'Lowest prices',
    icon: DollarSign,
    href: '/browse',
    searchParams: { sortBy: 'price', dir: 'asc' },
    bgClass: 'from-emerald-600/20 to-emerald-900/40',
  },
]

type CategoryCardsProps = {
  categories?: CategoryCard[]
  className?: string
}

export function CategoryCards({ categories = DEFAULT_CATEGORIES, className }: CategoryCardsProps) {
  return (
    <div className={cn('mb-8', className)}>
      {/* Scrollable row */}
      <div
        className={cn(
          'flex gap-3 overflow-x-auto',
          'scroll-smooth snap-x snap-mandatory',
          'pb-2',
          'scrollbar-none',
          '[&::-webkit-scrollbar]:hidden',
          '[-ms-overflow-style:none]',
          '[scrollbar-width:none]'
        )}
      >
        {categories.map((category) => (
          <CategoryCardItem key={category.id} category={category} />
        ))}
      </div>
    </div>
  )
}

function CategoryCardItem({ category }: { category: CategoryCard }) {
  const Icon = category.icon

  // Build the link with search params
  const searchString = category.searchParams
    ? '?' + new URLSearchParams(category.searchParams).toString()
    : ''

  return (
    <Link
      to={category.href}
      search={category.searchParams}
      className={cn(
        'snap-start flex-shrink-0',
        'w-[120px] sm:w-[140px]',
        'rounded-lg overflow-hidden',
        'border border-border bg-card',
        'hover:border-brand-500/50 hover:shadow-lg hover:shadow-brand-500/10',
        'transition-all duration-200',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500',
        'group'
      )}
    >
      {/* Image/Icon area */}
      <div
        className={cn(
          'aspect-[4/3] relative overflow-hidden',
          'bg-gradient-to-br',
          category.bgClass || 'from-muted to-muted/50',
          'flex items-center justify-center'
        )}
      >
        {category.imageUrl ? (
          <img
            src={category.imageUrl}
            alt={category.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          />
        ) : (
          <Icon className="w-10 h-10 text-foreground/60 group-hover:scale-110 transition-transform duration-300" />
        )}
      </div>

      {/* Text */}
      <div className="p-2">
        <h3 className="text-xs font-medium text-foreground truncate">{category.title}</h3>
        {category.description && (
          <p className="text-xs text-muted-foreground truncate">{category.description}</p>
        )}
      </div>
    </Link>
  )
}

/**
 * Loading skeleton for CategoryCards
 */
export function CategoryCardsSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('mb-6 animate-pulse', className)}>
      <div className="flex gap-3 overflow-hidden">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="w-[120px] sm:w-[140px] flex-shrink-0 rounded-lg border border-border bg-card overflow-hidden"
          >
            <div className="aspect-[4/3] bg-muted" />
            <div className="p-2 space-y-1">
              <div className="h-3 bg-muted rounded w-3/4" />
              <div className="h-3 bg-muted rounded w-1/2" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
