import { createRoute, Link, redirect, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { api, auth } from '../utils/auth'
import { Route as rootRoute } from './__root'
import { ArrowLeft, TrendingUp, ArrowUp, ArrowDown, Activity, Zap, BarChart3, DollarSign } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, AreaChart, Area } from 'recharts'
import { ColumnDef, flexRender, getCoreRowModel, useReactTable, getSortedRowModel, SortingState } from '@tanstack/react-table'
import { useState, useMemo } from 'react'
import clsx from 'clsx'

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

type MarketCard = {
    id: number
    name: string
    set_name: string
    rarity_id: number
    latest_price: number
    avg_price: number
    volume_24h: number // Mapped from volume_period (Total/Window)
    volume_change: number // Delta
    price_delta_24h: number
    market_cap: number
    deal_rating: number
}

function MarketAnalysis() {
  const navigate = useNavigate()
  const [sorting, setSorting] = useState<SortingState>([])

  // Fetch optimized overview data from new endpoint
  const { data: rawCards, isLoading } = useQuery({
    queryKey: ['market-overview'],
    queryFn: async () => {
        const data = await api.get('market/overview').json<any[]>()
        return data.map(c => ({
            ...c,
            latest_price: c.latest_price ?? 0,
            volume_24h: c.volume_period ?? 0, // Using period volume
            volume_change: c.volume_change ?? 0,
            price_delta_24h: c.price_delta_period ?? 0,
            deal_rating: c.deal_rating ?? 0,
            market_cap: (c.latest_price ?? 0) * (c.volume_period ?? 0)
        })) as MarketCard[]
    }
  })

  const cards = useMemo(() => rawCards || [], [rawCards])

  // Compute Stats
  const metrics = useMemo(() => {
      const totalVolume = cards.reduce((acc, c) => acc + c.volume_24h, 0)
      const totalCap = cards.reduce((acc, c) => acc + c.market_cap, 0)
      // Estimate velocity: Total Volume / (Cards * Days). Assuming 30d window for total volume usually?
      // Let's just use average volume per card
      const avgVol = cards.length > 0 ? totalVolume / cards.length : 0
      const gainers = cards.filter(c => c.price_delta_24h > 0).length
      const losers = cards.filter(c => c.price_delta_24h < 0).length
      return { totalVolume, totalCap, avgVol, gainers, losers }
  }, [cards])

  // Top Lists
  const topGainers = useMemo(() => [...cards].sort((a, b) => b.price_delta_24h - a.price_delta_24h).slice(0, 5), [cards])
  const topLosers = useMemo(() => [...cards].sort((a, b) => a.price_delta_24h - b.price_delta_24h).slice(0, 5), [cards])
  
  // Table Columns
  const columns = useMemo<ColumnDef<MarketCard>[]>(() => [
      {
          accessorKey: 'name',
          header: ({ column }) => (
              <div className="cursor-pointer flex items-center gap-1" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>
                  ASSET <ArrowUp className={clsx("w-3 h-3 transition-transform", column.getIsSorted() === 'asc' ? "rotate-0" : "rotate-180 opacity-0")} />
              </div>
          ),
          cell: ({ row }) => (
              <div>
                  <div className="font-bold text-foreground hover:text-primary cursor-pointer truncate" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: String(row.original.id) } })}>
                      {row.original.name}
                  </div>
                  <div className="text-[10px] text-muted-foreground uppercase">{row.original.set_name}</div>
              </div>
          )
      },
      {
          accessorKey: 'latest_price',
          header: ({ column }) => <div className="text-right cursor-pointer" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>PRICE</div>,
          cell: ({ row }) => <div className="text-right font-mono font-bold">${row.original.latest_price.toFixed(2)}</div>
      },
      {
          accessorKey: 'price_delta_24h',
          header: ({ column }) => <div className="text-right cursor-pointer" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>24H %</div>,
          cell: ({ row }) => (
              <div className={clsx("text-right font-mono font-bold", row.original.price_delta_24h >= 0 ? "text-emerald-500" : "text-red-500")}>
                  {row.original.price_delta_24h > 0 ? '+' : ''}{row.original.price_delta_24h.toFixed(2)}%
              </div>
          )
      },
      {
          accessorKey: 'volume_24h',
          header: ({ column }) => <div className="text-right cursor-pointer" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>VOL</div>,
          cell: ({ row }) => <div className="text-right font-mono">{row.original.volume_24h}</div>
      },
      {
          accessorKey: 'market_cap',
          header: ({ column }) => <div className="text-right cursor-pointer" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>CAP</div>,
          cell: ({ row }) => <div className="text-right font-mono text-muted-foreground">${(row.original.market_cap / 1000).toFixed(1)}k</div>
      },
      {
          accessorKey: 'deal_rating',
          header: ({ column }) => <div className="text-right cursor-pointer" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>DEAL RATING</div>,
          cell: ({ row }) => {
              const rating = row.original.deal_rating
              // Negative deal rating means price is BELOW average (Good Deal)
              // Positive deal rating means price is ABOVE average (Bad Deal/Premium)
              const isGood = rating < 0
              return (
                  <div className="flex justify-end">
                      <span className={clsx("px-1.5 py-0.5 rounded text-[10px] uppercase font-bold border", 
                          isGood ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-500" : "border-amber-500/50 bg-amber-500/10 text-amber-500")}>
                          {Math.abs(rating).toFixed(1)}% {isGood ? 'UNDER' : 'OVER'}
                      </span>
                  </div>
              )
          }
      }
  ], [navigate])

  const table = useReactTable({
      data: cards,
      columns,
      getCoreRowModel: getCoreRowModel(),
      getSortedRowModel: getSortedRowModel(),
      onSortingChange: setSorting,
      state: { sorting }
  })

  if (isLoading) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-background text-foreground font-mono">
            <div className="text-center animate-pulse">
                <div className="text-xl uppercase tracking-widest mb-2">Analyzing Market</div>
                <div className="text-xs text-muted-foreground">Computing aggregate trends...</div>
            </div>
        </div>
      )
  }

  return (
    <div className="p-4 md:p-6 min-h-screen bg-background text-foreground font-mono">
        <div className="max-w-[1800px] mx-auto space-y-4">
            {/* Compact Header */}
            <div className="flex items-center justify-between border-b border-border pb-4">
                <div className="flex items-center gap-3">
                    <div className="bg-primary text-primary-foreground p-1.5 rounded">
                        <Activity className="w-4 h-4" />
                    </div>
                    <h1 className="text-lg font-bold uppercase tracking-tight">Market Pulse</h1>
                </div>
                <div className="flex gap-4 text-xs text-muted-foreground uppercase font-bold">
                    <div className="flex items-center gap-1">
                        <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span>
                        Live
                    </div>
                    <div>{cards.length} Assets Tracked</div>
                </div>
            </div>

            {/* KPI Dashboard - Compact Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-card border border-border p-3 rounded flex flex-col justify-between hover:border-primary/50 transition-colors">
                    <div className="flex justify-between items-start mb-2">
                        <span className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest">Total Volume</span>
                        <BarChart3 className="w-3 h-3 text-muted-foreground" />
                    </div>
                    <div>
                        <div className="text-xl font-mono font-bold">{metrics.totalVolume.toLocaleString()}</div>
                        <div className="text-[10px] text-muted-foreground">Total Units Traded</div>
                    </div>
                </div>
                <div className="bg-card border border-border p-3 rounded flex flex-col justify-between hover:border-primary/50 transition-colors">
                    <div className="flex justify-between items-start mb-2">
                        <span className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest">Market Cap</span>
                        <DollarSign className="w-3 h-3 text-muted-foreground" />
                    </div>
                    <div>
                        <div className="text-xl font-mono font-bold text-emerald-500">${(metrics.totalCap / 1000).toFixed(1)}k</div>
                        <div className="text-[10px] text-muted-foreground">Est. Total Value</div>
                    </div>
                </div>
                <div className="bg-card border border-border p-3 rounded flex flex-col justify-between hover:border-primary/50 transition-colors">
                    <div className="flex justify-between items-start mb-2">
                        <span className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest">Breadth</span>
                        <Activity className="w-3 h-3 text-muted-foreground" />
                    </div>
                    <div className="flex items-end gap-2">
                        <div className="text-xl font-mono font-bold text-emerald-500">{metrics.gainers}</div>
                        <div className="text-[10px] text-muted-foreground mb-1">Up</div>
                        <div className="text-xl font-mono font-bold text-red-500 ml-2">{metrics.losers}</div>
                        <div className="text-[10px] text-muted-foreground mb-1">Down</div>
                    </div>
                </div>
                <div className="bg-card border border-border p-3 rounded flex flex-col justify-between hover:border-primary/50 transition-colors">
                    <div className="flex justify-between items-start mb-2">
                        <span className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest">Avg Velocity</span>
                        <Zap className="w-3 h-3 text-amber-500" />
                    </div>
                    <div>
                        <div className="text-xl font-mono font-bold">{metrics.avgVol.toFixed(1)}</div>
                        <div className="text-[10px] text-muted-foreground">Trades / Asset</div>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
                {/* Left Column: Movers (Compact) */}
                <div className="lg:col-span-1 space-y-4">
                    <div className="bg-card border border-border rounded overflow-hidden">
                        <div className="p-3 border-b border-border bg-muted/20 flex justify-between items-center">
                            <span className="text-xs font-bold uppercase tracking-widest flex items-center gap-2 text-emerald-500">
                                <ArrowUp className="w-3 h-3" /> Top Gainers
                            </span>
                        </div>
                        <div className="divide-y divide-border/50">
                            {topGainers.slice(0, 5).map(c => (
                                <div key={c.id} className="p-2 flex justify-between items-center hover:bg-muted/30 cursor-pointer transition-colors" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: String(c.id) } })}>
                                    <div className="truncate w-24 text-xs font-bold">{c.name}</div>
                                    <div className="text-right">
                                        <div className="text-emerald-500 text-xs font-mono font-bold">+{c.price_delta_24h.toFixed(1)}%</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="bg-card border border-border rounded overflow-hidden">
                        <div className="p-3 border-b border-border bg-muted/20 flex justify-between items-center">
                            <span className="text-xs font-bold uppercase tracking-widest flex items-center gap-2 text-red-500">
                                <ArrowDown className="w-3 h-3" /> Top Losers
                            </span>
                        </div>
                        <div className="divide-y divide-border/50">
                            {topLosers.slice(0, 5).map(c => (
                                <div key={c.id} className="p-2 flex justify-between items-center hover:bg-muted/30 cursor-pointer transition-colors" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: String(c.id) } })}>
                                    <div className="truncate w-24 text-xs font-bold">{c.name}</div>
                                    <div className="text-right">
                                        <div className="text-red-500 text-xs font-mono font-bold">{c.price_delta_24h.toFixed(1)}%</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Right Column: Detailed Table */}
                <div className="lg:col-span-3 bg-card border border-border rounded flex flex-col h-[600px]">
                    <div className="p-3 border-b border-border bg-muted/20 flex justify-between items-center">
                        <h3 className="text-xs font-bold uppercase tracking-widest">Market Depth & Analytics</h3>
                        <div className="text-[10px] text-muted-foreground">
                            Sortable Columns • Real-time
                        </div>
                    </div>
                    <div className="flex-1 overflow-auto">
                        <table className="w-full text-sm text-left border-collapse">
                            <thead className="text-[10px] uppercase bg-background text-muted-foreground sticky top-0 z-10 border-b border-border">
                                {table.getHeaderGroups().map(headerGroup => (
                                    <tr key={headerGroup.id}>
                                        {headerGroup.headers.map(header => (
                                            <th key={header.id} className="px-4 py-2 font-medium whitespace-nowrap bg-background">
                                                {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                                            </th>
                                        ))}
                                    </tr>
                                ))}
                            </thead>
                            <tbody className="divide-y divide-border/50">
                                {table.getRowModel().rows.map(row => (
                                    <tr key={row.id} className="hover:bg-muted/30 transition-colors group text-xs">
                                        {row.getVisibleCells().map(cell => (
                                            <td key={cell.id} className="px-4 py-2 whitespace-nowrap">
                                                {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
  )
}
