import { createFileRoute } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../utils/auth'
import {
  Users,
  Loader2,
  Code,
  UserCheck,
  UserX,
  RefreshCw,
  Shield,
  Mail,
  Calendar,
  Clock,
} from 'lucide-react'

export const Route = createFileRoute('/admin/users')({
  component: AdminUsers,
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
}

interface APIAccessRequest {
  id: number
  email: string
  username: string | null
  discord_handle: string | null
  requested_at: string | null
  created_at: string | null
}

function AdminUsers() {
  const queryClient = useQueryClient()

  const { data: stats, isLoading, refetch } = useQuery<AdminStats>({
    queryKey: ['admin-stats'],
    queryFn: async () => {
      return api.get('admin/stats').json<AdminStats>()
    },
    refetchInterval: 30000,
  })

  const { data: apiAccessRequests } = useQuery<APIAccessRequest[]>({
    queryKey: ['api-access-requests'],
    queryFn: async () => {
      return api.get('billing/api-access/requests').json<APIAccessRequest[]>()
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

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Users className="w-6 h-6" />
            Users
          </h1>
          <p className="text-sm text-muted-foreground">
            Manage users and access requests
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

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="border rounded-lg p-4 bg-card">
          <div className="text-xs text-muted-foreground mb-1">Total Users</div>
          <div className="text-2xl font-bold">{stats?.users.total ?? 0}</div>
        </div>
        <div className="border rounded-lg p-4 bg-card">
          <div className="text-xs text-muted-foreground mb-1">Active Today</div>
          <div className="text-2xl font-bold text-brand-400">{stats?.users.active_24h ?? 0}</div>
        </div>
        <div className="border rounded-lg p-4 bg-card">
          <div className="text-xs text-muted-foreground mb-1">Admins</div>
          <div className="text-2xl font-bold text-primary">
            {stats?.users.list?.filter(u => u.is_superuser).length ?? 0}
          </div>
        </div>
        <div className="border rounded-lg p-4 bg-card border-amber-500/50">
          <div className="text-xs text-muted-foreground mb-1">API Requests</div>
          <div className="text-2xl font-bold text-amber-500">{apiAccessRequests?.length ?? 0}</div>
        </div>
      </div>

      {/* API Access Requests */}
      {apiAccessRequests && apiAccessRequests.length > 0 && (
        <div className="border rounded-lg p-4 bg-card border-amber-500/50">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Code className="w-5 h-5 text-amber-500" />
            <span className="text-amber-500">Pending API Access Requests</span>
            <span className="ml-2 px-2 py-0.5 text-xs rounded-full bg-amber-500/20 text-amber-500">
              {apiAccessRequests.length}
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
                  <div className="text-xs text-muted-foreground flex flex-wrap gap-3">
                    <span className="flex items-center gap-1">
                      <Mail className="w-3 h-3" />
                      {request.email}
                    </span>
                    {request.discord_handle && (
                      <span>Discord: {request.discord_handle}</span>
                    )}
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {request.requested_at
                        ? new Date(request.requested_at).toLocaleDateString()
                        : 'Unknown'}
                    </span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => approveApiAccessMutation.mutate(request.id)}
                    disabled={approveApiAccessMutation.isPending}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded bg-brand-300/20 text-brand-300 hover:bg-brand-300/30 transition-colors disabled:opacity-50"
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

      {/* Users List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="border rounded-lg bg-card overflow-hidden">
          <div className="p-4 border-b border-border">
            <h2 className="font-semibold">All Users</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="text-left py-3 px-4 font-medium text-muted-foreground">User</th>
                  <th className="text-left py-3 px-4 font-medium text-muted-foreground hidden md:table-cell">Discord</th>
                  <th className="text-left py-3 px-4 font-medium text-muted-foreground">Role</th>
                  <th className="text-left py-3 px-4 font-medium text-muted-foreground hidden md:table-cell">Joined</th>
                  <th className="text-left py-3 px-4 font-medium text-muted-foreground">Last Login</th>
                </tr>
              </thead>
              <tbody>
                {stats?.users.list.map((user) => (
                  <tr key={user.id} className="border-b border-border/50 hover:bg-muted/20">
                    <td className="py-3 px-4">
                      <div className="font-medium">{user.username || user.email.split('@')[0]}</div>
                      <div className="text-xs text-muted-foreground">{user.email}</div>
                    </td>
                    <td className="py-3 px-4 text-muted-foreground hidden md:table-cell">
                      {user.discord_handle || '-'}
                    </td>
                    <td className="py-3 px-4">
                      {user.is_superuser ? (
                        <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded bg-primary/20 text-primary w-fit">
                          <Shield className="w-3 h-3" />
                          Admin
                        </span>
                      ) : (
                        <span className="text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">User</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-muted-foreground text-xs hidden md:table-cell">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {user.created_at
                          ? new Date(user.created_at).toLocaleDateString()
                          : '-'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-muted-foreground text-xs">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {user.last_login
                          ? new Date(user.last_login).toLocaleDateString()
                          : 'Never'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
