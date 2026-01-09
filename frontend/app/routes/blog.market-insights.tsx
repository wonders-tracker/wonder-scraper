import { createFileRoute, Link } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Calendar, RefreshCw } from 'lucide-react'
import { siteConfig } from '~/config/site'
import { MarketStatsRow } from '~/components/blog/MarketStatsRow'
import { MoversTable } from '~/components/blog/MoversTable'
import { VolumeLeadersTable } from '~/components/blog/VolumeLeadersTable'

const { apiUrl: API_URL } = siteConfig

export const Route = createFileRoute('/blog/market-insights')({
  component: MarketInsightsPage,
})

interface WeeklyData {
  date: string
  week_start: string
  week_end: string
  total_sales: number
  total_volume: number
  avg_sale_price: number
  gainers: Array<{
    card_id: number
    name: string
    current_price: number
    prev_price: number
    pct_change: number
  }>
  losers: Array<{
    card_id: number
    name: string
    current_price: number
    prev_price: number
    pct_change: number
  }>
  volume_leaders: Array<{
    card_id: number
    name: string
    sales_count: number
    total_volume: number
    avg_price: number
  }>
  new_highs: Array<{
    card_id: number
    name: string
    current_price: number
    prev_price: number
  }>
  new_lows: Array<{
    card_id: number
    name: string
    current_price: number
    prev_price: number
  }>
}

function MarketInsightsPage() {
  const { data, isLoading, error, refetch, dataUpdatedAt } = useQuery<WeeklyData>({
    queryKey: ['market-insights', 'latest'],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/blog/weekly-movers/latest`)
      if (!res.ok) throw new Error('Failed to fetch market data')
      return res.json()
    },
    staleTime: 5 * 60 * 1000,
  })

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto">
        <div className="animate-pulse space-y-8">
          <div className="h-8 bg-muted rounded w-1/3" />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-28 bg-muted rounded-xl" />
            ))}
          </div>
          <div className="grid md:grid-cols-2 gap-6">
            <div className="h-96 bg-muted rounded-xl" />
            <div className="h-96 bg-muted rounded-xl" />
          </div>
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="max-w-5xl mx-auto text-center py-20">
        <h1 className="text-2xl font-bold mb-4">Unable to Load Market Data</h1>
        <p className="text-muted-foreground mb-6">
          Please try again later.
        </p>
        <Link
          to="/blog"
          className="inline-flex items-center gap-2 text-brand-400 hover:underline"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Blog
        </Link>
      </div>
    )
  }

  const weekStart = new Date(data.week_start).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
  const weekEnd = new Date(data.week_end).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <Link
          to="/blog"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Blog
        </Link>
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold mb-2">Market Insights</h1>
            <p className="text-sm sm:text-base text-muted-foreground flex items-center gap-2">
              <Calendar className="w-4 h-4 flex-shrink-0" />
              <span>{weekStart} — {weekEnd}</span>
            </p>
          </div>
          <button
            onClick={() => refetch()}
            className="self-start p-2 text-muted-foreground hover:text-foreground rounded-lg hover:bg-muted transition-colors"
            title="Refresh data"
          >
            <RefreshCw className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Stats Row */}
      <div className="mb-8">
        <MarketStatsRow
          totalVolume={data.total_volume}
          totalSales={data.total_sales}
          avgPrice={data.avg_sale_price}
        />
      </div>

      {/* Movers Grid */}
      <div className="grid md:grid-cols-2 gap-6 mb-8">
        <MoversTable
          title="Top Gainers"
          movers={data.gainers.slice(0, 5)}
          type="gainers"
        />
        <MoversTable
          title="Top Losers"
          movers={data.losers.slice(0, 5)}
          type="losers"
        />
      </div>

      {/* Volume Leaders */}
      <div className="mb-8">
        <VolumeLeadersTable leaders={data.volume_leaders.slice(0, 5)} />
      </div>

      {/* New Highs/Lows */}
      {(data.new_highs.length > 0 || data.new_lows.length > 0) && (
        <div className="grid md:grid-cols-2 gap-6 mb-8">
          {data.new_highs.length > 0 && (
            <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/5 p-4">
              <h3 className="font-semibold text-yellow-500 mb-3">New Highs</h3>
              <div className="space-y-2">
                {data.new_highs.slice(0, 3).map(card => (
                  <Link
                    key={card.card_id}
                    to="/cards/$cardId"
                    params={{ cardId: String(card.card_id) }}
                    className="flex items-center justify-between hover:opacity-80"
                  >
                    <span>{card.name}</span>
                    <span className="font-medium">${card.current_price.toFixed(2)}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
          {data.new_lows.length > 0 && (
            <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-4">
              <h3 className="font-semibold text-blue-500 mb-3">New Lows</h3>
              <div className="space-y-2">
                {data.new_lows.slice(0, 3).map(card => (
                  <Link
                    key={card.card_id}
                    to="/cards/$cardId"
                    params={{ cardId: String(card.card_id) }}
                    className="flex items-center justify-between hover:opacity-80"
                  >
                    <span>{card.name}</span>
                    <span className="font-medium">${card.current_price.toFixed(2)}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="text-center text-sm text-muted-foreground py-8 border-t border-border">
        <p>Data updates every 15 minutes from eBay and Blokpax</p>
        {dataUpdatedAt && (
          <p className="mt-1">
            Last updated: {new Date(dataUpdatedAt).toLocaleTimeString()}
          </p>
        )}
      </div>
    </div>
  )
}
