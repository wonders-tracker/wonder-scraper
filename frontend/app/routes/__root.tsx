import { Outlet, createRootRoute, Link, useNavigate, redirect, useLocation } from '@tanstack/react-router'
import { LayoutDashboard, LineChart, Wallet, User, Server, LogOut, Menu, X, Shield, ChevronDown, Settings, Sparkles, Newspaper } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, auth } from '../utils/auth'
import { useState, useMemo, useRef, useEffect } from 'react'
import { usePageTracking } from '../hooks/usePageTracking'
import Marquee from '../components/ui/marquee'
import { Tooltip } from '../components/ui/tooltip'
import { Analytics } from '@vercel/analytics/react'
import { TimePeriodProvider, useTimePeriod } from '../context/TimePeriodContext'
import { UserProvider } from '../context/UserContext'

type UserProfile = {
    id: number
    email: string
    is_superuser: boolean
    onboarding_completed: boolean
    subscription_tier: string
    is_pro: boolean
}

type Card = {
  id: number
  slug?: string
  name: string
  latest_price?: number
  // New field names
  volume?: number
  price_delta?: number
  // Deprecated (backwards compat)
  volume_30d?: number
  price_delta_24h?: number
}

// Paths that should skip onboarding check
const SKIP_ONBOARDING_PATHS = ['/welcome', '/login', '/signup', '/auth/callback', '/forgot-password', '/reset-password']

export const Route = createRootRoute({
  component: RootComponent,
  beforeLoad: async ({ location }) => {
    // Skip onboarding check for auth-related pages
    if (SKIP_ONBOARDING_PATHS.some(path => location.pathname.startsWith(path))) {
      return
    }

    // Check if user has a token
    if (typeof window === 'undefined') return
    const token = localStorage.getItem('token')
    if (!token) return

    // Fetch user profile to check onboarding status
    const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'}/auth/me`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    })
    if (!response.ok) {
      if (response.status === 401) {
        localStorage.removeItem('token')
      }
      return
    }
    const user = await response.json()
    // Check if onboarding is incomplete: either flag is false OR username is empty
    const needsOnboarding = user && (user.onboarding_completed === false || !user.username)
    console.log('[onboarding check] user:', user?.email, 'onboarding_completed:', user?.onboarding_completed, 'username:', user?.username, 'needsOnboarding:', needsOnboarding)
    if (needsOnboarding) {
      console.log('[onboarding check] redirecting to /welcome')
      throw redirect({ to: '/welcome' })
    }
  },
})

