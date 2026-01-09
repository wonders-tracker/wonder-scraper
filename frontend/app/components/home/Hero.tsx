/**
 * Hero - Welcome section for the home page
 *
 * Features an animated grid of card images as background
 * with a dark scrim overlay for text readability.
 */

import { cn } from '@/lib/utils'
import { TrendingUp, BarChart3, Bell } from 'lucide-react'
import { HeroGrid } from './HeroGrid'

type HeroProps = {
  /** Card image URLs for the animated background */
  cardImages?: string[]
  className?: string
}

export function Hero({ cardImages = [], className }: HeroProps) {
  return (
    <div className={cn('relative mb-8 -mx-4 sm:-mx-6 lg:-mx-8 overflow-hidden', className)}>
      {/* Animated card grid background */}
      {cardImages.length > 0 && (
        <HeroGrid images={cardImages} />
      )}

      {/* Content */}
      <div className="relative z-10 px-4 sm:px-6 lg:px-8 py-12 sm:py-16">
        {/* Main headline */}
        <div className="mb-6">
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-foreground mb-4 tracking-tight">
            Wonders Tracker
          </h1>
          <p className="text-base sm:text-lg text-muted-foreground max-w-2xl leading-relaxed">
            Track prices, monitor sales, and discover deals for Wonders of the First trading cards.
            Real-time data from eBay, Blokpax, and OpenSea.
          </p>
        </div>

        {/* Value props */}
        <div className="flex flex-wrap gap-4 sm:gap-6">
          <div className="flex items-center gap-3 bg-background/50 backdrop-blur-sm rounded-full px-4 py-2 border border-border/50">
            <div className="p-1.5 rounded-full bg-brand-500/20 text-brand-400">
              <TrendingUp className="w-4 h-4" />
            </div>
            <span className="text-sm font-medium text-foreground">Live Price Tracking</span>
          </div>
          <div className="flex items-center gap-3 bg-background/50 backdrop-blur-sm rounded-full px-4 py-2 border border-border/50">
            <div className="p-1.5 rounded-full bg-brand-500/20 text-brand-400">
              <BarChart3 className="w-4 h-4" />
            </div>
            <span className="text-sm font-medium text-foreground">Market Analytics</span>
          </div>
          <div className="flex items-center gap-3 bg-background/50 backdrop-blur-sm rounded-full px-4 py-2 border border-border/50">
            <div className="p-1.5 rounded-full bg-brand-500/20 text-brand-400">
              <Bell className="w-4 h-4" />
            </div>
            <span className="text-sm font-medium text-foreground">Price Alerts</span>
          </div>
        </div>
      </div>
    </div>
  )
}
