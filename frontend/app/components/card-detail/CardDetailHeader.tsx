/**
 * CardDetailHeader - Top navigation bar for card detail page
 *
 * Layout:
 * - Left: Back button
 * - Center: Breadcrumbs (Home > Browse > Set > Card)
 * - Right: Watchlist and Price Alert buttons with text
 *
 * @see tasks.json E7-U5
 */

import { Link } from '@tanstack/react-router'
import { cn } from '@/lib/utils'
import { ArrowLeft, Heart, Bell, ChevronRight, Home } from 'lucide-react'
import { Button } from '../ui/button'
import { Tooltip } from '../ui/tooltip'

export type CardDetailHeaderProps = {
  /** Card name for breadcrumb */
  cardName: string
  /** Set name for breadcrumb */
  setName?: string
  /** Product type for browse filter */
  productType?: string
  /** Rarity name for browse filter */
  rarityName?: string
  /** Whether user is logged in */
  isLoggedIn: boolean
  /** Whether card is in user's watchlist */
  isInWatchlist?: boolean
  /** Callback for toggling watchlist */
  onToggleWatchlist?: () => void
  /** Whether watchlist action is in progress */
  watchlistLoading?: boolean
  /** Callback for opening price alert modal */
  onSetPriceAlert?: () => void
  /** Additional className */
  className?: string
}

export function CardDetailHeader({
  cardName,
  setName,
  productType,
  rarityName,
  isLoggedIn,
  isInWatchlist = false,
  onToggleWatchlist,
  watchlistLoading = false,
  onSetPriceAlert,
  className
}: CardDetailHeaderProps) {
  return (
    <header className={cn(
      "flex items-center justify-between gap-2 py-3 overflow-hidden",
      className
    )}>
      {/* Left: Back to Browse */}
      <Link
        to="/browse"
        className={cn(
          "flex items-center gap-1.5 px-2 py-1.5",
          "text-xs font-semibold uppercase tracking-wider",
          "text-muted-foreground hover:text-foreground",
          "border border-border rounded-lg",
          "hover:bg-muted/50 transition-colors",
          "shrink-0"
        )}
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span className="hidden md:inline">Browse</span>
      </Link>

      {/* Center: Breadcrumbs - hidden on small screens */}
      <nav
        className="hidden md:flex items-center gap-1 text-xs overflow-hidden min-w-0 flex-1 justify-center"
        aria-label="Breadcrumb"
      >
        {/* Home */}
        <Link
          to="/"
          className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
        >
          <Home className="w-3.5 h-3.5" />
        </Link>
        <ChevronRight className="w-3 h-3 text-muted-foreground shrink-0" />

        {/* Browse */}
        <Link
          to="/browse"
          className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
        >
          Browse
        </Link>

        {/* Set Name (links to browse with set filter) */}
        {setName && (
          <>
            <ChevronRight className="w-3 h-3 text-muted-foreground shrink-0" />
            <Link
              to="/browse"
              search={{ set: setName }}
              className="text-muted-foreground hover:text-foreground transition-colors truncate max-w-[100px] lg:max-w-[150px]"
            >
              {setName}
            </Link>
          </>
        )}

        {/* Card Name (current page - not a link) */}
        <ChevronRight className="w-3 h-3 text-muted-foreground shrink-0" />
        <span className="font-semibold text-foreground truncate max-w-[120px] lg:max-w-[200px]">
          {cardName}
        </span>
      </nav>

      {/* Right: Action buttons */}
      <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
        {/* Watchlist Button */}
        <Tooltip content={!isLoggedIn ? 'Log in to use watchlist' : isInWatchlist ? 'Remove from watchlist' : 'Add to watchlist'}>
          <Button
            variant={isInWatchlist ? 'secondary' : 'outline'}
            size="sm"
            className={cn(
              "gap-1.5 sm:gap-2 px-2 sm:px-3",
              isInWatchlist && "bg-pink-500/10 border-pink-500/30 text-pink-400 hover:bg-pink-500/20"
            )}
            onClick={onToggleWatchlist}
            disabled={watchlistLoading || !isLoggedIn}
            aria-label={isInWatchlist ? 'Remove from watchlist' : 'Add to watchlist'}
            aria-pressed={isInWatchlist}
          >
            <Heart
              className={cn(
                "w-4 h-4 transition-all",
                isInWatchlist && "fill-pink-400",
                watchlistLoading && "animate-pulse"
              )}
            />
            <span className="hidden sm:inline text-xs sm:text-sm">
              {isInWatchlist ? 'Saved' : 'Save'}
            </span>
          </Button>
        </Tooltip>

        {/* Price Alert Button */}
        {onSetPriceAlert && (
          <Tooltip content={!isLoggedIn ? 'Log in to set price alerts' : 'Set price alert'}>
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5 sm:gap-2 px-2 sm:px-3"
              onClick={isLoggedIn ? onSetPriceAlert : undefined}
              disabled={!isLoggedIn}
              aria-label="Set price alert"
            >
              <Bell className="w-4 h-4" />
              <span className="hidden sm:inline text-xs sm:text-sm">Alert</span>
            </Button>
          </Tooltip>
        )}
      </div>
    </header>
  )
}
