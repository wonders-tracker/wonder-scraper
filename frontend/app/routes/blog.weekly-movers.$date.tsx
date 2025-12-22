import { createFileRoute, Link } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { Calendar, ArrowLeft, ArrowRight, Share2 } from 'lucide-react'
import { siteConfig } from '~/config/site'
import { MarketStatsRow } from '~/components/blog/MarketStatsRow'
import { MoversTable } from '~/components/blog/MoversTable'
import { VolumeLeadersTable } from '~/components/blog/VolumeLeadersTable'

const { apiUrl: API_URL } = siteConfig

export const Route = createFileRoute('/blog/weekly-movers/$date')({
  component: WeeklyMoversDetailPage,
})

interface WeeklyMoversData {
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
      <div className="max-w-5xl mx-auto space-y-8 animate-pulse">
        <div className="h-10 bg-muted rounded w-1/2" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => <div key={i} className="h-24 bg-muted rounded-xl" />)}
        </div>
        <div className="grid md:grid-cols-2 gap-6">
          <div className="h-96 bg-muted rounded-xl" />
          <div className="h-96 bg-muted rounded-xl" />
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="max-w-5xl mx-auto">
        <Link
          to="/blog/weekly-movers"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Archive
        </Link>
        <div className="bg-red-500/10 text-red-500 rounded-xl p-8 text-center">
          <p className="font-medium">Data not available for this week</p>
          <p className="text-sm mt-2 opacity-80">Try selecting a different date from the archive.</p>
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

  const shareUrl = typeof window !== 'undefined' ? window.location.href : ''
  const shareText = `Wonders TCG Market Report: ${weekStart} - ${weekEnd}`

  return (
    <article className="max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <header>
        <Link
          to="/blog"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Market Insights
        </Link>

        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl md:text-4xl font-bold mb-2">Weekly Market Report</h1>
            <p className="text-lg text-muted-foreground flex items-center gap-2">
              <Calendar className="w-5 h-5" />
              {weekStart} — {weekEnd}
            </p>
          </div>
          <a
            href={`https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(shareUrl)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 text-muted-foreground hover:text-foreground rounded-lg hover:bg-muted transition-colors"
            title="Share on Twitter"
          >
            <Share2 className="w-5 h-5" />
          </a>
        </div>
      </header>

      {/* Stats */}
      <MarketStatsRow
        totalVolume={data.total_volume}
        totalSales={data.total_sales}
        avgPrice={data.avg_sale_price}
      />

      {/* Movers */}
      <div className="grid md:grid-cols-2 gap-6">
        <MoversTable
          title="Top Gainers"
          movers={data.gainers}
          type="gainers"
        />
        <MoversTable
          title="Top Losers"
          movers={data.losers}
          type="losers"
        />
      </div>

      {/* Volume Leaders */}
      {data.volume_leaders && data.volume_leaders.length > 0 && (
        <VolumeLeadersTable leaders={data.volume_leaders} />
      )}

      {/* New Highs/Lows */}
      {((data.new_highs?.length > 0) || (data.new_lows?.length > 0)) && (
        <div className="grid md:grid-cols-2 gap-6">
          {data.new_highs?.length > 0 && (
            <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/5 p-5">
              <h3 className="font-semibold text-yellow-500 mb-4">New All-Time Highs</h3>
              <div className="space-y-3">
                {data.new_highs.map(card => (
                  <Link
                    key={card.card_id}
                    to="/cards/$cardId"
                    params={{ cardId: String(card.card_id) }}
                    className="flex items-center justify-between hover:opacity-80"
                  >
                    <span className="font-medium">{card.name}</span>
                    <span className="text-yellow-500 font-bold">${card.current_price.toFixed(2)}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
          {data.new_lows?.length > 0 && (
            <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-5">
              <h3 className="font-semibold text-blue-500 mb-4">New All-Time Lows</h3>
              <div className="space-y-3">
                {data.new_lows.map(card => (
                  <Link
                    key={card.card_id}
                    to="/cards/$cardId"
                    params={{ cardId: String(card.card_id) }}
                    className="flex items-center justify-between hover:opacity-80"
                  >
                    <span className="font-medium">{card.name}</span>
                    <span className="text-blue-500 font-bold">${card.current_price.toFixed(2)}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <footer className="border-t border-border pt-8 text-sm text-muted-foreground">
        <p>
          Data sourced from eBay completed sales and Blokpax listings.
          Prices reflect actual transactions, not asking prices.
        </p>
        <div className="flex items-center gap-4 mt-4">
          <Link to="/methodology" className="text-brand-400 hover:underline">
            Methodology
          </Link>
          <Link to="/blog/weekly-movers" className="text-brand-400 hover:underline flex items-center gap-1">
            View Archive <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      </footer>
    </article>
  )
}
