import { createFileRoute, Link } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Calendar, TrendingUp, TrendingDown, BookOpen } from 'lucide-react'
import { siteConfig } from '~/config/site'
import { MarketStatsRow } from '~/components/blog/MarketStatsRow'
import { MoversTable } from '~/components/blog/MoversTable'

const { apiUrl: API_URL } = siteConfig

interface BlogPost {
  slug: string
  title: string
  description: string
  publishedAt: string
  author: string
  category: string
  tags: string[]
}

export const Route = createFileRoute('/blog/')({
  component: BlogIndexPage,
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
}

interface WeekSummary {
  date: string
  week_start: string
  week_end: string
  total_sales: number
  total_volume: number
}

function BlogIndexPage() {
  // Fetch latest market data
  const { data: latest, isLoading } = useQuery<WeeklyData>({
    queryKey: ['weekly-movers', 'latest'],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/api/v1/blog/weekly-movers/latest`)
      if (!res.ok) return null
      return res.json()
    },
    staleTime: 5 * 60 * 1000,
  })

  // Fetch archive
  const { data: archive } = useQuery<WeekSummary[]>({
    queryKey: ['weekly-movers', 'archive'],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/api/v1/blog/weekly-movers?limit=5`)
      if (!res.ok) return []
      return res.json()
    },
    staleTime: 5 * 60 * 1000,
  })

  // Fetch blog posts
  const { data: posts } = useQuery<BlogPost[]>({
    queryKey: ['blog-posts'],
    queryFn: async () => {
      const res = await fetch('/blog-manifest.json')
      if (!res.ok) return []
      return res.json()
    },
    staleTime: 60 * 60 * 1000, // Cache for 1 hour
  })

  const weekStart = latest ? new Date(latest.week_start).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  }) : ''
  const weekEnd = latest ? new Date(latest.week_end).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }) : ''

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-4xl md:text-5xl font-bold mb-2">Market Insights</h1>
          <p className="text-muted-foreground">
            Weekly market reports for Wonders of the First TCG
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-6 animate-pulse">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-24 bg-muted rounded-xl" />
            ))}
          </div>
          <div className="grid md:grid-cols-2 gap-6">
            <div className="h-80 bg-muted rounded-xl" />
            <div className="h-80 bg-muted rounded-xl" />
          </div>
        </div>
      ) : latest ? (
        <>
          {/* Date */}
          <div className="flex items-center justify-between">
            <p className="text-muted-foreground flex items-center gap-2">
              <Calendar className="w-4 h-4" />
              {weekStart} — {weekEnd}
            </p>
            <Link
              to="/blog/weekly-movers/$date"
              params={{ date: latest.date }}
              className="text-sm text-brand-400 hover:underline flex items-center gap-1"
            >
              Full Report <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          {/* Stats */}
          <MarketStatsRow
            totalVolume={latest.total_volume}
            totalSales={latest.total_sales}
            avgPrice={latest.avg_sale_price}
          />

          {/* Movers */}
          <div className="grid md:grid-cols-2 gap-6">
            <MoversTable
              title="Top Gainers"
              movers={latest.gainers.slice(0, 5)}
              type="gainers"
            />
            <MoversTable
              title="Top Losers"
              movers={latest.losers.slice(0, 5)}
              type="losers"
            />
          </div>

          {/* CTA */}
          <div className="text-center">
            <Link
              to="/blog/weekly-movers/$date"
              params={{ date: latest.date }}
              className="inline-flex items-center gap-2 px-6 py-3 bg-brand-400 text-black font-semibold rounded-lg hover:bg-brand-300 transition-colors"
            >
              View Full Report <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </>
      ) : (
        <div className="text-center py-12 text-muted-foreground">
          <p>Market data coming soon.</p>
        </div>
      )}

      {/* Archive */}
      {archive && archive.length > 1 && (
        <div className="border-t border-border pt-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold">Previous Reports</h2>
            <Link
              to="/blog/weekly-movers"
              className="text-sm text-brand-400 hover:underline flex items-center gap-1"
            >
              View All <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="grid gap-3">
            {archive.slice(1, 4).map((week) => {
              const start = new Date(week.week_start).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
              })
              const end = new Date(week.week_end).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
              })
              return (
                <Link
                  key={week.date}
                  to="/blog/weekly-movers/$date"
                  params={{ date: week.date }}
                  className="flex items-center justify-between p-4 bg-card border border-border rounded-lg hover:border-brand-400 transition-colors"
                >
                  <div>
                    <div className="font-medium">Week of {start} — {end}</div>
                    <div className="text-sm text-muted-foreground">
                      {week.total_sales} sales · ${week.total_volume.toLocaleString(undefined, { maximumFractionDigits: 0 })} volume
                    </div>
                  </div>
                  <ArrowRight className="w-4 h-4 text-muted-foreground" />
                </Link>
              )
            })}
          </div>
        </div>
      )}

      {/* Blog Posts */}
      {posts && posts.length > 0 && (
        <div className="border-t border-border pt-8">
          <div className="flex items-center gap-2 mb-4">
            <BookOpen className="w-5 h-5 text-brand-400" />
            <h2 className="text-xl font-bold">Guides & Analysis</h2>
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {posts.map((post) => (
              <Link
                key={post.slug}
                to="/blog/$slug"
                params={{ slug: post.slug }}
                className="group p-5 bg-card border border-border rounded-xl hover:border-brand-400 transition-colors"
              >
                <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                  <span className="px-2 py-0.5 bg-muted rounded-full capitalize">{post.category}</span>
                  <span>·</span>
                  <span>{new Date(post.publishedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
                </div>
                <h3 className="font-semibold mb-2 group-hover:text-brand-400 transition-colors">{post.title}</h3>
                <p className="text-sm text-muted-foreground line-clamp-2">{post.description}</p>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
