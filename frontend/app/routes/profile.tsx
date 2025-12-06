import { createRoute, Link, redirect } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, auth } from '../utils/auth'
import { analytics } from '~/services/analytics'
import { Route as rootRoute } from './__root'
import { ArrowLeft, User, Save, Server, Shield } from 'lucide-react'
import { useState, useEffect } from 'react'

type UserProfile = {
    id: number
    email: string
    username?: string
    discord_handle?: string
    bio?: string
    is_superuser: boolean
    created_at: string
}

export const Route = createRoute({
  getParentRoute: () => rootRoute,
  path: '/profile',
  component: Profile,
  beforeLoad: () => {
      if (typeof window !== 'undefined' && !auth.isAuthenticated()) {
          throw redirect({ to: '/login' })
      }
  }
})

function Profile() {
  const queryClient = useQueryClient()
  const [formData, setFormData] = useState({
      username: '',
      discord_handle: '',
      bio: ''
  })

  // Fetch User Profile
  const { data: user, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const data = await api.get('users/me').json<UserProfile>()
      return data
    }
  })

  // Track profile access
  useEffect(() => {
    analytics.trackProfileAccess()
  }, [])

  // Update local state when data is loaded
  useEffect(() => {
      if (user) {
          setFormData({
              username: user.username || '',
              discord_handle: user.discord_handle || '',
              bio: user.bio || ''
          })
      }
  }, [user])

  // Update Mutation
  const updateMutation = useMutation({
      mutationFn: async (data: typeof formData) => {
          await api.put('users/me', { json: data })
      },
      onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ['me'] })
          alert('Profile updated successfully!')
      },
      onError: () => {
          alert('Failed to update profile.')
      }
  })

  const handleSubmit = (e: React.FormEvent) => {
      e.preventDefault()
      updateMutation.mutate(formData)
  }

  if (isLoading) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-background text-foreground font-mono">
            <div className="text-center animate-pulse">
                <div className="text-xl uppercase tracking-widest mb-2">Loading Profile</div>
            </div>
        </div>
      )
  }

  return (
    <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center p-4">
        <div className="w-full max-w-4xl">
            {/* Header */}
            <div className="mb-6 flex items-center gap-4">
                <Link to="/" className="flex items-center justify-center w-8 h-8 border border-border rounded hover:bg-muted/50 transition-colors">
                    <ArrowLeft className="w-4 h-4 text-muted-foreground" />
                </Link>
                <h1 className="text-2xl font-bold uppercase tracking-tight">User Profile</h1>
            </div>

            <div className="border rounded-lg overflow-hidden bg-card">
                <div className="grid grid-cols-1 lg:grid-cols-2">
                    {/* Left Column: Avatar & Info */}
                    <div className="p-6 lg:p-8 flex flex-col items-center justify-center border-b lg:border-b-0 lg:border-r border-border bg-muted/30">
                        <div className="w-24 h-24 bg-muted rounded-full mb-4 flex items-center justify-center border-2 border-border">
                            <User className="w-10 h-10 text-muted-foreground" />
                        </div>
                        <h2 className="text-lg font-bold mb-1 text-center break-all px-2">{user?.email}</h2>
                        <div className="text-xs text-muted-foreground uppercase mb-4">Member since {new Date(user?.created_at || '').toLocaleDateString()}</div>

                        <div className="flex flex-wrap gap-2 justify-center">
                            {user?.is_superuser && (
                                <span className="bg-red-900/20 text-red-500 border border-red-900 px-2 py-1 rounded text-[10px] uppercase font-bold flex items-center gap-1">
                                    <Shield className="w-3 h-3" /> Admin
                                </span>
                            )}
                            <span className="bg-emerald-900/20 text-emerald-500 border border-emerald-900 px-2 py-1 rounded text-[10px] uppercase font-bold">
                                Pro Tier
                            </span>
                        </div>
                    </div>

                    {/* Right Column: Form */}
                    <div className="p-6 lg:p-8">
                        <form onSubmit={handleSubmit} className="space-y-6">
                            <div>
                                <h3 className="text-sm font-bold uppercase tracking-widest mb-6 border-b border-border pb-2">Personal Details</h3>

                                <div className="grid gap-4">
                                    <div>
                                        <label className="block text-xs uppercase font-bold text-muted-foreground mb-2">Username</label>
                                        <input
                                            type="text"
                                            className="w-full bg-muted/50 border border-border rounded px-3 py-2 text-sm focus:outline-none focus:border-primary"
                                            placeholder="Enter username"
                                            value={formData.username}
                                            onChange={(e) => setFormData({...formData, username: e.target.value})}
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs uppercase font-bold text-muted-foreground mb-2">Discord Handle</label>
                                        <input
                                            type="text"
                                            className="w-full bg-muted/50 border border-border rounded px-3 py-2 text-sm focus:outline-none focus:border-primary"
                                            placeholder="username#0000"
                                            value={formData.discord_handle}
                                            onChange={(e) => setFormData({...formData, discord_handle: e.target.value})}
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs uppercase font-bold text-muted-foreground mb-2">Bio</label>
                                        <textarea
                                            className="w-full bg-muted/50 border border-border rounded px-3 py-2 text-sm focus:outline-none focus:border-primary h-24 resize-none"
                                            placeholder="Tell us about your collection..."
                                            value={formData.bio}
                                            onChange={(e) => setFormData({...formData, bio: e.target.value})}
                                        />
                                    </div>
                                </div>
                            </div>

                            <div className="flex justify-end pt-4 border-t border-border">
                                <button
                                    type="submit"
                                    disabled={updateMutation.isPending}
                                    className="bg-primary text-primary-foreground px-6 py-2 rounded text-xs uppercase font-bold hover:bg-primary/90 transition-colors flex items-center gap-2 disabled:opacity-50"
                                >
                                    <Save className="w-4 h-4" />
                                    {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
  )
}
