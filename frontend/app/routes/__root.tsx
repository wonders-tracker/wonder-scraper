import { Outlet, createRootRoute, Link, useNavigate } from '@tanstack/react-router'
import { LayoutDashboard, LineChart, Wallet, Settings, User, Server, LogOut, Menu, X } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api, auth } from '../utils/auth'
import { useState, useMemo } from 'react'
import Marquee from '../components/ui/marquee'
import { Analytics } from '@vercel/analytics/react'

type UserProfile = {
    id: number
    email: string
    is_superuser: boolean
}

type Card = {
  id: number
  slug?: string
  name: string
  latest_price?: number
  price_delta_24h?: number
  volume_30d?: number
}

export const Route = createRootRoute({
  component: RootComponent,
})

function RootComponent() {
  const navigate = useNavigate()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const { data: user } = useQuery({
      queryKey: ['me'],
      queryFn: async () => {
          try {
              return await api.get('users/me').json<UserProfile>()
          } catch {
              // If API fails (e.g. 401), clear local token so app knows we are logged out
              // This prevents redirect loops where localStorage has token but API rejects it
              localStorage.removeItem('token')
              return null
          }
      },
      retry: false
  })

  // Fetch cards for marquee
  const { data: cards = [] } = useQuery({
      queryKey: ['cards'],
      queryFn: async () => {
          return await api.get('cards/').json<Card[]>()
      }
  })

  const topGainers = useMemo(() => [...cards].filter(c => c.price_delta_24h && c.price_delta_24h > 0).sort((a, b) => (b.price_delta_24h || 0) - (a.price_delta_24h || 0)).slice(0, 5), [cards])
  const topLosers = useMemo(() => [...cards].filter(c => c.price_delta_24h && c.price_delta_24h < 0).sort((a, b) => (a.price_delta_24h || 0) - (b.price_delta_24h || 0)).slice(0, 3), [cards])
  const topVolume = useMemo(() => [...cards].sort((a, b) => (b.volume_30d || 0) - (a.volume_30d || 0)).slice(0, 8), [cards])
  const marketMetrics = useMemo(() => {
      const totalVolume = cards.reduce((acc, c) => acc + (c.volume_30d || 0), 0)
      const avgVelocity = cards.length > 0 ? totalVolume / cards.length : 0
      return { totalVolume, avgVelocity }
  }, [cards])

  return (
    <>
      {/* Vercel Analytics */}
      <Analytics />

      <div className="min-h-screen bg-background text-foreground antialiased font-mono flex flex-col">
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
              {user && (
                <>
                  <Link to="/portfolio" className="flex items-center gap-2 px-3 py-1.5 text-muted-foreground hover:text-foreground rounded-md transition-colors text-xs font-bold uppercase [&.active]:text-primary [&.active]:bg-primary/5">
                    <Wallet className="w-3.5 h-3.5" />
                    <span>Portfolio</span>
                  </Link>
                  <Link to="/profile" className="flex items-center gap-2 px-3 py-1.5 text-muted-foreground hover:text-foreground rounded-md transition-colors text-xs font-bold uppercase [&.active]:text-primary [&.active]:bg-primary/5">
                    <User className="w-3.5 h-3.5" />
                    <span>Profile</span>
                  </Link>
                </>
              )}
            </nav>
          </div>

          <div className="flex items-center gap-4">
            {/* System Status */}
            <div className="hidden md:flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
              <span className="text-[9px] text-muted-foreground uppercase font-bold">System Online</span>
            </div>

            {/* Admin Quick Links */}
            {user?.is_superuser && (
              <div className="hidden md:flex items-center gap-2 border-r border-border pr-4 mr-2">
                <a href="#" className="text-muted-foreground hover:text-foreground transition-colors" title="Scraper Status">
                  <Server className="w-3.5 h-3.5" />
                </a>
                <a href="#" className="text-muted-foreground hover:text-foreground transition-colors" title="Settings">
                  <Settings className="w-3.5 h-3.5" />
                </a>
              </div>
            )}

            {user ? (
              <div className="flex items-center gap-3">
                <div className="text-xs font-bold uppercase truncate max-w-[120px] hidden sm:block">{user.email}</div>
                <button onClick={() => auth.logout()} className="text-muted-foreground hover:text-red-500 transition-colors p-1" title="Logout">
                  <LogOut className="w-3.5 h-3.5" />
                </button>
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
              {user && (
                <>
                  <Link
                    to="/portfolio"
                    className="flex items-center gap-3 px-3 py-2.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded-md transition-colors text-sm font-bold uppercase [&.active]:text-primary [&.active]:bg-primary/5"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    <Wallet className="w-4 h-4" />
                    <span>Portfolio</span>
                  </Link>
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
              <span className="font-bold text-emerald-500">{Number(marketMetrics.avgVelocity).toFixed(1)}/d</span>
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
                  <span className="text-emerald-500">+{Number(c.price_delta_24h).toFixed(1)}%</span>
                </div>
              ))}
              {topLosers.map(c => (
                <div key={`ticker-loss-${c.id}`} className="flex items-center gap-2 text-[10px] font-mono cursor-pointer hover:text-primary transition-colors whitespace-nowrap" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: String(c.id) } })}>
                  <span className="font-bold uppercase">{c.name}</span>
                  <span className="text-red-500">{Number(c.price_delta_24h).toFixed(1)}%</span>
                </div>
              ))}
            </Marquee>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <div className="flex-1 overflow-y-auto bg-background scrollbar-hide">
            <Outlet />
          </div>
        </div>

        {/* Footer */}
        <footer className="border-t border-border bg-muted/30 py-4 px-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-muted-foreground">
            <div className="flex items-center gap-4">
              <span>WondersTracker</span>
              <a
                href="https://discord.gg/Kx4fFj7V"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 hover:text-foreground transition-colors"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
                </svg>
                <span>Join Discord</span>
              </a>
            </div>
            <div className="text-[10px]">
              Not affiliated with Wonders of the First
            </div>
          </div>
        </footer>
      </div>
    </>
  )
}
