/**
 * CompactStats - Minimal stat cards for market overview
 */

import { cn } from '@/lib/utils'
import { TrendingUp, DollarSign, Tag } from 'lucide-react'

type StatCardProps = {
  label: string
  value: string | number
  icon: React.ReactNode
  className?: string
}

function StatCard({ label, value, icon, className }: StatCardProps) {
  return (
    <div className={cn(
      'bg-card border border-border rounded-lg p-4',
      'hover:border-border/80 transition-colors',
      className
    )}>
      <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
        {icon}
        <span>{label}</span>
      </div>
      <div className="text-2xl font-semibold">{value}</div>
    </div>
  )
}

type CompactStatsProps = {
  totalSales: number
  dollarVolume: number
  dealCount: number
  className?: string
}

export function CompactStats({
  totalSales,
  dollarVolume,
  dealCount,
  className,
}: CompactStatsProps) {
  // Format dollar volume
  const formatDollarVolume = (value: number) => {
    if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`
    if (value >= 1000) return `$${(value / 1000).toFixed(1)}k`
    return `$${value.toFixed(0)}`
  }

  return (
    <div className={cn('grid grid-cols-3 gap-3', className)}>
      <StatCard
        label="Total Sales"
        value={totalSales.toLocaleString()}
        icon={<TrendingUp className="w-3.5 h-3.5" />}
      />
      <StatCard
        label="Dollar Volume"
        value={formatDollarVolume(dollarVolume)}
        icon={<DollarSign className="w-3.5 h-3.5" />}
      />
      <StatCard
        label="Live Deals"
        value={dealCount}
        icon={<Tag className="w-3.5 h-3.5" />}
      />
    </div>
  )
}
