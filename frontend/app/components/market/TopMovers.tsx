/**
 * TopMovers - Top gainers and losers lists
 */

import { Link } from '@tanstack/react-router'
import { cn } from '@/lib/utils'
import { ArrowUp, ArrowDown } from 'lucide-react'
import { slugify } from '@/lib/formatters'

type Mover = {
  id: number
  slug?: string
  name: string
  price_delta: number
  floor_price?: number
}

type TopMoversProps = {
  gainers: Mover[]
  losers: Mover[]
  className?: string
}

function MoverList({
  title,
  movers,
  type,
}: {
  title: string
  movers: Mover[]
  type: 'gainers' | 'losers'
}) {
  const isGainer = type === 'gainers'
  const Icon = isGainer ? ArrowUp : ArrowDown
  const colorClass = isGainer ? 'text-emerald-500' : 'text-red-500'

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      <div className={cn(
        'px-3 py-2 border-b border-border flex items-center gap-2',
        isGainer ? 'bg-emerald-500/5' : 'bg-red-500/5'
      )}>
        <Icon className={cn('w-3.5 h-3.5', colorClass)} />
        <span className="text-xs font-semibold">{title}</span>
      </div>
      <div className="divide-y divide-border/50">
        {movers.slice(0, 5).map((mover) => (
          <Link
            key={mover.id}
            to="/cards/$cardId"
            params={{ cardId: mover.slug || slugify(mover.name) }}
            className="flex items-center justify-between px-3 py-2 hover:bg-muted/30 transition-colors"
          >
            <span className="text-sm truncate max-w-[120px]">{mover.name}</span>
            <span className={cn('text-sm font-mono font-medium', colorClass)}>
              {isGainer ? '+' : ''}{mover.price_delta.toFixed(1)}%
            </span>
          </Link>
        ))}
        {movers.length === 0 && (
          <div className="px-3 py-4 text-xs text-muted-foreground text-center">
            No data
          </div>
        )}
      </div>
    </div>
  )
}

export function TopMovers({ gainers, losers, className }: TopMoversProps) {
  return (
    <div className={cn('grid grid-cols-1 sm:grid-cols-2 gap-3', className)}>
      <MoverList title="Top Gainers" movers={gainers} type="gainers" />
      <MoverList title="Top Losers" movers={losers} type="losers" />
    </div>
  )
}
