import { createFileRoute, Link } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../utils/auth'
import {
  Key,
  Loader2,
  RefreshCw,
  Shield,
  Trash2,
  ExternalLink,
  Zap,
  Clock,
} from 'lucide-react'

export const Route = createFileRoute('/admin/api-keys')({
  component: AdminAPIKeys,
})

interface APIKeyStats {
  total_keys: number
  active_keys: number
  keys_used_today: number
  total_requests_today: number
  total_requests_all_time: number
  top_users: Array<{ email: string; total_requests: number; key_count: number }>
}

interface APIKey {
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
}

function AdminAPIKeys() {
  const queryClient = useQueryClient()

  const { data: keyStats, isLoading: statsLoading, refetch } = useQuery<APIKeyStats>({
    queryKey: ['admin-api-key-stats'],
    queryFn: async () => {
      return api.get('admin/api-keys/stats').json<APIKeyStats>()
    },
  })

  const { data: apiKeys, isLoading: keysLoading } = useQuery<APIKey[]>({
    queryKey: ['admin-api-keys'],
    queryFn: async () => {
      return api.get('admin/api-keys').json<APIKey[]>()
    },
  })

  const toggleKeyMutation = useMutation({
    mutationFn: async (keyId: number) => {
      await api.put(`admin/api-keys/${keyId}/toggle`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-api-keys'] })
      queryClient.invalidateQueries({ queryKey: ['admin-api-key-stats'] })
    },
  })

  const deleteKeyMutation = useMutation({
    mutationFn: async (keyId: number) => {
      await api.delete(`admin/api-keys/${keyId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-api-keys'] })
      queryClient.invalidateQueries({ queryKey: ['admin-api-key-stats'] })
    },
  })

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
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Key className="w-6 h-6" />
            API Keys
          </h1>
          <p className="text-sm text-muted-foreground">
            Manage API access and rate limits
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            to="/api"
            className="text-xs bg-primary/20 text-primary px-3 py-2 rounded hover:bg-primary/30 transition-colors flex items-center gap-1"
          >
            <ExternalLink className="w-3 h-3" />
            API Docs
          </Link>
          <button
            onClick={() => refetch()}
            className="p-2 rounded-md hover:bg-muted transition-colors"
            disabled={statsLoading}
          >
            <RefreshCw className={`w-5 h-5 ${statsLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      {statsLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="bg-muted/30 rounded-lg p-4 animate-pulse h-20" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="bg-card border rounded-lg p-4">
            <div className="text-xs text-muted-foreground mb-1">Total Keys</div>
            <div className="text-2xl font-bold">{keyStats?.total_keys ?? 0}</div>
          </div>
          <div className="bg-card border rounded-lg p-4">
            <div className="text-xs text-muted-foreground mb-1">Active Keys</div>
            <div className="text-2xl font-bold text-brand-300">{keyStats?.active_keys ?? 0}</div>
          </div>
          <div className="bg-card border rounded-lg p-4">
            <div className="text-xs text-muted-foreground mb-1">Used Today</div>
            <div className="text-2xl font-bold text-blue-500">{keyStats?.keys_used_today ?? 0}</div>
          </div>
          <div className="bg-card border rounded-lg p-4">
            <div className="text-xs text-muted-foreground mb-1">Requests Today</div>
            <div className="text-2xl font-bold">{keyStats?.total_requests_today?.toLocaleString() ?? 0}</div>
          </div>
          <div className="bg-card border rounded-lg p-4">
            <div className="text-xs text-muted-foreground mb-1">Total Requests</div>
            <div className="text-2xl font-bold">{keyStats?.total_requests_all_time?.toLocaleString() ?? 0}</div>
          </div>
        </div>
      )}

      {/* Top Users */}
      {keyStats?.top_users && keyStats.top_users.length > 0 && (
        <div className="border rounded-lg p-4 bg-card">
          <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Zap className="w-4 h-4" />
            Top API Users
          </h2>
          <div className="flex flex-wrap gap-2">
            {keyStats.top_users.slice(0, 10).map((user) => (
              <div key={user.email} className="text-xs bg-muted/50 px-3 py-2 rounded-lg">
                <span className="font-medium">{user.email.split('@')[0]}</span>
                <span className="text-muted-foreground ml-2">
                  {user.total_requests.toLocaleString()} requests
                </span>
                <span className="text-muted-foreground ml-2">
                  ({user.key_count} key{user.key_count !== 1 ? 's' : ''})
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Admin Controls */}
      <div className="flex gap-2">
        <button
          onClick={() => {
            if (confirm('Reset daily request counts for all API keys?')) {
              resetDailyMutation.mutate()
            }
          }}
          disabled={resetDailyMutation.isPending}
          className="text-xs bg-amber-500/20 text-amber-400 px-4 py-2 rounded hover:bg-amber-500/30 transition-colors flex items-center gap-1"
        >
          <RefreshCw className={`w-3 h-3 ${resetDailyMutation.isPending ? 'animate-spin' : ''}`} />
          Reset Daily Counts
        </button>
      </div>

      {/* API Keys Table */}
      <div className="border rounded-lg bg-card overflow-hidden">
        <div className="p-4 border-b border-border">
          <h2 className="font-semibold">All API Keys</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/30 text-left">
                <th className="py-3 px-4 font-medium text-muted-foreground">User</th>
                <th className="py-3 px-4 font-medium text-muted-foreground">Key</th>
                <th className="py-3 px-4 font-medium text-muted-foreground">Status</th>
                <th className="py-3 px-4 font-medium text-muted-foreground">Today</th>
                <th className="py-3 px-4 font-medium text-muted-foreground hidden md:table-cell">Total</th>
                <th className="py-3 px-4 font-medium text-muted-foreground hidden lg:table-cell">Limits</th>
                <th className="py-3 px-4 font-medium text-muted-foreground hidden lg:table-cell">Last Used</th>
                <th className="py-3 px-4 font-medium text-muted-foreground">Actions</th>
              </tr>
            </thead>
            <tbody>
              {keysLoading ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-muted-foreground">
                    <Loader2 className="w-6 h-6 animate-spin mx-auto" />
                  </td>
                </tr>
              ) : !apiKeys?.length ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-muted-foreground">
                    No API keys created yet
                  </td>
                </tr>
              ) : (
                apiKeys.map((key) => (
                  <tr key={key.id} className="border-b border-border/50 hover:bg-muted/20">
                    <td className="py-3 px-4">
                      <div className="font-medium">{key.user_email.split('@')[0]}</div>
                      <div className="text-xs text-muted-foreground">{key.name}</div>
                    </td>
                    <td className="py-3 px-4 font-mono text-xs">{key.key_prefix}...</td>
                    <td className="py-3 px-4">
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        key.is_active
                          ? 'bg-brand-300/20 text-brand-300'
                          : 'bg-red-500/20 text-red-400'
                      }`}>
                        {key.is_active ? 'Active' : 'Disabled'}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-medium">{key.requests_today.toLocaleString()}</td>
                    <td className="py-3 px-4 hidden md:table-cell">{key.requests_total.toLocaleString()}</td>
                    <td className="py-3 px-4 text-xs text-muted-foreground hidden lg:table-cell">
                      {key.rate_limit_per_minute}/min, {key.rate_limit_per_day}/day
                    </td>
                    <td className="py-3 px-4 text-xs text-muted-foreground hidden lg:table-cell">
                      {key.last_used_at ? (
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {new Date(key.last_used_at).toLocaleDateString()}
                        </span>
                      ) : (
                        'Never'
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex gap-1">
                        <button
                          onClick={() => toggleKeyMutation.mutate(key.id)}
                          disabled={toggleKeyMutation.isPending}
                          className={`p-1.5 rounded transition-colors ${
                            key.is_active
                              ? 'text-amber-400 hover:bg-amber-500/20'
                              : 'text-brand-300 hover:bg-brand-300/20'
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
                          disabled={deleteKeyMutation.isPending}
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
    </div>
  )
}
