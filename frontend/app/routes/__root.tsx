import { Outlet, createRootRoute, Link, useNavigate } from '@tanstack/react-router'
import { LayoutDashboard, LineChart, Wallet, Settings, User, Server, LogOut } from 'lucide-react'
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
  name: string
  latest_price?: number
  price_delta_24h?: number
  volume_24h?: number
}

export const Route = createRootRoute({
  component: RootComponent,
})

function RootComponent() {
  const navigate = useNavigate()
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
  const topVolume = useMemo(() => [...cards].sort((a, b) => (b.volume_24h || 0) - (a.volume_24h || 0)).slice(0, 8), [cards])
  const marketMetrics = useMemo(() => {
      const totalVolume = cards.reduce((acc, c) => acc + (c.volume_24h || 0), 0)
      const avgVelocity = cards.length > 0 ? totalVolume / cards.length : 0
      return { totalVolume, avgVelocity }
  }, [cards])

  return (
    <>
      {/* SEO Metadata */}
      <head>
        <title>Wonders of the First TCG Tracker | WondersTracker</title>
        <meta name="description" content="Track market prices, analyze trends, and manage your portfolio for Wonders of the First TCG/CCG. Real-time data for singles, boxes, packs, and proofs." />
        <meta name="keywords" content="Wonders of the First, WOTF, TCG tracker, CCG tracker, trading card game, market prices, card values, portfolio tracker, Existence set, collectible cards, card market analysis" />
        <meta property="og:title" content="Wonders of the First TCG Tracker | WondersTracker" />
        <meta property="og:description" content="Track market prices and analyze trends for Wonders of the First TCG" />
        <meta property="og:type" content="website" />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>

      {/* Vercel Analytics */}
      <Analytics />

      <div className="min-h-screen bg-background text-foreground antialiased font-mono flex flex-col">
        {/* Top Header Navigation */}
        <div className="h-14 border-b border-border sticky top-0 bg-background z-50 flex items-center px-4 justify-between">
          <div className="flex items-center gap-6">
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
      </div>
    </>
  )
}
