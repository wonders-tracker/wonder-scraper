import { TrendingUp, TrendingDown, DollarSign, BarChart3, ShoppingCart, Percent } from 'lucide-react'

interface MarketStatsRowProps {
  totalVolume: number
  totalSales: number
  avgPrice: number
  volumeChange?: number
}

export function MarketStatsRow({ totalVolume, totalSales, avgPrice, volumeChange }: MarketStatsRowProps) {
  const stats = [
    {
      label: 'Total Volume',
      value: `$${totalVolume.toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
      icon: DollarSign,
      change: volumeChange,
    },
    {
      label: 'Sales',
      value: totalSales.toLocaleString(),
      icon: ShoppingCart,
    },
    {
      label: 'Avg Price',
      value: `$${avgPrice.toFixed(2)}`,
      icon: BarChart3,
    },
    {
      label: 'Cards Traded',
      value: totalSales > 0 ? Math.round(totalVolume / avgPrice).toLocaleString() : '0',
      icon: Percent,
    },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="bg-card border border-border rounded-xl p-4 md:p-6"
        >
          <div className="flex items-center gap-2 text-muted-foreground mb-2">
            <stat.icon className="w-4 h-4" />
            <span className="text-xs uppercase tracking-wide">{stat.label}</span>
          </div>
          <div className="text-2xl md:text-3xl font-bold">{stat.value}</div>
          {stat.change !== undefined && (
            <div className={`flex items-center gap-1 text-sm mt-1 ${stat.change >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              {stat.change >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
              {stat.change >= 0 ? '+' : ''}{stat.change.toFixed(1)}% vs last week
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
