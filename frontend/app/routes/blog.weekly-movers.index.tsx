import { createFileRoute, Link } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { Calendar, TrendingUp, TrendingDown, ArrowRight } from 'lucide-react'
import { siteConfig } from '~/config/site'

const { apiUrl: API_URL } = siteConfig

export const Route = createFileRoute('/blog/weekly-movers/')({
  component: WeeklyMoversArchivePage,
})

interface WeekSummary {
  date: string
  week_start: string
  week_end: string
  total_sales: number
  total_volume: number
  top_gainer: {
    name: string
    pct_change: number
  } | null
  top_loser: {
    name: string
    pct_change: number
  } | null
}

function WeeklyMoversArchivePage() {
  const { data: weeks, isLoading, error } = useQuery<WeekSummary[]>({
    queryKey: ['weekly-movers', 'archive'],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/api/v1/blog/weekly-movers`)
      if (!res.ok) return []
      return res.json()
    },
    staleTime: 5 * 60 * 1000,
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Weekly Market Movers</h1>
        <p className="text-muted-foreground">
          Archive of weekly price movements, top gainers, and market trends
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="animate-pulse bg-card border border-border rounded-lg p-6">
              <div className="h-5 bg-muted rounded w-1/3 mb-4" />
              <div className="h-4 bg-muted rounded w-1/2" />
            </div>
          ))}
        </div>
      ) : error ? (
        <div className="bg-red-500/10 text-red-500 rounded-lg p-6">
          Failed to load weekly movers archive
        </div>
      ) : weeks && weeks.length > 0 ? (
        <div className="space-y-4">
          {weeks.map((week) => (
            <Link
              key={week.date}
              to="/blog/weekly-movers/$date"
              params={{ date: week.date }}
              className="block bg-card border border-border rounded-lg p-6 hover:border-brand-400 transition-colors"
            >
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-lg font-bold flex items-center gap-2">
                  <Calendar className="w-5 h-5 text-brand-400" />
                  Week of {new Date(week.week_start).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - {new Date(week.week_end).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                </h2>
                <ArrowRight className="w-5 h-5 text-muted-foreground" />
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Sales</span>
                  <p className="font-medium">{week.total_sales.toLocaleString()}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Volume</span>
                  <p className="font-medium">${week.total_volume.toLocaleString()}</p>
                </div>
                {week.top_gainer && (
                  <div>
                    <span className="text-muted-foreground flex items-center gap-1">
                      <TrendingUp className="w-3 h-3 text-green-500" />
                      Top Gainer
                    </span>
                    <p className="font-medium text-green-500 truncate">
                      {week.top_gainer.name} (+{week.top_gainer.pct_change.toFixed(1)}%)
                    </p>
                  </div>
                )}
                {week.top_loser && (
                  <div>
                    <span className="text-muted-foreground flex items-center gap-1">
                      <TrendingDown className="w-3 h-3 text-red-500" />
                      Top Loser
                    </span>
                    <p className="font-medium text-red-500 truncate">
                      {week.top_loser.name} ({week.top_loser.pct_change.toFixed(1)}%)
                    </p>
                  </div>
                )}
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="bg-muted/30 rounded-lg p-6 text-center text-muted-foreground">
          <p>No weekly movers data available yet.</p>
          <p className="mt-2 text-sm">Check back after the first week of market tracking.</p>
        </div>
      )}
    </div>
  )
}