// User profile dropdown component - positioned relative to avoid portal issues in sticky header
function UserDropdown({ user }: { user: UserProfile }) {
  const [open, setOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside)
      return () => document.removeEventListener("mousedown", handleClickOutside)
    }
  }, [open])

  // Close on escape
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false)
    }
    if (open) {
      document.addEventListener("keydown", handleEscape)
      return () => document.removeEventListener("keydown", handleEscape)
    }
  }, [open])

  return (
    <div ref={dropdownRef} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-2 py-1.5 text-xs font-bold uppercase rounded hover:bg-muted transition-colors"
      >
        <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center">
          <User className="w-3.5 h-3.5 text-primary" />
        </div>
        <span className="hidden sm:block max-w-[100px] truncate">{user.email.split('@')[0]}</span>
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-48 rounded-md border bg-popover shadow-lg z-[100]">
          <div className="p-2 border-b">
            <div className="text-xs font-medium truncate">{user.email}</div>
            <div className="text-[10px] text-muted-foreground">
              {user.is_superuser ? 'Administrator' : 'Member'}
            </div>
          </div>
          <div className="p-1">
            <Link
              to="/profile"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 px-2 py-1.5 text-sm rounded hover:bg-muted transition-colors w-full"
            >
              <Settings className="w-3.5 h-3.5" />
              <span>Settings</span>
            </Link>
            <button
              onClick={() => {
                setOpen(false)
                auth.logout()
              }}
              className="flex items-center gap-2 px-2 py-1.5 text-sm rounded hover:bg-red-500/10 text-red-500 transition-colors w-full"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Logout</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function RootComponent() {
  const navigate = useNavigate()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  return (
    <TimePeriodProvider>
      <RootLayout navigate={navigate} mobileMenuOpen={mobileMenuOpen} setMobileMenuOpen={setMobileMenuOpen} />
    </TimePeriodProvider>
  )
}

function RootLayout({ navigate, mobileMenuOpen, setMobileMenuOpen }: { navigate: any, mobileMenuOpen: boolean, setMobileMenuOpen: (v: boolean) => void }) {
  const { timePeriod } = useTimePeriod()
  const location = useLocation()

  // Check if we're on a docs page - these have their own layout
  const isDocsPage = location.pathname.startsWith('/docs')

  // Track page views for internal analytics
  usePageTracking()

  // React Query client for cache invalidation
  const queryClient = useQueryClient()

  // Reactive auth state - listens for auth-change events from login/logout

  // Listen for auth changes (login/logout from same tab or other tabs)
  useEffect(() => {
    const handleAuthChange = async () => {
      await queryClient.invalidateQueries({ queryKey: ['me'] })
      const hasToken = typeof window !== 'undefined' && !!localStorage.getItem('token')
      if (!hasToken) {
        queryClient.setQueryData(['me'], null)
      }
    }
    // Custom event for same-tab auth changes
    window.addEventListener('auth-change', handleAuthChange)
    // Storage event for cross-tab auth changes
    window.addEventListener('storage', handleAuthChange)
    return () => {
      window.removeEventListener('auth-change', handleAuthChange)
      window.removeEventListener('storage', handleAuthChange)
    }
  }, [queryClient])

  const { data: user, isLoading: userLoading } = useQuery({
      queryKey: ['me'],
      queryFn: async () => {
          try {
              return await api.get('auth/me').json<UserProfile>()
          } catch {
              // If API fails (e.g. 401), clear local token so app knows we are logged out
              // This prevents redirect loops where localStorage has token but API rejects it
              localStorage.removeItem('token')
              return null
          }
      },
      retry: false,
      staleTime: 5 * 60 * 1000, // 5 minutes - onboarding check is in beforeLoad now
  })

  // Note: Onboarding redirect is handled in beforeLoad at the route level

  // Fetch cards for marquee ticker - uses shared time period
  // Uses same query key as dashboard so data is shared/cached
  // slim=true reduces payload by ~50% for faster loading
  const { data: cards = [] } = useQuery({
      queryKey: ['cards', timePeriod, 'all'], // Same key as dashboard with productType='all'
      queryFn: async () => {
          return await api.get(`cards?limit=500&time_period=${timePeriod}&slim=true`).json<Card[]>()
      },
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 30 * 60 * 1000, // 30 minutes cache
  })

  // Helper to get delta with fallback
  const getDelta = (c: Card) => c.price_delta ?? c.price_delta_24h ?? 0
  const getVolume = (c: Card) => c.volume ?? c.volume_30d ?? 0

  const topGainers = useMemo(() => [...cards].filter(c => getDelta(c) > 0).sort((a, b) => getDelta(b) - getDelta(a)).slice(0, 5), [cards])
  const topLosers = useMemo(() => [...cards].filter(c => getDelta(c) < 0).sort((a, b) => getDelta(a) - getDelta(b)).slice(0, 3), [cards])
  const topVolume = useMemo(() => [...cards].sort((a, b) => getVolume(b) - getVolume(a)).slice(0, 8), [cards])
  const marketMetrics = useMemo(() => {
      const totalVolume = cards.reduce((acc, c) => acc + getVolume(c), 0)
      const avgVelocity = cards.length > 0 ? totalVolume / cards.length : 0
      return { totalVolume, avgVelocity }
  }, [cards])

  // For docs pages, render just the outlet with minimal wrapper
  if (isDocsPage) {
    return (
      <UserProvider user={user ?? null} isLoading={userLoading}>
        <>
          <Analytics />
          <div className="min-h-screen bg-background text-foreground antialiased font-mono">
            <Outlet />
          </div>
        </>
      </UserProvider>
    )
  }

  return (
    <UserProvider user={user ?? null} isLoading={userLoading}>
      <>
      {/* Vercel Analytics */}
      <Analytics />

      <div className="min-h-screen bg-background text-foreground antialiased font-mono flex flex-col">
        {/* Upgrade Banner for non-pro users */}
        {user && !user.is_pro && (
          <div className="bg-[#7dd3a8] text-gray-900 py-1.5 px-4 text-center text-xs font-bold flex items-center justify-center gap-2">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Unlock Pro features: Advanced analytics, API access, and more</span>
            <Link
              to="/upgrade"
              className="ml-2 bg-gray-900/20 hover:bg-gray-900/30 px-2 py-0.5 rounded text-[10px] uppercase font-bold transition-colors"
            >
              Upgrade Now
            </Link>
          </div>
        )}

        {/* Top Header Navigation */}
        <div className="h-14 border-b border-border sticky top-0 bg-background z-50 flex items-center px-4 justify-between">
          <div className="flex items-center gap-4">
            {/* Mobile Hamburger */}
            <button
              className="md:hidden p-1.5 text-muted-foreground hover:text-foreground transition-colors"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>

            <h1 className="text-lg font-bold tracking-tight uppercase flex items-center gap-2">
              WondersTracker
              <span className="text-[9px] font-normal text-muted-foreground bg-muted px-1.5 py-0.5 rounded">BETA</span>
            </h1>

            <nav className="hidden md:flex items-center gap-1">
              <Link to="/" className="flex items-center gap-2 px-3 py-1.5 text-muted-foreground hover:text-foreground rounded-md transition-colors text-xs font-bold uppercase [&.active]:text-primary [&.active]:bg-primary/5">
                <LayoutDashboard className="w-3.5 h-3.5" />
                <span>Dashboard</span>
              </Link>
              <Link to="/market" className="flex items-center gap-2 px-3 py-1.5 text-muted-foreground hover:text-foreground rounded-md transition-colors text-xs font-bold uppercase [&.active]:text-primary [&.active]:bg-primary/5">
                <LineChart className="w-3.5 h-3.5" />
                <span>Market</span>
              </Link>
              <Link to="/blog" className="flex items-center gap-2 px-3 py-1.5 text-muted-foreground hover:text-foreground rounded-md transition-colors text-xs font-bold uppercase [&.active]:text-primary [&.active]:bg-primary/5">
                <Newspaper className="w-3.5 h-3.5" />
                <span>Blog</span>
              </Link>
              <Link to="/portfolio" className="flex items-center gap-2 px-3 py-1.5 text-muted-foreground hover:text-foreground rounded-md transition-colors text-xs font-bold uppercase [&.active]:text-primary [&.active]:bg-primary/5">
                <Wallet className="w-3.5 h-3.5" />
                <span>Portfolio</span>
              </Link>
              {user && (
                <>
                  <Link to="/profile" className="flex items-center gap-2 px-3 py-1.5 text-muted-foreground hover:text-foreground rounded-md transition-colors text-xs font-bold uppercase [&.active]:text-primary [&.active]:bg-primary/5">
                    <User className="w-3.5 h-3.5" />
                    <span>Profile</span>
                  </Link>
                  {user.is_superuser && (
                    <Link to={"/admin" as any} className="flex items-center gap-2 px-3 py-1.5 text-muted-foreground hover:text-foreground rounded-md transition-colors text-xs font-bold uppercase [&.active]:text-primary [&.active]:bg-primary/5">
                      <Shield className="w-3.5 h-3.5" />
                      <span>Admin</span>
                    </Link>
                  )}
                </>
              )}
            </nav>
          </div>

          <div className="flex items-center gap-4">
            {/* System Status */}
            <div className="hidden md:flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-brand-400 animate-pulse"></span>
              <span className="text-[9px] text-muted-foreground uppercase font-bold">System Online</span>
            </div>

            {/* Admin Quick Links */}
            {user?.is_superuser && (
              <div className="hidden md:flex items-center gap-2 border-r border-border pr-4 mr-2">
                <Tooltip content="Server Health">
                    <Link to={"/admin" as any} className="text-muted-foreground hover:text-foreground transition-colors">
                      <Server className="w-3.5 h-3.5" />
                    </Link>
                </Tooltip>
              </div>
            )}

            {user ? (
              <div className="relative">
                <UserDropdown user={user} />
              </div>
            ) : (
              <Link to="/login" className="text-xs font-bold uppercase px-3 py-1.5 bg-primary text-primary-foreground rounded hover:bg-primary/90 transition-colors relative z-50">
                Login
              </Link>
            )}
          </div>
        </div>

        {/* Mobile Menu Panel */}
        {mobileMenuOpen && (
          <div className="md:hidden absolute top-14 left-0 right-0 bg-background border-b border-border z-50 shadow-lg">
            <nav className="flex flex-col p-4 gap-2">
              <Link
                to="/"
                className="flex items-center gap-3 px-3 py-2.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded-md transition-colors text-sm font-bold uppercase [&.active]:text-primary [&.active]:bg-primary/5"
                onClick={() => setMobileMenuOpen(false)}
              >
                <LayoutDashboard className="w-4 h-4" />
                <span>Dashboard</span>
              </Link>
              <Link
                to="/market"
                className="flex items-center gap-3 px-3 py-2.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded-md transition-colors text-sm font-bold uppercase [&.active]:text-primary [&.active]:bg-primary/5"
                onClick={() => setMobileMenuOpen(false)}
              >
                <LineChart className="w-4 h-4" />
                <span>Market</span>
              </Link>
              <Link
                to="/blog"
                className="flex items-center gap-3 px-3 py-2.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded-md transition-colors text-sm font-bold uppercase [&.active]:text-primary [&.active]:bg-primary/5"
                onClick={() => setMobileMenuOpen(false)}
              >
                <Newspaper className="w-4 h-4" />
                <span>Blog</span>
              </Link>
              <Link
                to="/portfolio"
                className="flex items-center gap-3 px-3 py-2.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded-md transition-colors text-sm font-bold uppercase [&.active]:text-primary [&.active]:bg-primary/5"
                onClick={() => setMobileMenuOpen(false)}
              >
                <Wallet className="w-4 h-4" />
                <span>Portfolio</span>
              </Link>
              {user && (
                <>
                  <Link
                    to="/profile"
                    className="flex items-center gap-3 px-3 py-2.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded-md transition-colors text-sm font-bold uppercase [&.active]:text-primary [&.active]:bg-primary/5"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    <User className="w-4 h-4" />
                    <span>Profile</span>
                  </Link>
                </>
              )}
              {!user && (
                <Link
                  to="/login"
                  className="flex items-center gap-3 px-3 py-2.5 bg-primary text-primary-foreground hover:bg-primary/90 rounded-md transition-colors text-sm font-bold uppercase"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  <User className="w-4 h-4" />
                  <span>Login</span>
                </Link>
              )}
              {user && (
                <>
                  {user.is_superuser && (
                    <Link
                      to={"/admin" as any}
                      className="flex items-center gap-3 px-3 py-2.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded-md transition-colors text-sm font-bold uppercase [&.active]:text-primary [&.active]:bg-primary/5"
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      <Shield className="w-4 h-4" />
                      <span>Admin</span>
                    </Link>
                  )}
                  <button
                    onClick={() => {
                      auth.logout()
                      setMobileMenuOpen(false)
                    }}
                    className="flex items-center gap-3 px-3 py-2.5 text-red-500 hover:bg-red-500/10 rounded-md transition-colors text-sm font-bold uppercase w-full text-left"
                  >
                    <LogOut className="w-4 h-4" />
                    <span>Logout</span>
                  </button>
                </>
              )}
            </nav>
          </div>
        )}

        {/* Market Pulse Marquee - Persistent across all pages */}
        <div className="border-b border-border bg-muted/10 overflow-hidden flex items-center h-8 sticky top-14 z-40">
          {/* Fixed Metrics */}
          <div className="flex items-center px-3 border-r border-border h-full bg-background/50 z-10">
            <div className="flex items-center gap-2 text-[10px] font-mono mr-3">
              <span className="text-muted-foreground uppercase">Vol:</span>
              <span className="font-bold">{marketMetrics.totalVolume}</span>
            </div>
            <div className="flex items-center gap-2 text-[10px] font-mono">
              <span className="text-muted-foreground uppercase">Vel:</span>
              <span className="font-bold text-brand-300">{Number(marketMetrics.avgVelocity).toFixed(1)}/d</span>
            </div>
          </div>

          {/* Scrolling Ticker */}
          <div className="flex-1 min-w-0">
            <Marquee pauseOnHover className="[--gap:2rem]">
              {/* Fallback if lists are empty: show top volume items */}
              {(topGainers.length === 0 && topLosers.length === 0) && topVolume.map(c => (
                <div key={`ticker-vol-${c.id}`} className="flex items-center gap-2 text-[10px] font-mono cursor-pointer hover:text-primary transition-colors whitespace-nowrap" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: String(c.id) } })}>
                  <span className="font-bold uppercase">{c.name}</span>
                  <span className="text-muted-foreground">${Number(c.latest_price).toFixed(2)}</span>
                </div>
              ))}

              {topGainers.map(c => (
                <div key={`ticker-${c.id}`} className="flex items-center gap-2 text-[10px] font-mono cursor-pointer hover:text-primary transition-colors whitespace-nowrap" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: String(c.id) } })}>
                  <span className="font-bold uppercase">{c.name}</span>
                  <span className="text-brand-300">+{getDelta(c).toFixed(1)}%</span>
                </div>
              ))}
              {topLosers.map(c => (
                <div key={`ticker-loss-${c.id}`} className="flex items-center gap-2 text-[10px] font-mono cursor-pointer hover:text-primary transition-colors whitespace-nowrap" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: String(c.id) } })}>
                  <span className="font-bold uppercase">{c.name}</span>
                  <span className="text-red-500">{getDelta(c).toFixed(1)}%</span>
                </div>
              ))}
            </Marquee>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <div className="flex-1 overflow-y-auto bg-background scrollbar-hide pb-14">
            <Outlet />
          </div>
        </div>

        {/* Footer - Fixed to bottom */}
        <footer className="border-t border-border bg-background py-3 px-4 fixed bottom-0 left-0 right-0 z-40">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-muted-foreground">
            <div className="flex items-center gap-4">
              <span className="font-bold">WondersTracker</span>
              <a
                href="https://discord.gg/Kx4fFj7V"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 hover:text-foreground transition-colors"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
                </svg>
                <span>Discord</span>
              </a>
              <Link
                to="/api"
                className="flex items-center gap-1.5 hover:text-foreground transition-colors"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 17l6-6-6-6" />
                  <path d="M12 19h8" />
                </svg>
                <span>API</span>
              </Link>
              <Link
                to="/methodology"
                className="hover:text-foreground transition-colors"
              >
                Methodology
              </Link>
            </div>
            <div className="text-[10px]">
              Not affiliated with Wonders of the First
            </div>
          </div>
        </footer>
      </div>
      </>
    </UserProvider>
  )
}
