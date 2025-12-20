import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { api } from '../utils/auth'
import {
  BarChart3,
  Loader2,
  RefreshCw,
  TrendingUp,
  Database,
  Package,
  Calendar,
} from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'

export const Route = createFileRoute('/admin/market')({
  component: AdminMarket,
})

interface AdminStats {
  cards: {
    total: number
  }
  listings: {
    total: number
    sold: number
    active: number
    last_24h: number
    last_7d: number
  }
  snapshots: {
    total: number
    latest: string | null
  }
  top_cards: Array<{ name: string; listings: number }>
  daily_volume: Array<{ date: string; count: number }>
}

function AdminMarket() {
  const { data: stats, isLoading, refetch } = useQuery<AdminStats>({
    queryKey: ['admin-stats'],
    queryFn: async () => {
      return api.get('admin/stats').json<AdminStats>()
    },
    refetchInterval: 60000,
  })

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <BarChart3 className="w-6 h-6" />
            Market Data
          </h1>
          <p className="text-sm text-muted-foreground">
            Listings, sales, and market activity
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="p-2 rounded-md hover:bg-muted transition-colors"
          disabled={isLoading}
        >
          <RefreshCw className={`w-5 h-5 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          {/* Stats Row */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="border rounded-lg p-4 bg-card">
              <div className="flex items-center gap-2 mb-2">
                <Package className="w-4 h-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">Total Cards</span>
              </div>
              <div className="text-2xl font-bold">{stats?.cards.total ?? 0}</div>
            </div>
            <div className="border rounded-lg p-4 bg-card">
              <div className="flex items-center gap-2 mb-2">
                <BarChart3 className="w-4 h-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">Total Listings</span>
              </div>
              <div className="text-2xl font-bold">{stats?.listings.total?.toLocaleString() ?? 0}</div>
            </div>
            <div className="border rounded-lg p-4 bg-card">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="w-4 h-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">Sales</span>
              </div>
              <div className="text-2xl font-bold text-brand-400">{stats?.listings.sold?.toLocaleString() ?? 0}</div>
            </div>
            <div className="border rounded-lg p-4 bg-card">
              <div className="flex items-center gap-2 mb-2">
                <Calendar className="w-4 h-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">Last 24h</span>
              </div>
              <div className="text-2xl font-bold text-blue-500">+{stats?.listings.last_24h?.toLocaleString() ?? 0}</div>
            </div>
            <div className="border rounded-lg p-4 bg-card">
              <div className="flex items-center gap-2 mb-2">
                <Database className="w-4 h-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">Snapshots</span>
              </div>
              <div className="text-2xl font-bold">{stats?.snapshots.total?.toLocaleString() ?? 0}</div>
            </div>
          </div>

          {/* Daily Volume Chart */}
          {stats?.daily_volume && stats.daily_volume.length > 0 && (
            <div className="border rounded-lg p-4 bg-card">
              <h2 className="text-sm font-semibold mb-4">Daily Scrape Volume (Last 7 Days)</h2>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={[...stats.daily_volume].reverse()}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                    <XAxis
                      dataKey="date"
                      tick={{ fill: '#888', fontSize: 12 }}
                      tickFormatter={(value) =>
                        new Date(value).toLocaleDateString('en-US', { weekday: 'short' })
                      }
                    />
                    <YAxis tick={{ fill: '#888', fontSize: 12 }} />
                    <RechartsTooltip
                      contentStyle={{
                        backgroundColor: 'hsl(var(--card))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '6px',
                      }}
                      labelFormatter={(value) => new Date(value).toLocaleDateString()}
                      formatter={(value: number) => [value.toLocaleString(), 'Listings']}
                    />
                    <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Top Cards */}
            <div className="border rounded-lg p-4 bg-card">
              <h2 className="text-sm font-semibold mb-4 flex items-center gap-2">
                <TrendingUp className="w-4 h-4" />
                Top Cards by Listing Count
              </h2>
              <div className="space-y-2">
                {stats?.top_cards?.slice(0, 10).map((card, i) => {
                  const maxListings = stats.top_cards[0]?.listings || 1
                  const percentage = (card.listings / maxListings) * 100
                  return (
                    <div key={card.name} className="relative">
                      <div
                        className="absolute inset-0 bg-primary/10 rounded"
                        style={{ width: `${percentage}%` }}
                      />
                      <div className="relative flex items-center justify-between p-2">
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-muted-foreground w-5">{i + 1}.</span>
                          <span className="text-sm font-medium truncate max-w-[180px]">{card.name}</span>
                        </div>
                        <span className="text-sm text-muted-foreground">
                          {card.listings.toLocaleString()}
                        </span>
                      </div>
                    </div>
                  )
                })}
                {(!stats?.top_cards || stats.top_cards.length === 0) && (
                  <p className="text-sm text-muted-foreground text-center py-4">No card data</p>
                )}
              </div>
            </div>

            {/* Market Summary */}
            <div className="border rounded-lg p-4 bg-card">
              <h2 className="text-sm font-semibold mb-4 flex items-center gap-2">
                <Database className="w-4 h-4" />
                Market Summary
              </h2>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
                  <span className="text-sm text-muted-foreground">Active Listings</span>
                  <span className="font-semibold">{stats?.listings.active?.toLocaleString() ?? 0}</span>
                </div>
                <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
                  <span className="text-sm text-muted-foreground">Sold Listings</span>
                  <span className="font-semibold text-brand-400">{stats?.listings.sold?.toLocaleString() ?? 0}</span>
                </div>
                <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
                  <span className="text-sm text-muted-foreground">New (7 days)</span>
                  <span className="font-semibold">{stats?.listings.last_7d?.toLocaleString() ?? 0}</span>
                </div>
                <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
                  <span className="text-sm text-muted-foreground">Latest Snapshot</span>
                  <span className="font-mono text-xs">
                    {stats?.snapshots.latest
                      ? new Date(stats.snapshots.latest).toLocaleString()
                      : 'Never'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
