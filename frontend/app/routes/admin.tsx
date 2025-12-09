import { createFileRoute, redirect, Link } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, auth } from '../utils/auth'
import {
  Users,
  Database,
  Activity,
  Clock,
  Play,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  TrendingUp,
  Package,
  BarChart3,
  HardDrive,
  Loader2,
  Server,
  ArrowLeft,
  Eye,
  Monitor,
  Smartphone,
  Tablet,
  Globe,
  ExternalLink,
  Key,
  Trash2,
  Shield,
  Zap,
  UserCheck,
  UserX,
  Code,
} from 'lucide-react'
import { Tooltip } from '../components/ui/tooltip'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'

export const Route = createFileRoute('/admin')({
  component: AdminDashboard,
  beforeLoad: () => {
    if (typeof window !== 'undefined' && !auth.isAuthenticated()) {
      throw redirect({ to: '/login' })
    }
  },
})

interface UserInfo {
  id: number
  email: string
  username: string | null
  discord_handle: string | null
  is_superuser: boolean
  is_active: boolean
  created_at: string | null
  last_login: string | null
}

interface AdminStats {
  users: {
    total: number
    active_24h: number
    list: UserInfo[]
  }
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
  portfolio: {
    total_cards: number
  }
  snapshots: {
    total: number
    latest: string | null
  }
  database: {
    size: string
  }
  top_cards: Array<{ name: string; listings: number }>
  daily_volume: Array<{ date: string; count: number }>
  scraper_jobs: Record<
    string,
    {
      status: string
      started?: string
      finished?: string
      processed?: number
      total?: number
      errors?: number
      error?: string
    }
  >
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
  }
}

interface SchedulerStatus {
  running: boolean
  jobs: Array<{
    id: string
    name: string
    next_run: string | null
    trigger: string
  }>
}

interface APIAccessRequest {
  id: number
  email: string
  username: string | null
  discord_handle: string | null
  requested_at: string | null
  created_at: string | null
}

