import { Link } from '@tanstack/react-router'
import { TrendingUp, TrendingDown } from 'lucide-react'

interface Mover {
  card_id: number
  name: string
  current_price: number
  prev_price: number
  pct_change: number
}

interface MoversTableProps {
  title: string
  movers: Mover[]
  type: 'gainers' | 'losers'
}

export function MoversTable({ title, movers, type }: MoversTableProps) {
  const isGainer = type === 'gainers'
  const Icon = isGainer ? TrendingUp : TrendingDown
  const colorClass = isGainer ? 'text-green-500' : 'text-red-500'
  const bgClass = isGainer ? 'bg-green-500/5 border-green-500/20' : 'bg-red-500/5 border-red-500/20'

  return (
    <div className={`rounded-xl border ${bgClass} overflow-hidden`}>
      <div className={`px-4 py-3 border-b ${bgClass} flex items-center gap-2`}>
        <Icon className={`w-4 h-4 ${colorClass}`} />
        <h3 className={`font-semibold ${colorClass}`}>{title}</h3>
      </div>
      <div className="divide-y divide-border">
        {movers.map((mover, idx) => (
          <Link
            key={mover.card_id}
            to="/cards/$cardId"
            params={{ cardId: String(mover.card_id) }}
            className="flex items-center gap-4 px-4 py-3 hover:bg-muted/30 transition-colors"
          >
            <span className="text-muted-foreground text-sm w-6">{idx + 1}</span>
            <div className="flex-1 min-w-0">
              <div className="font-medium truncate">{mover.name}</div>
              <div className="text-sm text-muted-foreground">
                ${mover.prev_price.toFixed(2)} → ${mover.current_price.toFixed(2)}
              </div>
            </div>
            <div className={`text-right ${colorClass}`}>
              <div className="font-bold text-lg">
                {isGainer ? '+' : ''}{mover.pct_change.toFixed(1)}%
              </div>
            </div>
          </Link>
        ))}
        {movers.length === 0 && (
          <div className="px-4 py-8 text-center text-muted-foreground">
            No data available
          </div>
        )}
      </div>
    </div>
  )
}
