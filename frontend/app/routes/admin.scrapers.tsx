import { createFileRoute } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../utils/auth'
import {
  Activity,
  Clock,
  Play,
  RefreshCw,
  CheckCircle,
  Loader2,
  Database,
  AlertTriangle,
} from 'lucide-react'

export const Route = createFileRoute('/admin/scrapers')({
  component: AdminScrapers,
})

interface AdminStats {
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

function AdminScrapers() {
  const queryClient = useQueryClient()

  const { data: stats, isLoading, refetch } = useQuery<AdminStats>({
    queryKey: ['admin-stats'],
    queryFn: async () => {
      return api.get('admin/stats').json<AdminStats>()
    },
    refetchInterval: 10000, // More frequent for scrapers
  })

  const { data: schedulerStatus, refetch: refetchScheduler } = useQuery<SchedulerStatus>({
    queryKey: ['scheduler-status'],
    queryFn: async () => {
      return api.get('admin/scheduler/status').json<SchedulerStatus>()
    },
    refetchInterval: 10000,
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
    ? Object.entries(stats.scraper_jobs).find(([_, job]) => job.status === 'running')
    : null

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Activity className="w-6 h-6" />
            Scrapers
          </h1>
          <p className="text-sm text-muted-foreground">
            Scraper controls and job management
          </p>
        </div>
        <button
          onClick={() => {
            refetch()
            refetchScheduler()
          }}
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
          {/* Current Status */}
          {activeJob ? (
            <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
                <span className="font-semibold text-blue-500">Job Running: {activeJob[0]}</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-3">
                <div>
                  <div className="text-xs text-muted-foreground">Progress</div>
                  <div className="font-mono">
                    {activeJob[1].processed ?? 0} / {activeJob[1].total ?? '?'}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Errors</div>
                  <div className={activeJob[1].errors ? 'text-red-500 font-medium' : ''}>
                    {activeJob[1].errors ?? 0}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Started</div>
                  <div className="font-mono text-xs">
                    {activeJob[1].started ? new Date(activeJob[1].started).toLocaleTimeString() : '-'}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Status</div>
                  <div className="text-blue-500 font-medium">{activeJob[1].status}</div>
                </div>
              </div>
              {activeJob[1].total && activeJob[1].processed && (
                <div className="mt-3">
                  <div className="h-2 bg-blue-500/20 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500 transition-all"
                      style={{ width: `${(activeJob[1].processed / activeJob[1].total) * 100}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="p-4 bg-brand-400/10 border border-brand-400/30 rounded-lg">
              <div className="flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-brand-400" />
                <span className="font-medium text-brand-400">System Idle</span>
                <span className="text-sm text-muted-foreground ml-2">No jobs currently running</span>
              </div>
            </div>
          )}

          {/* Controls */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Scraper Controls */}
            <div className="border rounded-lg p-4 bg-card">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Play className="w-5 h-5" />
                Manual Controls
              </h2>
              <div className="space-y-3">
                <button
                  onClick={() => triggerScrapeMutation.mutate()}
                  disabled={triggerScrapeMutation.isPending || !!activeJob}
                  className="w-full px-4 py-3 bg-primary text-primary-foreground rounded-md font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                >
                  {triggerScrapeMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                  Trigger Scheduled Scrape
                </button>
                <button
                  onClick={() => triggerBackfillMutation.mutate({ limit: 50, force_all: false })}
                  disabled={triggerBackfillMutation.isPending || !!activeJob}
                  className="w-full px-4 py-3 bg-muted text-foreground rounded-md font-medium hover:bg-muted/80 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                >
                  {triggerBackfillMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <RefreshCw className="w-4 h-4" />
                  )}
                  Backfill (50 cards)
                </button>
                <button
                  onClick={() => triggerBackfillMutation.mutate({ limit: 100, force_all: true })}
                  disabled={triggerBackfillMutation.isPending || !!activeJob}
                  className="w-full px-4 py-3 bg-amber-500/20 text-amber-400 rounded-md font-medium hover:bg-amber-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                >
                  {triggerBackfillMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <AlertTriangle className="w-4 h-4" />
                  )}
                  Force Backfill All (100 cards)
                </button>
              </div>

              {(triggerScrapeMutation.isError || triggerBackfillMutation.isError) && (
                <div className="mt-3 p-2 bg-red-500/10 border border-red-500/30 rounded text-sm text-red-500">
                  {triggerBackfillMutation.error?.message || 'A job may already be running'}
                </div>
              )}
            </div>

            {/* Scheduler Status */}
            <div className="border rounded-lg p-4 bg-card">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Clock className="w-5 h-5" />
                Scheduler
                <span className={`ml-auto text-xs px-2 py-0.5 rounded ${
                  schedulerStatus?.running ? 'bg-brand-400/20 text-brand-400' : 'bg-red-500/20 text-red-500'
                }`}>
                  {schedulerStatus?.running ? 'Running' : 'Stopped'}
                </span>
              </h2>

              <div className="space-y-2">
                {schedulerStatus?.jobs?.map((job) => (
                  <div
                    key={job.id}
                    className="p-3 bg-muted/30 rounded-lg flex justify-between items-center"
                  >
                    <div>
                      <div className="font-medium text-sm">{job.name}</div>
                      <div className="text-xs text-muted-foreground font-mono">{job.trigger}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-muted-foreground">Next run</div>
                      <div className="font-mono text-sm font-medium">
                        {formatRelativeTime(job.next_run)}
                      </div>
                    </div>
                  </div>
                ))}
                {(!schedulerStatus?.jobs || schedulerStatus.jobs.length === 0) && (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    No scheduled jobs
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Recent Jobs */}
          <div className="border rounded-lg p-4 bg-card">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Database className="w-5 h-5" />
              Recent Jobs
            </h2>
            <div className="space-y-2">
              {stats?.scraper_jobs && Object.keys(stats.scraper_jobs).length > 0 ? (
                Object.entries(stats.scraper_jobs)
                  .slice(0, 10)
                  .map(([jobId, job]) => (
                    <div
                      key={jobId}
                      className="p-3 bg-muted/30 rounded-lg grid grid-cols-2 md:grid-cols-5 gap-3 items-center"
                    >
                      <div>
                        <div className="text-xs text-muted-foreground">Job ID</div>
                        <div className="font-mono text-sm truncate">{jobId}</div>
                      </div>
                      <div>
                        <div className="text-xs text-muted-foreground">Status</div>
                        <span className={`text-xs px-2 py-0.5 rounded ${
                          job.status === 'completed'
                            ? 'bg-brand-400/20 text-brand-400'
                            : job.status === 'running'
                              ? 'bg-blue-500/20 text-blue-500'
                              : 'bg-red-500/20 text-red-500'
                        }`}>
                          {job.status}
                        </span>
                      </div>
                      <div>
                        <div className="text-xs text-muted-foreground">Processed</div>
                        <div className="font-medium">{job.processed ?? 0}</div>
                      </div>
                      <div>
                        <div className="text-xs text-muted-foreground">Errors</div>
                        <div className={job.errors ? 'text-red-500 font-medium' : 'text-muted-foreground'}>
                          {job.errors ?? 0}
                        </div>
                      </div>
                      <div className="hidden md:block">
                        <div className="text-xs text-muted-foreground">Finished</div>
                        <div className="font-mono text-xs">
                          {job.finished ? new Date(job.finished).toLocaleString() : '-'}
                        </div>
                      </div>
                    </div>
                  ))
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No recent jobs
                </p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
