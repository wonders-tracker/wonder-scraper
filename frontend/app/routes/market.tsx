import { createRoute, Link, redirect } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { api, auth } from '../utils/auth'
import { Route as rootRoute } from './__root'
import { ArrowLeft, TrendingUp, ArrowUp, ArrowDown, Activity } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

export const Route = createRoute({
  getParentRoute: () => rootRoute,
  path: '/market',
  component: MarketAnalysis,
  beforeLoad: () => {
      if (typeof window !== 'undefined' && !auth.isAuthenticated()) {
          throw redirect({ to: '/login' })
      }
  }
})

function MarketAnalysis() {
  // Fetch optimized overview data from new endpoint
  const { data: cards, isLoading } = useQuery({
    queryKey: ['market-overview'],
    queryFn: async () => {
        const data = await api.get('market/overview').json<any[]>()
        return data.map(c => ({
            ...c,
            latest_price: c.latest_price ?? 0,
            volume_24h: c.volume_24h ?? 0,
            price_delta_24h: c.price_delta_24h ?? 0, // Backend currently returns 0 for speed, we might enhance later
            market_cap: (c.latest_price ?? 0) * (c.volume_24h ?? 0)
        }))
    }
  })

  if (isLoading || !cards) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-background text-foreground font-mono">
            <div className="text-center animate-pulse">
                <div className="text-xl uppercase tracking-widest mb-2">Analyzing Market</div>
                <div className="text-xs text-muted-foreground">Computing aggregate trends...</div>
            </div>
        </div>
      )
  }

  // Compute Stats (Client side aggregation is fine for ~500 items)
  const totalVolume = cards.reduce((acc, c) => acc + (c.volume_24h || 0), 0)
  const totalVolumeUSD = cards.reduce((acc, c) => acc + ((c.volume_24h || 0) * (c.latest_price || 0)), 0)
  
  // Note: With backend returning 0 delta for optimization, gainers/losers won't show much unless backend is updated.
  // But this structure supports it when we enable delta calculation in the optimized endpoint.
  const topGainers = [...cards]
    .filter(c => c.latest_price > 0 && c.price_delta_24h > 0)
    .sort((a, b) => b.price_delta_24h - a.price_delta_24h)
    .slice(0, 5)

  const topLosers = [...cards]
    .filter(c => c.latest_price > 0 && c.price_delta_24h < 0)
    .sort((a, b) => a.price_delta_24h - b.price_delta_24h)
    .slice(0, 5)

  const volumeLeaders = [...cards]
    .sort((a, b) => b.volume_24h - a.volume_24h)
    .slice(0, 10)

  // Chart Data
  const volChartData = volumeLeaders.map(c => ({
      name: c.name.substring(0, 10) + '...',
      volume: c.volume_24h
  }))

  return (
    <div className="p-6 min-h-screen bg-background text-foreground font-mono">
        <div className="max-w-7xl mx-auto">
            {/* Header */}
            <div className="mb-10 flex justify-between items-center">
                <div className="flex items-center gap-4">
                    <Link to="/" className="flex items-center justify-center w-8 h-8 border border-border rounded hover:bg-muted/50 transition-colors">
                        <ArrowLeft className="w-4 h-4 text-muted-foreground" />
                    </Link>
                    <h1 className="text-3xl font-bold uppercase tracking-tight">Market Analysis</h1>
                </div>
                <div className="text-xs text-muted-foreground uppercase tracking-wider">
                    Market Status: <span className="text-emerald-500 font-bold">Active</span>
                </div>
            </div>

            {/* KPI Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
                <div className="border border-border p-6 rounded-lg bg-card relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-4 opacity-10">
                        <Activity className="w-24 h-24" />
                    </div>
                    <div className="text-xs text-muted-foreground uppercase mb-2 font-bold tracking-widest">Market Volume (24h)</div>
                    <div className="text-4xl font-mono font-bold">{totalVolume.toLocaleString()} <span className="text-lg font-normal text-muted-foreground">units</span></div>
                </div>
                <div className="border border-border p-6 rounded-lg bg-card relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-4 opacity-10">
                        <TrendingUp className="w-24 h-24" />
                    </div>
                    <div className="text-xs text-muted-foreground uppercase mb-2 font-bold tracking-widest">Traded Value (24h)</div>
                    <div className="text-4xl font-mono font-bold text-emerald-500">${totalVolumeUSD.toLocaleString(undefined, {maximumFractionDigits: 0})}</div>
                </div>
                <div className="border border-border p-6 rounded-lg bg-card relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-4 opacity-10">
                        <Activity className="w-24 h-24" />
                    </div>
                    <div className="text-xs text-muted-foreground uppercase mb-2 font-bold tracking-widest">Active Assets</div>
                    <div className="text-4xl font-mono font-bold">{cards.length} <span className="text-lg font-normal text-muted-foreground">cards</span></div>
                </div>
            </div>

            {/* Movers Section */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-10">
                {/* Top Gainers */}
                <div className="border border-border rounded-lg bg-card">
                    <div className="px-6 py-4 border-b border-border bg-muted/20">
                        <h3 className="text-xs font-bold uppercase tracking-widest flex items-center gap-2 text-emerald-500">
                            <ArrowUp className="w-4 h-4" /> Top Gainers (24h)
                        </h3>
                    </div>
                    <div className="divide-y divide-border/50">
                        {topGainers.map(c => (
                            <div key={c.id} className="px-6 py-3 flex justify-between items-center hover:bg-muted/30 transition-colors">
                                <div>
                                    <Link to={`/cards/${c.id}`} className="font-bold hover:text-primary text-sm">{c.name}</Link>
                                    <div className="text-[10px] text-muted-foreground uppercase">{c.set_name}</div>
                                </div>
                                <div className="text-right">
                                    <div className="text-emerald-500 font-mono font-bold">+{c.price_delta_24h.toFixed(2)}%</div>
                                    <div className="text-xs text-muted-foreground font-mono">${c.latest_price.toFixed(2)}</div>
                                </div>
                            </div>
                        ))}
                        {topGainers.length === 0 && <div className="p-6 text-center text-muted-foreground text-xs">No gainers recorded.</div>}
                    </div>
                </div>

                {/* Top Losers */}
                <div className="border border-border rounded-lg bg-card">
                    <div className="px-6 py-4 border-b border-border bg-muted/20">
                        <h3 className="text-xs font-bold uppercase tracking-widest flex items-center gap-2 text-red-500">
                            <ArrowDown className="w-4 h-4" /> Top Losers (24h)
                        </h3>
                    </div>
                    <div className="divide-y divide-border/50">
                        {topLosers.map(c => (
                            <div key={c.id} className="px-6 py-3 flex justify-between items-center hover:bg-muted/30 transition-colors">
                                <div>
                                    <Link to={`/cards/${c.id}`} className="font-bold hover:text-primary text-sm">{c.name}</Link>
                                    <div className="text-[10px] text-muted-foreground uppercase">{c.set_name}</div>
                                </div>
                                <div className="text-right">
                                    <div className="text-red-500 font-mono font-bold">{c.price_delta_24h.toFixed(2)}%</div>
                                    <div className="text-xs text-muted-foreground font-mono">${c.latest_price.toFixed(2)}</div>
                                </div>
                            </div>
                        ))}
                        {topLosers.length === 0 && <div className="p-6 text-center text-muted-foreground text-xs">No losers recorded.</div>}
                    </div>
                </div>
            </div>

            {/* Volume Chart */}
            <div className="border border-border rounded-lg bg-card p-6">
                <h3 className="text-xs font-bold uppercase tracking-widest mb-6">Volume Leaders</h3>
                <div className="h-[300px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={volChartData} layout="vertical">
                            <CartesianGrid strokeDasharray="3 3" stroke="#333" horizontal={false} />
                            <XAxis type="number" hide />
                            <YAxis 
                                dataKey="name" 
                                type="category" 
                                width={100} 
                                tick={{fill: '#888', fontSize: 10, fontFamily: 'monospace'}} 
                                interval={0}
                            />
                            <Tooltip 
                                cursor={{fill: '#333', opacity: 0.2}}
                                contentStyle={{backgroundColor: '#000', borderColor: '#333', fontFamily: 'monospace', fontSize: '12px'}}
                                itemStyle={{color: '#fff'}}
                            />
                            <Bar dataKey="volume" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>
        </div>
    </div>
  )
}
