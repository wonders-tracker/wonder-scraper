import { createFileRoute, Link } from '@tanstack/react-router'
import { TrendingUp, TrendingDown, Calendar, ArrowRight } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { siteConfig } from '~/config/site'

const { apiUrl: API_URL } = siteConfig

export const Route = createFileRoute('/blog/')({
  component: BlogIndexPage,
})

interface WeeklyMoversData {
  date: string
  week_start: string
  week_end: string
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
  total_volume: number
  total_sales: number
}

function BlogIndexPage() {
  // Fetch latest weekly movers
  const { data: latestWeekly, isLoading } = useQuery<WeeklyMoversData>({
    queryKey: ['weekly-movers', 'latest'],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/api/v1/blog/weekly-movers/latest`)
      if (!res.ok) return null
      return res.json()
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold mb-2">WondersTracker Blog</h1>
        <p className="text-muted-foreground">
          Market analysis, price trends, and guides for Wonders of the First TCG
        </p>
      </div>

      {/* Featured: Latest Weekly Movers */}
      <section className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-brand-400" />
            Weekly Market Movers
          </h2>
          <Link
            to="/blog/weekly-movers"
            className="text-sm text-brand-400 hover:underline flex items-center gap-1"
          >
            View Archive <ArrowRight className="w-4 h-4" />
          </Link>
        </div>

        {isLoading ? (
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-muted rounded w-1/3" />
            <div className="grid grid-cols-2 gap-4">
              <div className="h-24 bg-muted rounded" />
              <div className="h-24 bg-muted rounded" />
            </div>
          </div>
        ) : latestWeekly ? (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground flex items-center gap-2">
              <Calendar className="w-4 h-4" />
              Week of {new Date(latestWeekly.week_start).toLocaleDateString()} - {new Date(latestWeekly.week_end).toLocaleDateString()}
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Top Gainers */}
              <div className="bg-green-500/10 rounded-lg p-4">
                <h3 className="text-sm font-bold text-green-500 mb-3 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4" />
                  Top Gainers
                </h3>
                <div className="space-y-2">
                  {latestWeekly.gainers?.slice(0, 3).map((card) => (
                    <Link
                      key={card.card_id}
                      to="/cards/$cardId"
                      params={{ cardId: String(card.card_id) }}
                      className="flex items-center justify-between text-sm hover:bg-green-500/10 rounded px-2 py-1 -mx-2"
                    >
                      <span className="truncate">{card.name}</span>
                      <span className="text-green-500 font-medium">
                        +{card.pct_change.toFixed(1)}%
                      </span>
                    </Link>
                  ))}
                </div>
              </div>

              {/* Top Losers */}
              <div className="bg-red-500/10 rounded-lg p-4">
                <h3 className="text-sm font-bold text-red-500 mb-3 flex items-center gap-2">
                  <TrendingDown className="w-4 h-4" />
                  Top Losers
                </h3>
                <div className="space-y-2">
                  {latestWeekly.losers?.slice(0, 3).map((card) => (
                    <Link
                      key={card.card_id}
                      to="/cards/$cardId"
                      params={{ cardId: String(card.card_id) }}
                      className="flex items-center justify-between text-sm hover:bg-red-500/10 rounded px-2 py-1 -mx-2"
                    >
                      <span className="truncate">{card.name}</span>
                      <span className="text-red-500 font-medium">
                        {card.pct_change.toFixed(1)}%
                      </span>
                    </Link>
                  ))}
                </div>
              </div>
            </div>

            <Link
              to="/blog/weekly-movers/$date"
              params={{ date: latestWeekly.date }}
              className="inline-flex items-center gap-2 text-sm text-brand-400 hover:underline mt-2"
            >
              View Full Report <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        ) : (
          <p className="text-muted-foreground text-sm">
            Weekly movers data coming soon. Check back after the first week of market tracking.
          </p>
        )}
      </section>

      {/* Blog Posts Section - Placeholder for now */}
      <section>
        <h2 className="text-xl font-bold mb-4">Latest Posts</h2>
        <div className="text-muted-foreground text-sm bg-muted/30 rounded-lg p-6 text-center">
          <p>Blog posts coming soon!</p>
          <p className="mt-2">We're working on market analysis, guides, and news updates.</p>
        </div>
      </section>

      {/* Categories */}
      <section>
        <h2 className="text-xl font-bold mb-4">Browse by Category</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link
            to="/blog"
            search={{ category: 'analysis' }}
            className="bg-card border border-border rounded-lg p-4 hover:border-brand-400 transition-colors"
          >
            <h3 className="font-bold mb-1">Market Analysis</h3>
            <p className="text-sm text-muted-foreground">
              Deep dives into price trends, treatment analysis, and market forecasts
            </p>
          </Link>
          <Link
            to="/blog"
            search={{ category: 'news' }}
            className="bg-card border border-border rounded-lg p-4 hover:border-brand-400 transition-colors"
          >
            <h3 className="font-bold mb-1">News & Updates</h3>
            <p className="text-sm text-muted-foreground">
              Site updates, new features, and TCG news
            </p>
          </Link>
          <Link
            to="/blog"
            search={{ category: 'guide' }}
            className="bg-card border border-border rounded-lg p-4 hover:border-brand-400 transition-colors"
          >
            <h3 className="font-bold mb-1">Guides</h3>
            <p className="text-sm text-muted-foreground">
              How to use the tracker, investment strategies, and tips
            </p>
          </Link>
        </div>
      </section>
    </div>
  )
}
