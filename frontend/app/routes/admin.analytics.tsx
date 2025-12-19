import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { api } from '../utils/auth'
import {
  Eye,
  Loader2,
  RefreshCw,
  Monitor,
  Smartphone,
  Tablet,
  Globe,
  ExternalLink,
  TrendingUp,
  Users,
  Zap,
  MousePointer,
  Image,
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

export const Route = createFileRoute('/admin/analytics')({
  component: AdminAnalytics,
})

interface AdminStats {
  analytics: {
    total_pageviews: number
    pageviews_24h: number
    pageviews_7d: number
    unique_visitors_24h: number
    unique_visitors_7d: number
    top_pages: Array<{ path: string; views: number }>
    device_breakdown: Array<{ device: string; count: number }>
    daily_pageviews: Array<{ date: string; count: number }>
    top_referrers: Array<{ referrer: string; count: number }>
    popular_cards: Array<{
      path: string
      card_id: number | null
      card_name: string | null
      image_url: string | null
      views: number
    }>
    total_events: number
    events_24h: number
    events_7d: number
    top_events: Array<{ event_name: string; count: number }>
    daily_events: Array<{ date: string; count: number }>
    external_clicks: Array<{ platform: string; count: number }>
  }
}

function AdminAnalytics() {
  const { data: stats, isLoading, error, refetch } = useQuery<AdminStats>({
    queryKey: ['admin-stats'],
    queryFn: async () => {
      return api.get('admin/stats').json<AdminStats>()
    },
    refetchInterval: 60000, // Every minute
  })

  const analytics = stats?.analytics

  // Show error state
  if (error) {
    return (
      <div className="p-4 md:p-6">
        <div className="border border-red-500/50 bg-red-500/10 rounded-lg p-4">
          <h2 className="text-red-400 font-semibold mb-2">Error Loading Analytics</h2>
          <p className="text-sm text-muted-foreground">
            {error instanceof Error ? error.message : 'Failed to load analytics data'}
          </p>
          <p className="text-xs text-muted-foreground mt-2">
            Make sure you're logged in as a superuser.
          </p>
          <button
            onClick={() => refetch()}
            className="mt-3 px-3 py-1.5 bg-red-500/20 text-red-400 rounded text-sm hover:bg-red-500/30"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Eye className="w-6 h-6" />
            Traffic Analytics
          </h1>
          <p className="text-sm text-muted-foreground">
            Site traffic and visitor insights
          </p>
        </div>
        <div className="flex gap-2">
          <a
            href="https://analytics.google.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs bg-muted text-muted-foreground px-3 py-2 rounded hover:bg-muted/80 transition-colors flex items-center gap-1"
          >
            <ExternalLink className="w-3 h-3" />
            Google Analytics
          </a>
          <button
            onClick={() => refetch()}
            className="p-2 rounded-md hover:bg-muted transition-colors"
            disabled={isLoading}
          >
            <RefreshCw className={`w-5 h-5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          {/* Stats Row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="border rounded-lg p-4 bg-card">
              <div className="flex items-center gap-2 mb-2">
                <Eye className="w-4 h-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">Page Views (24h)</span>
              </div>
              <div className="text-2xl font-bold">{analytics?.pageviews_24h?.toLocaleString() ?? 0}</div>
            </div>
            <div className="border rounded-lg p-4 bg-card">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="w-4 h-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">Page Views (7d)</span>
              </div>
              <div className="text-2xl font-bold">{analytics?.pageviews_7d?.toLocaleString() ?? 0}</div>
            </div>
            <div className="border rounded-lg p-4 bg-card">
              <div className="flex items-center gap-2 mb-2">
                <Users className="w-4 h-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">Visitors (24h)</span>
              </div>
              <div className="text-2xl font-bold text-brand-400">{analytics?.unique_visitors_24h?.toLocaleString() ?? 0}</div>
            </div>
            <div className="border rounded-lg p-4 bg-card">
              <div className="flex items-center gap-2 mb-2">
                <Users className="w-4 h-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">Visitors (7d)</span>
              </div>
              <div className="text-2xl font-bold text-blue-500">{analytics?.unique_visitors_7d?.toLocaleString() ?? 0}</div>
            </div>
          </div>

          {/* Daily Pageviews Chart */}
          {analytics?.daily_pageviews && analytics.daily_pageviews.length > 0 && (
            <div className="border rounded-lg p-4 bg-card">
              <h2 className="text-sm font-semibold mb-4">Daily Page Views (Last 7 Days)</h2>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={[...analytics.daily_pageviews].reverse()}>
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
                      formatter={(value: number) => [value.toLocaleString(), 'Views']}
                    />
                    <Bar dataKey="count" fill="#22c55e" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Popular Cards */}
          {analytics?.popular_cards && analytics.popular_cards.length > 0 && (
            <div className="border rounded-lg p-4 bg-card">
              <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <Image className="w-4 h-4" />
                Popular Cards (Last 7 Days)
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {analytics.popular_cards.slice(0, 10).map((card, i) => (
                  <a
                    key={card.path}
                    href={card.path}
                    className="border rounded-lg p-2 hover:bg-muted/50 transition-colors group"
                  >
                    <div className="aspect-[3/4] rounded overflow-hidden mb-2 bg-muted">
                      {card.image_url ? (
                        <img
                          src={card.image_url}
                          alt={card.card_name || `Card ${card.card_id}`}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                          <Image className="w-8 h-8" />
                        </div>
                      )}
                    </div>
                    <div className="text-xs truncate font-medium">
                      {card.card_name || `Card ${card.card_id}`}
                    </div>
                    <div className="text-xs text-muted-foreground flex items-center justify-between mt-1">
                      <span className="text-brand-400">#{i + 1}</span>
                      <span>{card.views.toLocaleString()} views</span>
                    </div>
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Events Section */}
          <div className="border rounded-lg p-4 bg-card">
            <h2 className="text-sm font-semibold mb-4 flex items-center gap-2">
              <Zap className="w-4 h-4" />
              Events Tracking
            </h2>

            {/* Events Stats Row */}
            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="border rounded-lg p-3 bg-muted/30">
                <div className="text-xs text-muted-foreground mb-1">Events (24h)</div>
                <div className="text-xl font-bold">{analytics?.events_24h?.toLocaleString() ?? 0}</div>
              </div>
              <div className="border rounded-lg p-3 bg-muted/30">
                <div className="text-xs text-muted-foreground mb-1">Events (7d)</div>
                <div className="text-xl font-bold">{analytics?.events_7d?.toLocaleString() ?? 0}</div>
              </div>
              <div className="border rounded-lg p-3 bg-muted/30">
                <div className="text-xs text-muted-foreground mb-1">Total Events</div>
                <div className="text-xl font-bold">{analytics?.total_events?.toLocaleString() ?? 0}</div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Top Events */}
              <div>
                <h3 className="text-xs font-semibold mb-2 text-muted-foreground uppercase tracking-wide">Top Events</h3>
                <div className="space-y-2">
                  {analytics?.top_events?.slice(0, 8).map((event, i) => {
                    const maxCount = analytics.top_events[0]?.count || 1
                    const percentage = (event.count / maxCount) * 100
                    return (
                      <div key={event.event_name} className="relative">
                        <div
                          className="absolute inset-0 bg-blue-500/10 rounded"
                          style={{ width: `${percentage}%` }}
                        />
                        <div className="relative flex items-center justify-between p-2">
                          <div className="flex items-center gap-2">
                            <MousePointer className="w-3 h-3 text-muted-foreground" />
                            <span className="text-xs font-mono">{event.event_name}</span>
                          </div>
                          <span className="text-sm font-medium">{event.count.toLocaleString()}</span>
                        </div>
                      </div>
                    )
                  })}
                  {(!analytics?.top_events || analytics.top_events.length === 0) && (
                    <p className="text-sm text-muted-foreground text-center py-4">No events tracked yet</p>
                  )}
                </div>
              </div>

              {/* External Clicks by Platform */}
              <div>
                <h3 className="text-xs font-semibold mb-2 text-muted-foreground uppercase tracking-wide">External Clicks by Platform</h3>
                <div className="space-y-2">
                  {analytics?.external_clicks?.map((click) => {
                    const totalClicks = analytics.external_clicks.reduce((sum, c) => sum + c.count, 0)
                    const percentage = totalClicks > 0 ? (click.count / totalClicks) * 100 : 0
                    return (
                      <div key={click.platform} className="flex items-center gap-3">
                        <ExternalLink className="w-4 h-4 text-muted-foreground" />
                        <div className="flex-1">
                          <div className="flex justify-between mb-1">
                            <span className="capitalize text-sm">{click.platform}</span>
                            <span className="text-sm text-muted-foreground">{click.count.toLocaleString()}</span>
                          </div>
                          <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                            <div
                              className="h-full bg-brand-500 rounded-full"
                              style={{ width: `${percentage}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    )
                  })}
                  {(!analytics?.external_clicks || analytics.external_clicks.length === 0) && (
                    <p className="text-sm text-muted-foreground text-center py-4">No external link clicks yet</p>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Top Pages, Devices, Referrers */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Top Pages */}
            <div className="md:col-span-2 border rounded-lg p-4 bg-card">
              <h2 className="text-sm font-semibold mb-3">Top Pages</h2>
              <div className="space-y-2">
                {analytics?.top_pages?.slice(0, 10).map((page, i) => {
                  const maxViews = analytics.top_pages[0]?.views || 1
                  const percentage = (page.views / maxViews) * 100
                  return (
                    <div key={page.path} className="relative">
                      <div
                        className="absolute inset-0 bg-primary/10 rounded"
                        style={{ width: `${percentage}%` }}
                      />
                      <div className="relative flex items-center justify-between p-2">
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-muted-foreground w-4">{i + 1}.</span>
                          <span className="font-mono text-xs truncate max-w-[200px]">{page.path}</span>
                        </div>
                        <span className="text-sm font-medium">{page.views.toLocaleString()}</span>
                      </div>
                    </div>
                  )
                })}
                {(!analytics?.top_pages || analytics.top_pages.length === 0) && (
                  <p className="text-sm text-muted-foreground text-center py-4">No page view data</p>
                )}
              </div>
            </div>

            {/* Devices & Referrers */}
            <div className="space-y-6">
              {/* Device Breakdown */}
              <div className="border rounded-lg p-4 bg-card">
                <h2 className="text-sm font-semibold mb-3">Devices</h2>
                <div className="space-y-2">
                  {analytics?.device_breakdown?.map((device) => {
                    const Icon = device.device === 'mobile' ? Smartphone
                      : device.device === 'tablet' ? Tablet
                      : Monitor
                    const totalDevices = analytics.device_breakdown.reduce((sum, d) => sum + d.count, 0)
                    const percentage = totalDevices > 0 ? (device.count / totalDevices) * 100 : 0
                    return (
                      <div key={device.device} className="flex items-center gap-3">
                        <Icon className="w-4 h-4 text-muted-foreground" />
                        <div className="flex-1">
                          <div className="flex justify-between mb-1">
                            <span className="capitalize text-sm">{device.device}</span>
                            <span className="text-sm text-muted-foreground">{device.count.toLocaleString()}</span>
                          </div>
                          <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                            <div
                              className="h-full bg-primary rounded-full"
                              style={{ width: `${percentage}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    )
                  })}
                  {(!analytics?.device_breakdown || analytics.device_breakdown.length === 0) && (
                    <p className="text-sm text-muted-foreground text-center py-2">No data</p>
                  )}
                </div>
              </div>

              {/* Top Referrers */}
              <div className="border rounded-lg p-4 bg-card">
                <h2 className="text-sm font-semibold mb-3">Top Referrers</h2>
                <div className="space-y-2">
                  {analytics?.top_referrers?.slice(0, 5).map((ref) => (
                    <div key={ref.referrer} className="flex items-center gap-2 text-sm">
                      <Globe className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                      <span className="truncate flex-1">{ref.referrer}</span>
                      <span className="text-muted-foreground">{ref.count}</span>
                    </div>
                  ))}
                  {(!analytics?.top_referrers || analytics.top_referrers.length === 0) && (
                    <p className="text-sm text-muted-foreground text-center py-2">No referrer data</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
