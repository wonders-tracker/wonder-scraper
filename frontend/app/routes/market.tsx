import { createRoute, Link, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { api, auth } from '../utils/auth'
import { Route as rootRoute } from './__root'
import { ArrowLeft, TrendingUp, ArrowUp, ArrowDown, Activity, Zap, BarChart3, DollarSign } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, AreaChart, Area } from 'recharts'
import { ColumnDef, flexRender, getCoreRowModel, useReactTable, getSortedRowModel, SortingState, getPaginationRowModel } from '@tanstack/react-table'
import { useState, useMemo } from 'react'
import clsx from 'clsx'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Clock } from 'lucide-react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select"

export const Route = createRoute({
  getParentRoute: () => rootRoute,
  path: '/market',
  component: MarketAnalysis
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
    treatment?: string
}

function MarketAnalysis() {
  const navigate = useNavigate()
  const [sorting, setSorting] = useState<SortingState>([])
  const [timeFrame, setTimeFrame] = useState('24h')

  // Fetch treatment price floors
  const { data: treatments } = useQuery({
    queryKey: ['treatments'],
    queryFn: async () => {
        return await api.get('market/treatments').json<{ name: string; min_price: number; count: number }[]>()
    }
  })

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
      const avgVol = cards.length > 0 ? totalVolume / cards.length : 0
      const gainers = cards.filter(c => c.price_delta_24h > 0).length
      const losers = cards.filter(c => c.price_delta_24h < 0).length
      const unchanged = cards.filter(c => c.price_delta_24h === 0).length
      const totalAssets = cards.length

      // Top mover (biggest absolute change)
      const sortedByChange = [...cards].sort((a, b) => Math.abs(b.price_delta_24h) - Math.abs(a.price_delta_24h))
      const topMover = sortedByChange[0] || null

      // Most active (highest volume)
      const sortedByVolume = [...cards].sort((a, b) => b.volume_24h - a.volume_24h)
      const mostActive = sortedByVolume[0] || null

      // Highest value card
      const sortedByPrice = [...cards].sort((a, b) => b.latest_price - a.latest_price)
      const highestValue = sortedByPrice[0] || null

      // Breadth ratio
      const breadthRatio = totalAssets > 0 ? ((gainers - losers) / totalAssets * 100) : 0

      return { totalVolume, totalCap, avgVol, gainers, losers, unchanged, totalAssets, topMover, mostActive, highestValue, breadthRatio }
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
          header: ({ column }) => <div className="text-right cursor-pointer" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>MKT CAP</div>,
          cell: ({ row }) => {
              const cap = row.original.market_cap
              if (cap === 0 || !cap) return <div className="text-right font-mono text-muted-foreground">-</div>
              // Format based on size: <$1k show $X, $1k-$1M show $Xk, >$1M show $XM
              let formatted: string
              if (cap >= 1000000) {
                  formatted = `$${(cap / 1000000).toFixed(1)}M`
              } else if (cap >= 1000) {
                  formatted = `$${(cap / 1000).toFixed(1)}k`
              } else {
                  formatted = `$${cap.toFixed(0)}`
              }
              return <div className="text-right font-mono text-muted-foreground">{formatted}</div>
          }
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
      getPaginationRowModel: getPaginationRowModel(),
      onSortingChange: setSorting,
      state: { sorting },
      initialState: {
          pagination: {
              pageSize: 20,
          },
      },
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
    <div className="p-4 md:p-6 h-[calc(100vh-4rem)] bg-background text-foreground font-mono flex flex-col overflow-hidden">
        <div className="max-w-[1800px] mx-auto w-full flex flex-col gap-4 h-full overflow-hidden">
            {/* Compact Header */}
            <div className="flex items-center justify-between border-b border-border pb-4">
                <div className="flex items-center gap-3">
                    <div className="bg-primary text-primary-foreground p-1.5 rounded">
                        <Activity className="w-4 h-4" />
                    </div>
                    <h1 className="text-lg font-bold uppercase tracking-tight">Market Pulse</h1>
                    <div className="flex items-center gap-2 ml-4">
                        <Clock className="w-3 h-3 text-muted-foreground" />
                        <Select value={timeFrame} onValueChange={setTimeFrame}>
                            <SelectTrigger className="w-[100px] h-8 text-xs">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="1h">1 Hour</SelectItem>
                                <SelectItem value="24h">24 Hours</SelectItem>
                                <SelectItem value="7d">7 Days</SelectItem>
                                <SelectItem value="30d">30 Days</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </div>
                <div className="flex gap-4 text-xs text-muted-foreground uppercase font-bold">
                    <div className="flex items-center gap-1">
                        <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span>
                        Live
                    </div>
                    <div>{cards.length} Assets Tracked</div>
                </div>
            </div>

            {/* KPI Dashboard - Wide Cards with Insights */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2 flex-shrink-0">
                <div className="bg-card border border-border px-4 py-2.5 rounded hover:border-primary/50 transition-colors">
                    <div className="flex items-center justify-between mb-1">
                        <span className="text-[9px] uppercase text-muted-foreground font-medium">Assets Tracked</span>
                    </div>
                    <div className="text-xl font-mono font-bold">{metrics.totalAssets}</div>
                </div>

                <div className="bg-card border border-border px-4 py-2.5 rounded hover:border-primary/50 transition-colors">
                    <div className="flex items-center justify-between mb-1">
                        <span className="text-[9px] uppercase text-muted-foreground font-medium">24h Volume</span>
                    </div>
                    <div className="text-xl font-mono font-bold">{metrics.totalVolume.toLocaleString()} <span className="text-xs text-muted-foreground">units</span></div>
                </div>

                <div className="bg-card border border-border px-4 py-2.5 rounded hover:border-primary/50 transition-colors">
                    <div className="flex items-center justify-between mb-1">
                        <span className="text-[9px] uppercase text-muted-foreground font-medium">Market Cap</span>
                    </div>
                    <div className="text-xl font-mono font-bold text-emerald-500">${(metrics.totalCap / 1000).toFixed(1)}k</div>
                </div>

                <div className="bg-card border border-border px-4 py-2.5 rounded hover:border-primary/50 transition-colors">
                    <div className="flex items-center justify-between mb-1">
                        <span className="text-[9px] uppercase text-muted-foreground font-medium">Market Sentiment</span>
                    </div>
                    <div className="flex items-center gap-3">
                        <span className="text-lg font-mono font-bold text-emerald-500">{metrics.gainers}↑</span>
                        <span className="text-lg font-mono font-bold text-red-500">{metrics.losers}↓</span>
                        <span className="text-xs text-muted-foreground">{metrics.unchanged} flat</span>
                    </div>
                </div>

                <div className="bg-card border border-border px-4 py-2.5 rounded hover:border-primary/50 transition-colors cursor-pointer" onClick={() => metrics.mostActive && navigate({ to: '/cards/$cardId', params: { cardId: String(metrics.mostActive.id) } })}>
                    <div className="flex items-center justify-between mb-1">
                        <span className="text-[9px] uppercase text-muted-foreground font-medium">Most Active</span>
                        <span className="text-[9px] text-primary">→</span>
                    </div>
                    <div className="truncate">
                        <span className="text-sm font-bold">{metrics.mostActive?.name || '-'}</span>
                        <span className="text-xs text-muted-foreground ml-2">{metrics.mostActive?.volume_24h || 0} trades</span>
                    </div>
                </div>

                <div className="bg-card border border-border px-4 py-2.5 rounded hover:border-primary/50 transition-colors cursor-pointer" onClick={() => metrics.highestValue && navigate({ to: '/cards/$cardId', params: { cardId: String(metrics.highestValue.id) } })}>
                    <div className="flex items-center justify-between mb-1">
                        <span className="text-[9px] uppercase text-muted-foreground font-medium">Highest Value</span>
                        <span className="text-[9px] text-primary">→</span>
                    </div>
                    <div className="truncate">
                        <span className="text-sm font-bold">{metrics.highestValue?.name || '-'}</span>
                        <span className="text-xs text-emerald-500 ml-2">${metrics.highestValue?.latest_price.toFixed(2) || '0'}</span>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 flex-1 overflow-hidden">
                {/* Left Column: Movers (Compact) */}
                <div className="lg:col-span-1 space-y-4 overflow-y-auto">
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

                    {/* Price Floors by Treatment */}
                    <div className="bg-card border border-border rounded overflow-hidden">
                        <div className="p-3 border-b border-border bg-muted/20">
                            <span className="text-xs font-bold uppercase tracking-widest flex items-center gap-2">
                                <DollarSign className="w-3 h-3" /> Price Floors
                            </span>
                        </div>
                        <div className="divide-y divide-border/50">
                            {treatments?.map(treatment => (
                                <div key={treatment.name} className="p-2 flex justify-between items-center">
                                    <div className="flex items-center gap-2">
                                        <div className="text-xs font-bold">{treatment.name}</div>
                                        <div className="text-[10px] text-muted-foreground">({treatment.count})</div>
                                    </div>
                                    <div className="text-right">
                                        <div className="text-xs font-mono font-bold">${treatment.min_price.toFixed(2)}</div>
                                    </div>
                                </div>
                            )) || (
                                <div className="p-4 text-center text-xs text-muted-foreground">Loading...</div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Right Column: Detailed Table */}
                <div className="lg:col-span-3 bg-card border border-border rounded flex flex-col min-h-0">
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

                    {/* Pagination Controls */}
                    <div className="border-t border-border p-3 bg-muted/20 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => table.setPageIndex(0)}
                                disabled={!table.getCanPreviousPage()}
                                className="p-1 rounded hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                <ChevronsLeft className="w-4 h-4" />
                            </button>
                            <button
                                onClick={() => table.previousPage()}
                                disabled={!table.getCanPreviousPage()}
                                className="p-1 rounded hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                <ChevronLeft className="w-4 h-4" />
                            </button>
                            <button
                                onClick={() => table.nextPage()}
                                disabled={!table.getCanNextPage()}
                                className="p-1 rounded hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                <ChevronRight className="w-4 h-4" />
                            </button>
                            <button
                                onClick={() => table.setPageIndex(table.getPageCount() - 1)}
                                disabled={!table.getCanNextPage()}
                                className="p-1 rounded hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                <ChevronsRight className="w-4 h-4" />
                            </button>
                        </div>

                        <div className="flex items-center gap-4">
                            <span className="text-xs text-muted-foreground">
                                Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
                            </span>
                            <span className="text-xs text-muted-foreground">
                                {table.getFilteredRowModel().rows.length} total assets
                            </span>
                        </div>

                        <Select
                            value={String(table.getState().pagination.pageSize)}
                            onValueChange={(value) => table.setPageSize(Number(value))}
                        >
                            <SelectTrigger className="w-[100px] h-8 text-xs">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="10">10 / page</SelectItem>
                                <SelectItem value="20">20 / page</SelectItem>
                                <SelectItem value="50">50 / page</SelectItem>
                                <SelectItem value="100">100 / page</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </div>
            </div>
        </div>
    </div>
  )
}