function AdminDashboard() {
  const queryClient = useQueryClient()

  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
    refetch: refetchStats,
  } = useQuery<AdminStats>({
    queryKey: ['admin-stats'],
    queryFn: async () => {
      const res = await api.get('admin/stats').json<AdminStats>()
      return res
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  })

  const {
    data: schedulerStatus,
    isLoading: schedulerLoading,
    refetch: refetchScheduler,
  } = useQuery<SchedulerStatus>({
    queryKey: ['scheduler-status'],
    queryFn: async () => {
      const res = await api.get('admin/scheduler/status').json<SchedulerStatus>()
      return res
    },
    refetchInterval: 30000,
  })

  // API Access Requests
  const {
    data: apiAccessRequests,
    isLoading: apiAccessLoading,
    refetch: refetchApiAccess,
  } = useQuery<APIAccessRequest[]>({
    queryKey: ['api-access-requests'],
    queryFn: async () => {
      const res = await api.get('billing/api-access/requests').json<APIAccessRequest[]>()
      return res
    },
    refetchInterval: 60000,
  })

  const approveApiAccessMutation = useMutation({
    mutationFn: async (userId: number) => {
      await api.post(`billing/api-access/approve/${userId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-access-requests'] })
    },
  })

  const denyApiAccessMutation = useMutation({
    mutationFn: async (userId: number) => {
      await api.post(`billing/api-access/deny/${userId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-access-requests'] })
    },
  })

  const triggerScrapeMutation = useMutation({
    mutationFn: async () => {
      await api.post('admin/scrape/trigger')
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-stats'] })
    },
  })

  const triggerBackfillMutation = useMutation({
    mutationFn: async (params: { limit: number; force_all: boolean }) => {
      await api.post('admin/backfill', {
        json: { ...params, is_backfill: true },
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-stats'] })
    },
  })

  // Show error if not authorized (not superuser)
  if (statsError) {
    const errorMessage = (statsError as any)?.response?.status === 403
      ? "You don't have permission to access this page."
      : "Failed to load admin stats."

    return (
      <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center p-4">
        <div className="w-full max-w-md p-8 border rounded-lg bg-card text-center">
          <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold mb-2">Access Denied</h2>
          <p className="text-muted-foreground mb-4">{errorMessage}</p>
          <Link
            to="/"
            className="px-4 py-2 bg-muted text-foreground rounded-md hover:bg-muted/80 transition-colors inline-block"
          >
            Go Home
          </Link>
        </div>
      </div>
    )
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Never'
    return new Date(dateStr).toLocaleString()
  }

  const formatRelativeTime = (dateStr: string | null) => {
    if (!dateStr) return 'N/A'
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = date.getTime() - now.getTime()
    const diffMins = Math.round(diffMs / 60000)

    if (diffMins < 0) return 'Past due'
    if (diffMins < 60) return `in ${diffMins}m`
    const diffHours = Math.round(diffMins / 60)
    return `in ${diffHours}h`
  }

  // Get active scraper job
  const activeJob = stats?.scraper_jobs
    ? Object.entries(stats.scraper_jobs).find(
        ([_, job]) => job.status === 'running'
      )
    : null

  return (
    <div className="max-w-7xl mx-auto p-4 md:p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Link
            to="/"
            className="p-2 rounded-md hover:bg-muted transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Server className="w-6 h-6" />
              Server Health
            </h1>
            <p className="text-sm text-muted-foreground">
              System stats and scraper management
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Tooltip content="Refresh">
            <button
              onClick={() => {
                refetchStats()
                refetchScheduler()
              }}
              className="p-2 rounded-md hover:bg-muted transition-colors"
            >
              <RefreshCw
                className={`w-5 h-5 ${statsLoading ? 'animate-spin' : ''}`}
              />
            </button>
          </Tooltip>
        </div>
      </div>

      {statsLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="space-y-6">
          {/* Stats Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            <StatCard
              icon={Users}
              label="Users"
              value={stats?.users.total ?? 0}
              subtext={`${stats?.users.active_24h ?? 0} active today`}
            />
            <StatCard
              icon={Package}
              label="Cards"
              value={stats?.cards.total ?? 0}
            />
            <StatCard
              icon={BarChart3}
              label="Total Listings"
              value={stats?.listings.total ?? 0}
              subtext={`${stats?.listings.last_24h ?? 0} new today`}
            />
            <StatCard
              icon={TrendingUp}
              label="Sales"
              value={stats?.listings.sold ?? 0}
            />
            <StatCard
              icon={Activity}
              label="Active Listings"
              value={stats?.listings.active ?? 0}
            />
            <StatCard
              icon={HardDrive}
              label="DB Size"
              value={stats?.database.size ?? 'N/A'}
            />
          </div>

          {/* Users List */}
          <div className="border rounded-lg p-4 bg-card">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Users className="w-5 h-5" />
              Users ({stats?.users.total ?? 0})
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 px-2 text-muted-foreground font-medium">User</th>
                    <th className="text-left py-2 px-2 text-muted-foreground font-medium">Discord</th>
                    <th className="text-left py-2 px-2 text-muted-foreground font-medium">Role</th>
                    <th className="text-left py-2 px-2 text-muted-foreground font-medium">Joined</th>
                    <th className="text-left py-2 px-2 text-muted-foreground font-medium">Last Login</th>
                  </tr>
                </thead>
                <tbody>
                  {stats?.users.list.map((user) => (
                    <tr key={user.id} className="border-b border-border/50 hover:bg-muted/30">
                      <td className="py-2 px-2">
                        <div className="font-medium">{user.username || user.email}</div>
                        {user.username && (
                          <div className="text-xs text-muted-foreground">{user.email}</div>
                        )}
                      </td>
                      <td className="py-2 px-2 text-muted-foreground">
                        {user.discord_handle || '-'}
                      </td>
                      <td className="py-2 px-2">
                        {user.is_superuser ? (
                          <span className="text-xs px-2 py-0.5 rounded bg-primary/20 text-primary">Admin</span>
                        ) : (
                          <span className="text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">User</span>
                        )}
                      </td>
                      <td className="py-2 px-2 text-muted-foreground text-xs">
                        {user.created_at
                          ? new Date(user.created_at).toLocaleDateString()
                          : '-'}
                      </td>
                      <td className="py-2 px-2 text-muted-foreground text-xs">
                        {user.last_login
                          ? new Date(user.last_login).toLocaleString()
                          : 'Never'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* API Access Requests */}
          {apiAccessRequests && apiAccessRequests.length > 0 && (
            <div className="border rounded-lg p-4 bg-card border-amber-500/50">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Code className="w-5 h-5 text-amber-500" />
                <span className="text-amber-500">API Access Requests</span>
                <span className="ml-2 px-2 py-0.5 text-xs rounded-full bg-amber-500/20 text-amber-500">
                  {apiAccessRequests.length} pending
                </span>
              </h2>
              <div className="space-y-3">
                {apiAccessRequests.map((request) => (
                  <div
                    key={request.id}
                    className="flex items-center justify-between p-3 bg-muted/30 rounded-lg"
                  >
                    <div className="flex-1">
                      <div className="font-medium">{request.username || request.email}</div>
                      <div className="text-xs text-muted-foreground flex gap-3">
                        <span>{request.email}</span>
                        {request.discord_handle && (
                          <span>Discord: {request.discord_handle}</span>
                        )}
                        <span>
                          Requested: {request.requested_at
                            ? new Date(request.requested_at).toLocaleDateString()
                            : 'Unknown'}
                        </span>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => approveApiAccessMutation.mutate(request.id)}
                        disabled={approveApiAccessMutation.isPending}
                        className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded bg-emerald-500/20 text-emerald-500 hover:bg-emerald-500/30 transition-colors disabled:opacity-50"
                      >
                        <UserCheck className="w-3.5 h-3.5" />
                        Approve
                      </button>
                      <button
                        onClick={() => denyApiAccessMutation.mutate(request.id)}
                        disabled={denyApiAccessMutation.isPending}
                        className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded bg-red-500/20 text-red-500 hover:bg-red-500/30 transition-colors disabled:opacity-50"
                      >
                        <UserX className="w-3.5 h-3.5" />
                        Deny
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Traffic Analytics */}
          <div className="border rounded-lg p-4 bg-card">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Eye className="w-5 h-5" />
              Traffic & Analytics (Last 7 Days)
            </h2>

            {/* Analytics Stats Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="p-3 bg-muted/30 rounded-lg">
                <div className="text-xs text-muted-foreground mb-1">Page Views (24h)</div>
                <div className="text-2xl font-bold">{stats?.analytics?.pageviews_24h?.toLocaleString() ?? 0}</div>
              </div>
              <div className="p-3 bg-muted/30 rounded-lg">
                <div className="text-xs text-muted-foreground mb-1">Page Views (7d)</div>
                <div className="text-2xl font-bold">{stats?.analytics?.pageviews_7d?.toLocaleString() ?? 0}</div>
              </div>
              <div className="p-3 bg-muted/30 rounded-lg">
                <div className="text-xs text-muted-foreground mb-1">Unique Visitors (24h)</div>
                <div className="text-2xl font-bold">{stats?.analytics?.unique_visitors_24h?.toLocaleString() ?? 0}</div>
              </div>
              <div className="p-3 bg-muted/30 rounded-lg">
                <div className="text-xs text-muted-foreground mb-1">Unique Visitors (7d)</div>
                <div className="text-2xl font-bold">{stats?.analytics?.unique_visitors_7d?.toLocaleString() ?? 0}</div>
              </div>
            </div>

            {/* Daily Pageviews Chart */}
            {stats?.analytics?.daily_pageviews && stats.analytics.daily_pageviews.length > 0 && (
              <div className="mb-6">
                <h3 className="text-sm font-medium mb-3 text-muted-foreground">Daily Page Views</h3>
                <div className="h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={[...stats.analytics.daily_pageviews].reverse()}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                      <XAxis
                        dataKey="date"
                        tick={{ fill: '#888', fontSize: 11 }}
                        tickFormatter={(value) =>
                          new Date(value).toLocaleDateString('en-US', { weekday: 'short' })
                        }
                      />
                      <YAxis tick={{ fill: '#888', fontSize: 11 }} />
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

            {/* Top Pages & Device Breakdown */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Top Pages */}
              <div className="md:col-span-2">
                <h3 className="text-sm font-medium mb-2 text-muted-foreground">Top Pages</h3>
                <div className="space-y-1">
                  {stats?.analytics?.top_pages?.slice(0, 8).map((page, i) => (
                    <div key={page.path} className="flex items-center justify-between p-2 bg-muted/20 rounded text-sm">
                      <span className="truncate max-w-[250px] font-mono text-xs">{page.path}</span>
                      <span className="text-muted-foreground ml-2">{page.views.toLocaleString()}</span>
                    </div>
                  ))}
                  {(!stats?.analytics?.top_pages || stats.analytics.top_pages.length === 0) && (
                    <p className="text-sm text-muted-foreground text-center py-2">No page view data yet</p>
                  )}
                </div>
              </div>

              {/* Device Breakdown */}
              <div>
                <h3 className="text-sm font-medium mb-2 text-muted-foreground">Devices</h3>
                <div className="space-y-2">
                  {stats?.analytics?.device_breakdown?.map((device) => {
                    const Icon = device.device === 'mobile' ? Smartphone
                      : device.device === 'tablet' ? Tablet
                      : Monitor
                    return (
                      <div key={device.device} className="flex items-center gap-2 p-2 bg-muted/20 rounded">
                        <Icon className="w-4 h-4 text-muted-foreground" />
                        <span className="capitalize text-sm flex-1">{device.device}</span>
                        <span className="text-sm text-muted-foreground">{device.count.toLocaleString()}</span>
                      </div>
                    )
                  })}
                  {(!stats?.analytics?.device_breakdown || stats.analytics.device_breakdown.length === 0) && (
                    <p className="text-sm text-muted-foreground text-center py-2">No data</p>
                  )}
                </div>

                {/* Top Referrers */}
                {stats?.analytics?.top_referrers && stats.analytics.top_referrers.length > 0 && (
                  <div className="mt-4">
                    <h3 className="text-sm font-medium mb-2 text-muted-foreground">Top Referrers</h3>
                    <div className="space-y-1">
                      {stats.analytics.top_referrers.slice(0, 5).map((ref) => (
                        <div key={ref.referrer} className="flex items-center gap-2 p-2 bg-muted/20 rounded text-xs">
                          <Globe className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                          <span className="truncate flex-1">{ref.referrer}</span>
                          <span className="text-muted-foreground">{ref.count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Link to GA */}
            <div className="mt-4 pt-4 border-t border-border">
              <a
                href="https://analytics.google.com/analytics/web/#/p123456789/reports/intelligenthome"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-1"
              >
                <ExternalLink className="w-3 h-3" />
                View full analytics in Google Analytics
              </a>
            </div>
          </div>

          {/* Scraper Status */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Scraper Controls */}
            <div className="border rounded-lg p-4 bg-card">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Activity className="w-5 h-5" />
                Scraper Controls
              </h2>

              {activeJob ? (
                <div className="mb-4 p-3 bg-blue-500/10 border border-blue-500/30 rounded-md">
                  <div className="flex items-center gap-2 mb-2">
                    <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
                    <span className="font-medium text-blue-500">
                      Job Running: {activeJob[0]}
                    </span>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Progress: {activeJob[1].processed ?? 0} /{' '}
                    {activeJob[1].total ?? '?'} cards
                    {activeJob[1].errors ? (
                      <span className="text-red-500 ml-2">
                        ({activeJob[1].errors} errors)
                      </span>
                    ) : null}
                  </div>
                </div>
              ) : (
                <div className="mb-4 p-3 bg-green-500/10 border border-green-500/30 rounded-md">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-500" />
                    <span className="text-green-500">No jobs running</span>
                  </div>
                </div>
              )}

              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => triggerScrapeMutation.mutate()}
                  disabled={triggerScrapeMutation.isPending || !!activeJob}
                  className="px-4 py-2 bg-primary text-primary-foreground rounded-md font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                >
                  {triggerScrapeMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                  Trigger Scheduled Scrape
                </button>
                <button
                  onClick={() =>
                    triggerBackfillMutation.mutate({
                      limit: 50,
                      force_all: false,
                    })
                  }
                  disabled={triggerBackfillMutation.isPending || !!activeJob}
                  className="px-4 py-2 bg-muted text-foreground rounded-md font-medium hover:bg-muted/80 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                >
                  {triggerBackfillMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <RefreshCw className="w-4 h-4" />
                  )}
                  Backfill (50 cards)
                </button>
              </div>

              {(triggerScrapeMutation.isError ||
                triggerBackfillMutation.isError) && (
                <div className="mt-3 p-2 bg-red-500/10 border border-red-500/30 rounded text-sm text-red-500">
                  {triggerBackfillMutation.error?.message ||
                    'A job may already be running'}
                </div>
              )}
            </div>

            {/* Scheduler Status */}
            <div className="border rounded-lg p-4 bg-card">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Clock className="w-5 h-5" />
                Scheduler Status
              </h2>

              {schedulerLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <>
                  <div className="mb-4 flex items-center gap-2">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        schedulerStatus?.running ? 'bg-green-500' : 'bg-red-500'
                      }`}
                    />
                    <span className="text-sm">
                      Scheduler:{' '}
                      {schedulerStatus?.running ? 'Running' : 'Stopped'}
                    </span>
                  </div>

                  <div className="space-y-2">
                    {schedulerStatus?.jobs.map((job) => (
                      <div
                        key={job.id}
                        className="p-2 bg-muted/50 rounded-md flex justify-between items-center"
                      >
                        <div>
                          <div className="font-medium text-sm">{job.name}</div>
                          <div className="text-xs text-muted-foreground">
                            {job.trigger}
                          </div>
                        </div>
                        <div className="text-sm text-right">
                          <div className="text-muted-foreground">Next run</div>
                          <div className="font-mono">
                            {formatRelativeTime(job.next_run)}
                          </div>
                        </div>
                      </div>
                    ))}
                    {(!schedulerStatus?.jobs ||
                      schedulerStatus.jobs.length === 0) && (
                      <p className="text-sm text-muted-foreground text-center py-4">
                        No scheduled jobs
                      </p>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Daily Volume Chart */}
          {stats?.daily_volume && stats.daily_volume.length > 0 && (
            <div className="border rounded-lg p-4 bg-card">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <BarChart3 className="w-5 h-5" />
                Daily Scrape Volume (Last 7 Days)
              </h2>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={[...stats.daily_volume].reverse()}>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="rgba(255,255,255,0.1)"
                    />
                    <XAxis
                      dataKey="date"
                      tick={{ fill: '#888', fontSize: 12 }}
                      tickFormatter={(value) =>
                        new Date(value).toLocaleDateString('en-US', {
                          weekday: 'short',
                        })
                      }
                    />
                    <YAxis tick={{ fill: '#888', fontSize: 12 }} />
                    <RechartsTooltip
                      contentStyle={{
                        backgroundColor: 'hsl(var(--card))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '6px',
                      }}
                      labelFormatter={(value) =>
                        new Date(value).toLocaleDateString()
                      }
                      formatter={(value: number) => [
                        value.toLocaleString(),
                        'Listings',
                      ]}
                    />
                    <Bar
                      dataKey="count"
                      fill="hsl(var(--primary))"
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Top Cards & Recent Jobs */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top Cards */}
            <div className="border rounded-lg p-4 bg-card">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <TrendingUp className="w-5 h-5" />
                Top Cards by Listing Count
              </h2>
              <div className="space-y-2">
                {stats?.top_cards.map((card, i) => (
                  <div
                    key={card.name}
                    className="flex items-center justify-between p-2 bg-muted/30 rounded"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground w-4">
                        {i + 1}.
                      </span>
                      <span className="text-sm font-medium truncate max-w-[200px]">
                        {card.name}
                      </span>
                    </div>
                    <span className="text-sm text-muted-foreground">
                      {card.listings.toLocaleString()} listings
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Recent Jobs */}
            <div className="border rounded-lg p-4 bg-card">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Database className="w-5 h-5" />
                Recent Scraper Jobs
              </h2>
              <div className="space-y-2">
                {stats?.scraper_jobs &&
                Object.keys(stats.scraper_jobs).length > 0 ? (
                  Object.entries(stats.scraper_jobs)
                    .slice(0, 5)
                    .map(([jobId, job]) => (
                      <div
                        key={jobId}
                        className="p-2 bg-muted/30 rounded flex justify-between items-center"
                      >
                        <div>
                          <div className="text-sm font-mono">{jobId}</div>
                          <div className="text-xs text-muted-foreground">
                            {job.processed ?? 0} processed
                            {job.errors ? `, ${job.errors} errors` : ''}
                          </div>
                        </div>
                        <span
                          className={`text-xs px-2 py-1 rounded ${
                            job.status === 'completed'
                              ? 'bg-green-500/20 text-green-500'
                              : job.status === 'running'
                                ? 'bg-blue-500/20 text-blue-500'
                                : 'bg-red-500/20 text-red-500'
                          }`}
                        >
                          {job.status}
                        </span>
                      </div>
                    ))
                ) : (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    No recent jobs
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Snapshot Info */}
          <div className="border rounded-lg p-4 bg-card">
            <h2 className="text-lg font-semibold mb-2 flex items-center gap-2">
              <Database className="w-5 h-5" />
              Market Snapshots
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <div className="text-muted-foreground">Total Snapshots</div>
                <div className="text-lg font-medium">
                  {stats?.snapshots.total?.toLocaleString() ?? 0}
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">Latest Snapshot</div>
                <div className="font-mono text-sm">
                  {formatDate(stats?.snapshots.latest ?? null)}
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">Portfolio Cards</div>
                <div className="text-lg font-medium">
                  {stats?.portfolio.total_cards?.toLocaleString() ?? 0}
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">Listings (7d)</div>
                <div className="text-lg font-medium">
                  {stats?.listings.last_7d?.toLocaleString() ?? 0}
                </div>
              </div>
            </div>
          </div>

          {/* API Key Management */}
          <APIKeyManagement />
        </div>
      )}
    </div>
  )
}

// API Key Management Component
function APIKeyManagement() {
  const queryClient = useQueryClient()

  // Fetch API keys stats
  const { data: keyStats, isLoading: statsLoading } = useQuery({
    queryKey: ['admin-api-key-stats'],
    queryFn: async () => {
      const res = await api.get('admin/api-keys/stats').json()
      return res as {
        total_keys: number
        active_keys: number
        keys_used_today: number
        total_requests_today: number
        total_requests_all_time: number
        top_users: Array<{ email: string; total_requests: number; key_count: number }>
      }
    },
  })

  // Fetch all API keys
  const { data: apiKeys, isLoading: keysLoading } = useQuery({
    queryKey: ['admin-api-keys'],
    queryFn: async () => {
      const res = await api.get('admin/api-keys').json()
      return res as Array<{
        id: number
        user_id: number
        user_email: string
        key_prefix: string
        name: string
        is_active: boolean
        rate_limit_per_minute: number
        rate_limit_per_day: number
        requests_today: number
        requests_total: number
        last_used_at: string | null
        created_at: string | null
      }>
    },
  })

  // Toggle API key mutation
  const toggleKeyMutation = useMutation({
    mutationFn: async (keyId: number) => {
      await api.put(`admin/api-keys/${keyId}/toggle`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-api-keys'] })
      queryClient.invalidateQueries({ queryKey: ['admin-api-key-stats'] })
    },
  })

  // Delete API key mutation
  const deleteKeyMutation = useMutation({
    mutationFn: async (keyId: number) => {
      await api.delete(`admin/api-keys/${keyId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-api-keys'] })
      queryClient.invalidateQueries({ queryKey: ['admin-api-key-stats'] })
    },
  })

  // Reset daily counts mutation
  const resetDailyMutation = useMutation({
    mutationFn: async () => {
      await api.post('admin/api-keys/reset-daily')
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-api-keys'] })
      queryClient.invalidateQueries({ queryKey: ['admin-api-key-stats'] })
    },
  })

  return (
    <div className="border rounded-lg p-4 bg-card">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Key className="w-5 h-5" />
          API Key Management
        </h2>
        <div className="flex gap-2">
          <Link
            to="/api"
            className="text-xs bg-primary/20 text-primary px-3 py-1.5 rounded hover:bg-primary/30 transition-colors flex items-center gap-1"
          >
            <ExternalLink className="w-3 h-3" />
            API Docs
          </Link>
          <button
            onClick={() => {
              if (confirm('Reset daily request counts for all API keys?')) {
                resetDailyMutation.mutate()
              }
            }}
            className="text-xs bg-amber-500/20 text-amber-400 px-3 py-1.5 rounded hover:bg-amber-500/30 transition-colors"
          >
            Reset Daily Counts
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      {statsLoading ? (
        <div className="text-center py-4 text-muted-foreground">Loading stats...</div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
          <div className="bg-muted/30 rounded p-3">
            <div className="text-xs text-muted-foreground">Total Keys</div>
            <div className="text-xl font-bold">{keyStats?.total_keys ?? 0}</div>
          </div>
          <div className="bg-muted/30 rounded p-3">
            <div className="text-xs text-muted-foreground">Active Keys</div>
            <div className="text-xl font-bold text-emerald-500">{keyStats?.active_keys ?? 0}</div>
          </div>
          <div className="bg-muted/30 rounded p-3">
            <div className="text-xs text-muted-foreground">Used Today</div>
            <div className="text-xl font-bold text-blue-500">{keyStats?.keys_used_today ?? 0}</div>
          </div>
          <div className="bg-muted/30 rounded p-3">
            <div className="text-xs text-muted-foreground">Requests Today</div>
            <div className="text-xl font-bold">{keyStats?.total_requests_today?.toLocaleString() ?? 0}</div>
          </div>
          <div className="bg-muted/30 rounded p-3">
            <div className="text-xs text-muted-foreground">Total Requests</div>
            <div className="text-xl font-bold">{keyStats?.total_requests_all_time?.toLocaleString() ?? 0}</div>
          </div>
        </div>
      )}

      {/* Top Users */}
      {keyStats?.top_users && keyStats.top_users.length > 0 && (
        <div className="mb-4">
          <h3 className="text-xs font-bold uppercase text-muted-foreground mb-2">Top API Users</h3>
          <div className="flex flex-wrap gap-2">
            {keyStats.top_users.slice(0, 5).map((user) => (
              <span key={user.email} className="text-xs bg-muted/50 px-2 py-1 rounded">
                {user.email.split('@')[0]} ({user.total_requests.toLocaleString()} req)
              </span>
            ))}
          </div>
        </div>
      )}

      {/* API Keys Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left">
              <th className="pb-2 font-medium text-muted-foreground">User</th>
              <th className="pb-2 font-medium text-muted-foreground">Key</th>
              <th className="pb-2 font-medium text-muted-foreground">Status</th>
              <th className="pb-2 font-medium text-muted-foreground">Today</th>
              <th className="pb-2 font-medium text-muted-foreground">Total</th>
              <th className="pb-2 font-medium text-muted-foreground">Limits</th>
              <th className="pb-2 font-medium text-muted-foreground">Actions</th>
            </tr>
          </thead>
          <tbody>
            {keysLoading ? (
              <tr>
                <td colSpan={7} className="py-4 text-center text-muted-foreground">
                  Loading API keys...
                </td>
              </tr>
            ) : !apiKeys?.length ? (
              <tr>
                <td colSpan={7} className="py-4 text-center text-muted-foreground">
                  No API keys created yet
                </td>
              </tr>
            ) : (
              apiKeys.map((key) => (
                <tr key={key.id} className="border-b border-border/50">
                  <td className="py-2">
                    <div className="font-medium">{key.user_email.split('@')[0]}</div>
                    <div className="text-xs text-muted-foreground">{key.name}</div>
                  </td>
                  <td className="py-2 font-mono text-xs">{key.key_prefix}...</td>
                  <td className="py-2">
                    <span
                      className={`text-xs px-2 py-0.5 rounded ${
                        key.is_active
                          ? 'bg-emerald-500/20 text-emerald-400'
                          : 'bg-red-500/20 text-red-400'
                      }`}
                    >
                      {key.is_active ? 'Active' : 'Disabled'}
                    </span>
                  </td>
                  <td className="py-2">{key.requests_today.toLocaleString()}</td>
                  <td className="py-2">{key.requests_total.toLocaleString()}</td>
                  <td className="py-2 text-xs text-muted-foreground">
                    {key.rate_limit_per_minute}/min, {key.rate_limit_per_day}/day
                  </td>
                  <td className="py-2">
                    <div className="flex gap-1">
                      <button
                        onClick={() => toggleKeyMutation.mutate(key.id)}
                        className={`p-1.5 rounded transition-colors ${
                          key.is_active
                            ? 'text-amber-400 hover:bg-amber-500/20'
                            : 'text-emerald-400 hover:bg-emerald-500/20'
                        }`}
                        title={key.is_active ? 'Disable' : 'Enable'}
                      >
                        <Shield className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => {
                          if (confirm(`Delete API key ${key.key_prefix}...?`)) {
                            deleteKeyMutation.mutate(key.id)
                          }
                        }}
                        className="p-1.5 text-red-400 hover:bg-red-500/20 rounded transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function StatCard({
  icon: Icon,
  label,
  value,
  subtext,
}: {
  icon: React.ElementType
  label: string
  value: number | string
  subtext?: string
}) {
  return (
    <div className="border rounded-lg p-3 bg-card">
      <div className="flex items-center gap-2 mb-1">
        <Icon className="w-4 h-4 text-muted-foreground" />
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <div className="text-xl font-bold">
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
      {subtext && (
        <div className="text-xs text-muted-foreground mt-1">{subtext}</div>
      )}
    </div>
  )
}
