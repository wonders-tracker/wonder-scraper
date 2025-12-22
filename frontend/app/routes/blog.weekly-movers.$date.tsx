import { createFileRoute, Link } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import {
  TrendingUp,
  TrendingDown,
  Calendar,
  DollarSign,
  BarChart3,
  ArrowLeft,
  ExternalLink,
} from 'lucide-react'
import { siteConfig } from '~/config/site'

const { apiUrl: API_URL } = siteConfig

export const Route = createFileRoute('/blog/weekly-movers/$date')({
  component: WeeklyMoversDetailPage,
})

interface CardMover {
  card_id: number
  name: string
  current_price: number
  prev_price: number
  pct_change: number
  volume?: number
}

interface VolumeLeader {
  card_id: number
  name: string
  sales_count: number
  total_volume: number
  avg_price: number
}

interface WeeklyMoversData {
  date: string
  week_start: string
  week_end: string
  total_sales: number
  total_volume: number
  avg_sale_price: number
  gainers: CardMover[]
  losers: CardMover[]
  volume_leaders: VolumeLeader[]
  new_highs: CardMover[]
  new_lows: CardMover[]
}

function WeeklyMoversDetailPage() {
  const { date } = Route.useParams()

  const { data, isLoading, error } = useQuery<WeeklyMoversData>({
    queryKey: ['weekly-movers', date],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/api/v1/blog/weekly-movers/${date}`)
      if (!res.ok) throw new Error('Failed to fetch weekly movers')
      return res.json()
    },
    staleTime: 10 * 60 * 1000,
  })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="animate-pulse">
          <div className="h-8 bg-muted rounded w-2/3 mb-4" />
          <div className="h-4 bg-muted rounded w-1/2" />
        </div>
        <div className="grid grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-24 bg-muted rounded" />
          ))}
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="space-y-4">
        <Link
          to="/blog/weekly-movers"
          className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-2"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Archive
        </Link>
        <div className="bg-red-500/10 text-red-500 rounded-lg p-6">
          Weekly movers data not available for this date.
        </div>
      </div>
    )
  }

  const weekStart = new Date(data.week_start).toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
  })
  const weekEnd = new Date(data.week_end).toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })

  return (
    <article className="space-y-8">
      {/* Header */}
      <header>
        <Link
          to="/blog/weekly-movers"
          className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-2 mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Archive
        </Link>

        <h1 className="text-3xl font-bold mb-2">Weekly Market Movers</h1>
        <p className="text-lg text-muted-foreground flex items-center gap-2">
          <Calendar className="w-5 h-5" />
          {weekStart} - {weekEnd}
        </p>
      </header>

      {/* Summary Stats */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center gap-2 text-muted-foreground text-sm mb-1">
            <BarChart3 className="w-4 h-4" />
            Total Sales
          </div>
          <p className="text-2xl font-bold">{data.total_sales.toLocaleString()}</p>
        </div>
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center gap-2 text-muted-foreground text-sm mb-1">
            <DollarSign className="w-4 h-4" />
            Total Volume
          </div>
          <p className="text-2xl font-bold">${data.total_volume.toLocaleString()}</p>
        </div>
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center gap-2 text-muted-foreground text-sm mb-1">
            <DollarSign className="w-4 h-4" />
            Avg Sale Price
          </div>
          <p className="text-2xl font-bold">${data.avg_sale_price.toFixed(2)}</p>
        </div>
      </section>

      {/* Top Gainers & Losers */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Gainers */}
        <div className="bg-card border border-border rounded-lg p-6">
          <h2 className="text-lg font-bold mb-4 flex items-center gap-2 text-green-500">
            <TrendingUp className="w-5 h-5" />
            Top Gainers
          </h2>
          <div className="space-y-3">
            {data.gainers.map((card, i) => (
              <Link
                key={card.card_id}
                to="/cards/$cardId"
                params={{ cardId: String(card.card_id) }}
                className="flex items-center justify-between p-3 bg-green-500/5 hover:bg-green-500/10 rounded-lg transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-muted-foreground w-6">#{i + 1}</span>
                  <div>
                    <p className="font-medium">{card.name}</p>
                    <p className="text-sm text-muted-foreground">
                      ${card.prev_price.toFixed(2)} → ${card.current_price.toFixed(2)}
                    </p>
                  </div>
                </div>
                <span className="text-green-500 font-bold">
                  +{card.pct_change.toFixed(1)}%
                </span>
              </Link>
            ))}
          </div>
        </div>

        {/* Losers */}
        <div className="bg-card border border-border rounded-lg p-6">
          <h2 className="text-lg font-bold mb-4 flex items-center gap-2 text-red-500">
            <TrendingDown className="w-5 h-5" />
            Top Losers
          </h2>
          <div className="space-y-3">
            {data.losers.map((card, i) => (
              <Link
                key={card.card_id}
                to="/cards/$cardId"
                params={{ cardId: String(card.card_id) }}
                className="flex items-center justify-between p-3 bg-red-500/5 hover:bg-red-500/10 rounded-lg transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-muted-foreground w-6">#{i + 1}</span>
                  <div>
                    <p className="font-medium">{card.name}</p>
                    <p className="text-sm text-muted-foreground">
                      ${card.prev_price.toFixed(2)} → ${card.current_price.toFixed(2)}
                    </p>
                  </div>
                </div>
                <span className="text-red-500 font-bold">
                  {card.pct_change.toFixed(1)}%
                </span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Volume Leaders */}
      {data.volume_leaders && data.volume_leaders.length > 0 && (
        <section className="bg-card border border-border rounded-lg p-6">
          <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-brand-400" />
            Volume Leaders
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground border-b border-border">
                  <th className="pb-2 font-medium">#</th>
                  <th className="pb-2 font-medium">Card</th>
                  <th className="pb-2 font-medium text-right">Sales</th>
                  <th className="pb-2 font-medium text-right">Volume</th>
                  <th className="pb-2 font-medium text-right">Avg Price</th>
                </tr>
              </thead>
              <tbody>
                {data.volume_leaders.map((card, i) => (
                  <tr key={card.card_id} className="border-b border-border/50">
                    <td className="py-3 text-muted-foreground">{i + 1}</td>
                    <td className="py-3">
                      <Link
                        to="/cards/$cardId"
                        params={{ cardId: String(card.card_id) }}
                        className="hover:text-brand-400 flex items-center gap-1"
                      >
                        {card.name}
                        <ExternalLink className="w-3 h-3" />
                      </Link>
                    </td>
                    <td className="py-3 text-right font-medium">{card.sales_count}</td>
                    <td className="py-3 text-right font-medium">${card.total_volume.toLocaleString()}</td>
                    <td className="py-3 text-right">${card.avg_price.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* New Highs & Lows */}
      {((data.new_highs && data.new_highs.length > 0) || (data.new_lows && data.new_lows.length > 0)) && (
        <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {data.new_highs && data.new_highs.length > 0 && (
            <div className="bg-card border border-border rounded-lg p-6">
              <h2 className="text-lg font-bold mb-4 text-yellow-500">New All-Time Highs</h2>
              <div className="space-y-2">
                {data.new_highs.map((card) => (
                  <Link
                    key={card.card_id}
                    to="/cards/$cardId"
                    params={{ cardId: String(card.card_id) }}
                    className="flex items-center justify-between p-2 hover:bg-muted/50 rounded"
                  >
                    <span>{card.name}</span>
                    <span className="font-medium">${card.current_price.toFixed(2)}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
          {data.new_lows && data.new_lows.length > 0 && (
            <div className="bg-card border border-border rounded-lg p-6">
              <h2 className="text-lg font-bold mb-4 text-blue-500">New All-Time Lows</h2>
              <div className="space-y-2">
                {data.new_lows.map((card) => (
                  <Link
                    key={card.card_id}
                    to="/cards/$cardId"
                    params={{ cardId: String(card.card_id) }}
                    className="flex items-center justify-between p-2 hover:bg-muted/50 rounded"
                  >
                    <span>{card.name}</span>
                    <span className="font-medium">${card.current_price.toFixed(2)}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {/* Footer */}
      <footer className="border-t border-border pt-6 text-sm text-muted-foreground">
        <p>
          Data sourced from eBay completed sales and Blokpax listings.
          Prices reflect actual transaction data, not asking prices.
        </p>
        <p className="mt-2">
          <Link to="/methodology" className="text-brand-400 hover:underline">
            Learn more about our methodology
          </Link>
        </p>
      </footer>
    </article>
  )
}
