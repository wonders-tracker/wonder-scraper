import { createFileRoute, Link } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { api } from '../utils/auth'
import {
  Users,
  Database,
  Activity,
  TrendingUp,
  Package,
  BarChart3,
  HardDrive,
  Loader2,
  AlertTriangle,
  RefreshCw,
  CheckCircle,
  Clock,
  Eye,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react'

export const Route = createFileRoute('/admin/')({
  component: AdminOverview,
})

interface AdminStats {
  users: {
    total: number
    active_24h: number
    list: Array<{
      id: number
      email: string
      username: string | null
      is_superuser: boolean
      created_at: string | null
      last_login: string | null
    }>
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
  analytics: {
    pageviews_24h: number
    unique_visitors_24h: number
  }
  scraper_jobs: Record<string, { status: string }>
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

function AdminOverview() {
  const {
    data: stats,
    isLoading,
    error,
    refetch,
  } = useQuery<AdminStats>({
    queryKey: ['admin-stats'],
    queryFn: async () => {
      return api.get('admin/stats').json<AdminStats>()
    },
    refetchInterval: 30000,
  })

  const { data: schedulerStatus } = useQuery<SchedulerStatus>({
    queryKey: ['scheduler-status'],
    queryFn: async () => {
      return api.get('admin/scheduler/status').json<SchedulerStatus>()
    },
    refetchInterval: 30000,
  })

  if (error) {
    const errorMessage = (error as any)?.response?.status === 403
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

  // Get active scraper job
  const activeJob = stats?.scraper_jobs
    ? Object.entries(stats.scraper_jobs).find(([_, job]) => job.status === 'running')
    : null

  // Get next scheduled job
  const nextJob = schedulerStatus?.jobs?.[0]
  const formatRelativeTime = (dateStr: string | null) => {
    if (!dateStr) return 'N/A'
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = date.getTime() - now.getTime()
    const diffMins = Math.round(diffMs / 60000)
    if (diffMins < 0) return 'Past due'
    if (diffMins < 60) return `${diffMins}m`
    return `${Math.round(diffMins / 60)}h`
  }

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Overview</h1>
          <p className="text-sm text-muted-foreground">System health at a glance</p>
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
          {/* Quick Status Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {/* Scraper Status */}
            <div className={`border rounded-lg p-4 ${activeJob ? 'border-blue-500/50 bg-blue-500/5' : 'border-brand-400/50 bg-brand-400/5'}`}>
              <div className="flex items-center gap-2 mb-2">
                {activeJob ? (
                  <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
                ) : (
                  <CheckCircle className="w-4 h-4 text-brand-400" />
                )}
                <span className="text-xs font-medium text-muted-foreground">Scraper</span>
              </div>
              <div className="text-lg font-bold">
                {activeJob ? 'Running' : 'Idle'}
              </div>
              {nextJob && (
                <div className="text-xs text-muted-foreground mt-1">
                  Next: {formatRelativeTime(nextJob.next_run)}
                </div>
              )}
            </div>

            {/* Scheduler Status */}
            <div className={`border rounded-lg p-4 ${schedulerStatus?.running ? 'border-brand-400/50 bg-brand-400/5' : 'border-red-500/50 bg-red-500/5'}`}>
              <div className="flex items-center gap-2 mb-2">
                <Clock className="w-4 h-4 text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground">Scheduler</span>
              </div>
              <div className="text-lg font-bold">
                {schedulerStatus?.running ? 'Active' : 'Stopped'}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {schedulerStatus?.jobs?.length ?? 0} jobs
              </div>
            </div>

            {/* Traffic Today */}
            <div className="border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Eye className="w-4 h-4 text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground">Traffic (24h)</span>
              </div>
              <div className="text-lg font-bold">
                {stats?.analytics?.pageviews_24h?.toLocaleString() ?? 0}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {stats?.analytics?.unique_visitors_24h ?? 0} visitors
              </div>
            </div>

            {/* Database Size */}
            <div className="border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <HardDrive className="w-4 h-4 text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground">Database</span>
              </div>
              <div className="text-lg font-bold">{stats?.database.size ?? 'N/A'}</div>
              <div className="text-xs text-muted-foreground mt-1">
                {stats?.snapshots.total?.toLocaleString() ?? 0} snapshots
              </div>
            </div>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            <StatCard
              icon={Users}
              label="Users"
              value={stats?.users.total ?? 0}
              subtext={`${stats?.users.active_24h ?? 0} active today`}
              trend={stats?.users.active_24h && stats.users.active_24h > 0 ? 'up' : undefined}
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
              subtext={`+${stats?.listings.last_24h ?? 0} today`}
              trend="up"
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
              icon={Database}
              label="Portfolios"
              value={stats?.portfolio.total_cards ?? 0}
              subtext="cards tracked"
            />
          </div>

          {/* Quick Links */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <QuickLinkCard
              to="/admin/users"
              icon={Users}
              title="Users"
              description={`${stats?.users.total ?? 0} total users`}
              highlight={`${stats?.users.active_24h ?? 0} active today`}
            />
            <QuickLinkCard
              to="/admin/scrapers"
              icon={Activity}
              title="Scrapers"
              description={activeJob ? 'Job running' : 'System idle'}
              highlight={nextJob ? `Next run in ${formatRelativeTime(nextJob.next_run)}` : undefined}
            />
            <QuickLinkCard
              to="/admin/analytics"
              icon={Eye}
              title="Analytics"
              description={`${stats?.analytics?.pageviews_24h?.toLocaleString() ?? 0} views today`}
              highlight={`${stats?.analytics?.unique_visitors_24h ?? 0} unique visitors`}
            />
          </div>

          {/* Recent Activity */}
          <div className="border rounded-lg p-4 bg-card">
            <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <Activity className="w-4 h-4" />
              Latest Activity
            </h2>
            <div className="space-y-2 text-sm">
              {stats?.snapshots.latest && (
                <div className="flex items-center justify-between p-2 bg-muted/30 rounded">
                  <span className="text-muted-foreground">Last snapshot</span>
                  <span className="font-mono text-xs">
                    {new Date(stats.snapshots.latest).toLocaleString()}
                  </span>
                </div>
              )}
              <div className="flex items-center justify-between p-2 bg-muted/30 rounded">
                <span className="text-muted-foreground">Listings (7 days)</span>
                <span className="font-medium">{stats?.listings.last_7d?.toLocaleString() ?? 0}</span>
              </div>
              <div className="flex items-center justify-between p-2 bg-muted/30 rounded">
                <span className="text-muted-foreground">Listings (24h)</span>
                <span className="font-medium">{stats?.listings.last_24h?.toLocaleString() ?? 0}</span>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function StatCard({
  icon: Icon,
  label,
  value,
  subtext,
  trend,
}: {
  icon: React.ElementType
  label: string
  value: number | string
  subtext?: string
  trend?: 'up' | 'down'
}) {
  return (
    <div className="border rounded-lg p-3 bg-card">
      <div className="flex items-center gap-2 mb-1">
        <Icon className="w-4 h-4 text-muted-foreground" />
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <div className="text-xl font-bold flex items-center gap-1">
        {typeof value === 'number' ? value.toLocaleString() : value}
        {trend === 'up' && <ArrowUpRight className="w-4 h-4 text-brand-400" />}
        {trend === 'down' && <ArrowDownRight className="w-4 h-4 text-red-400" />}
      </div>
      {subtext && (
        <div className="text-xs text-muted-foreground mt-1">{subtext}</div>
      )}
    </div>
  )
}

function QuickLinkCard({
  to,
  icon: Icon,
  title,
  description,
  highlight,
}: {
  to: string
  icon: React.ElementType
  title: string
  description: string
  highlight?: string
}) {
  return (
    <Link
      to={to}
      className="border rounded-lg p-4 bg-card hover:bg-muted/30 transition-colors group"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-md bg-primary/10">
            <Icon className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h3 className="font-semibold group-hover:text-primary transition-colors">{title}</h3>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
        </div>
      </div>
      {highlight && (
        <div className="mt-3 text-xs text-primary font-medium">
          {highlight}
        </div>
      )}
    </Link>
  )
}
