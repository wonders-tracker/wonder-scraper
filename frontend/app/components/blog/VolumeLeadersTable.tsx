import { Link } from '@tanstack/react-router'
import { BarChart3 } from 'lucide-react'
import { slugify } from '@/lib/formatters'

interface VolumeLeader {
  card_id: number
  name: string
  sales_count: number
  total_volume: number
  avg_price: number
}

interface VolumeLeadersTableProps {
  leaders: VolumeLeader[]
}

export function VolumeLeadersTable({ leaders }: VolumeLeadersTableProps) {
  const maxVolume = Math.max(...leaders.map(l => l.total_volume), 1)

  return (
    <div className="rounded-xl border border-border overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center gap-2 bg-muted/30">
        <BarChart3 className="w-4 h-4 text-brand-400" />
        <h3 className="font-semibold">Volume Leaders</h3>
      </div>
      <div className="divide-y divide-border">
        {leaders.map((leader, idx) => (
          <Link
            key={leader.card_id}
            to="/cards/$cardId"
            params={{ cardId: slugify(leader.name) }}
            className="block px-4 py-3 hover:bg-muted/30 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                <span className="text-muted-foreground text-sm w-6">{idx + 1}</span>
                <span className="font-medium">{leader.name}</span>
              </div>
              <span className="font-bold">${leader.total_volume.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-6" />
              <div className="flex-1">
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-brand-400 rounded-full transition-all"
                    style={{ width: `${(leader.total_volume / maxVolume) * 100}%` }}
                  />
                </div>
              </div>
              <span className="text-sm text-muted-foreground w-24 text-right">
                {leader.sales_count} sales
              </span>
            </div>
          </Link>
        ))}
        {leaders.length === 0 && (
          <div className="px-4 py-8 text-center text-muted-foreground">
            No data available
          </div>
        )}
      </div>
    </div>
  )
}
