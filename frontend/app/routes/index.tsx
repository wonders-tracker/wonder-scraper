import { createRoute, useNavigate, Link } from '@tanstack/react-router'
import { api, auth } from '../utils/auth'
import { useQuery } from '@tanstack/react-query'
import { ColumnDef, flexRender, getCoreRowModel, useReactTable, getSortedRowModel, SortingState, getFilteredRowModel } from '@tanstack/react-table'
import { useState, useMemo } from 'react'
import { ArrowUpDown, Search, ArrowUp, ArrowDown, Calendar, TrendingUp, DollarSign, BarChart3, LayoutDashboard } from 'lucide-react'
import clsx from 'clsx'
import { Route as rootRoute } from './__root'
import Marquee from '../components/ui/marquee'

// Updated Type Definition including placeholder fields
type Card = {
  id: number
  name: string
  set_name: string
  rarity_id: number
  // Optional fields that might come from backend logic or joins
  latest_price?: number
  vwap?: number // Volume Weighted Average Price
  volume_24h?: number
  price_delta_24h?: number // Placeholder for delta
  lowest_ask?: number
  inventory?: number
  volume_usd_24h?: number // New field for dollar volume
  product_type?: string // Single, Box, Pack, Proof
  max_price?: number // Highest confirmed sale
}

type UserProfile = {
    id: number
    email: string
    is_superuser: boolean
}

export const Route = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: Home,
})

function Home() {
  const [sorting, setSorting] = useState<SortingState>([])
  const [globalFilter, setGlobalFilter] = useState('')
  const [timePeriod, setTimePeriod] = useState<string>('24h')
  const [productType, setProductType] = useState<string>('all')
  const navigate = useNavigate()

  // Fetch User Profile for Permissions
  const { data: user } = useQuery({
      queryKey: ['me'],
      queryFn: async () => {
          try {
              return await api.get('users/me').json<UserProfile>()
          } catch {
              return null
          }
      },
      retry: false
  })

  const { data: cards, isLoading } = useQuery({
    queryKey: ['cards', timePeriod, productType],
    queryFn: async () => {
      const typeParam = productType !== 'all' ? `&product_type=${productType}` : ''
      // Limit increased to 500 to show more assets
      const data = await api.get(`cards?limit=500&time_period=${timePeriod}${typeParam}`).json<Card[]>()
      return data.map(c => ({
          ...c,
          // Logic: Use real data if available, fallback to mock ONLY if null/undefined for demo smoothness
          // The API now returns flattened real data
          latest_price: c.latest_price ?? 0,
          volume_24h: c.volume_24h ?? 0,
          inventory: c.inventory ?? 0,
          // These fields are not yet in schema/DB so we mock them or derive
          // high_bid: (c.lowest_ask ?? c.latest_price ?? 0) * 0.9, // Removed mock high_bid
          // low_ask: c.lowest_ask ?? (c.latest_price ?? 0) * 1.1, // Removed mock low_ask
          // Only show delta if price exists
          price_delta_24h: c.price_delta_24h ?? 0,
          volume_usd_24h: (c.volume_24h ?? 0) * (c.vwap ?? c.latest_price ?? 0), // Calculate dollar volume using VWAP if possible
          highest_bid: (c as any).highest_bid ?? 0
      })).filter(c => (c.latest_price && c.latest_price > 0) || (c.volume_24h && c.volume_24h > 0)) // Filter out 0 listings
    },
    staleTime: 5 * 60 * 1000, // 5 minutes - data stays fresh
    gcTime: 30 * 60 * 1000, // 30 minutes - cache persists (renamed from cacheTime in v5)
    refetchOnWindowFocus: false, // Don't refetch on tab focus
    refetchOnMount: false, // Don't refetch on component mount if data exists
  })

  const columns = useMemo<ColumnDef<Card>[]>(() => [
    {
      accessorKey: 'name',
      header: ({ column }) => {
        return (
          <button
            className="flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Name
            <ArrowUpDown className="h-3 w-3" />
          </button>
        )
      },
      cell: ({ row }) => {
        const productType = row.original.product_type || 'Single'
        return (
          <div className="max-w-[150px] md:max-w-none truncate">
              <div className="flex items-center gap-2">
                <span className="font-bold text-foreground truncate" title={row.getValue('name')}>{row.getValue('name')}</span>
                <span className="hidden md:inline-flex px-1.5 py-0.5 rounded text-[8px] uppercase font-semibold bg-muted/30 text-muted-foreground border border-border">
                  {productType}
                </span>
              </div>
              <div className="text-xs text-muted-foreground uppercase truncate">{row.original.set_name}</div>
          </div>
        )
      },
    },
    {
      accessorKey: 'vwap', // Changed to VWAP for price column
      header: ({ column }) => (
        <button
          className="flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs ml-auto"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          Price (VWAP)
          <ArrowUpDown className="h-3 w-3" />
        </button>
      ),
      cell: ({ row }) => {
          const price = row.original.vwap || row.original.latest_price // Prefer VWAP
          const delta = row.original.price_delta_24h || 0
          const isPositive = delta >= 0
          const hasPrice = price && price > 0

          return (
            <div className="text-right">
                <div className="font-mono text-base">
                    {hasPrice ? `$${price.toFixed(2)}` : '---'}
                </div>
                {hasPrice ? (
                    delta !== 0 ? (
                        <div className={clsx(
                            "text-xs font-mono flex items-center justify-end gap-1",
                            isPositive ? "text-emerald-500" : "text-red-500"
                        )}>
                            {isPositive ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
                            {Math.abs(delta).toFixed(2)}%
                        </div>
                    ) : (
                        <div className="text-xs font-mono flex items-center justify-end gap-1 text-muted-foreground/50">
                            <span>0.00%</span>
                        </div>
                    )
                ) : null}
            </div>
          )
      }
    },
    {
        accessorKey: 'volume_24h',
        header: ({ column }) => (
          <button
            className="flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs ml-auto"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Vol (Units)
            <ArrowUpDown className="h-3 w-3" />
          </button>
        ),
        cell: ({ row }) => {
            const vol = row.original.volume_24h || 0
            // Improved Contrast Badges
            let badgeClass = "bg-zinc-800 text-zinc-300 border-zinc-700" // Low/Gray
            if (vol > 30) badgeClass = "bg-emerald-700 text-emerald-50 border-emerald-600 font-bold" // Updated to solid colors
            else if (vol > 10) badgeClass = "bg-amber-700 text-amber-50 border-amber-600 font-bold" // Updated to solid colors
            else if (vol === 0) badgeClass = "bg-red-700 text-red-50 border-red-600 opacity-50" // Updated to solid colors

            return (
                <div className="flex justify-end">
                    <span className={clsx("px-2 py-0.5 rounded border font-mono text-xs shadow-sm", badgeClass)}>
                        {vol}
                    </span>
                </div>
            )
        }
    },
    {
        accessorKey: 'volume_usd_24h', // New column for dollar volume
        header: ({ column }) => (
          <button
            className="hidden md:flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs ml-auto"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Vol ($)
            <ArrowUpDown className="h-3 w-3" />
          </button>
        ),
        cell: ({ row }) => {
            const volUsd = row.original.volume_usd_24h || 0
            return (
                <div className="hidden md:block text-right font-mono text-xs text-muted-foreground">
                    {volUsd > 0 ? `$${volUsd.toFixed(2)}` : '---'}
                </div>
            )
        }
    },
    {
        accessorKey: 'lowest_ask',
        header: ({ column }) => (
          <button
            className="hidden md:flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs text-muted-foreground ml-auto"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Low Ask
            <ArrowUpDown className="h-3 w-3" />
          </button>
        ),
        cell: ({ row }) => <div className="hidden md:block text-right font-mono text-xs text-muted-foreground">{row.original.lowest_ask ? `$${Number(row.original.lowest_ask).toFixed(2)}` : '---'}</div>
    },
    {
        accessorKey: 'max_price',
        header: ({ column }) => (
          <button
            className="hidden lg:flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs text-muted-foreground ml-auto"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Highest Sale
            <ArrowUpDown className="h-3 w-3" />
          </button>
        ),
        cell: ({ row }) => <div className="hidden lg:block text-right font-mono text-xs text-emerald-600">{row.original.max_price ? `$${Number(row.original.max_price).toFixed(2)}` : '---'}</div>
    },
    {
        accessorKey: 'inventory',
        header: ({ column }) => (
          <button
            className="hidden md:flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs text-muted-foreground ml-auto"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Inv
            <ArrowUpDown className="h-3 w-3" />
          </button>
        ),
        cell: ({ row }) => <div className="hidden md:block text-right font-mono text-xs text-muted-foreground">{row.original.inventory}</div>
    }
  ], [])

  const table = useReactTable({
    data: cards || [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    onSortingChange: setSorting,
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onGlobalFilterChange: setGlobalFilter,
    state: {
      sorting,
      globalFilter,
    },
  })

  // Compute dynamic sidebars
  const topGainers = useMemo(() => {
      if (!cards) return []
      // Lower threshold to 0.01% to capture more gainers
      return [...cards]
          .filter(c => (c.latest_price || 0) > 0 && (c.price_delta_24h || 0) > 0.01)
          .sort((a, b) => (b.price_delta_24h || 0) - (a.price_delta_24h || 0))
          .slice(0, 5)
  }, [cards])
  
  const topLosers = useMemo(() => {
      if (!cards) return []
      // Lower threshold to -0.01% to capture more losers
      return [...cards]
          .filter(c => (c.latest_price || 0) > 0 && (c.price_delta_24h || 0) < -0.01)
          .sort((a, b) => (a.price_delta_24h || 0) - (b.price_delta_24h || 0))
          .slice(0, 5)
  }, [cards])

  const topVolume = useMemo(() => {
      if (!cards) return []
      return [...cards]
          .sort((a, b) => (b.volume_24h || 0) - (a.volume_24h || 0))
          .slice(0, 5)
  }, [cards])
  
  // Calculate market metrics
  const marketMetrics = useMemo(() => {
      if (!cards) return { totalVolume: 0, totalVolumeUSD: 0, avgVelocity: 0 }
      
      const totalVolume = cards.reduce((sum, c) => sum + (c.volume_24h || 0), 0)
      const totalVolumeUSD = cards.reduce((sum, c) => sum + ((c.volume_24h || 0) * (c.latest_price || 0)), 0)
      
      // Sale velocity = avg sales per card per day
      // For time periods other than 24h, normalize to daily rate
      const timePeriodDays = timePeriod === '24h' ? 1 : timePeriod === '7d' ? 7 : timePeriod === '30d' ? 30 : timePeriod === '90d' ? 90 : 1
      const avgVelocity = cards.length > 0 ? (totalVolume / cards.length / timePeriodDays) : 0
      
      return { totalVolume, totalVolumeUSD, avgVelocity }
  }, [cards, timePeriod])

  return (
    <div className="min-h-screen bg-background text-foreground font-mono">
      {/* Market Pulse Marquee */}
      <div className="border-b border-border bg-muted/10 backdrop-blur overflow-hidden flex items-center h-10 sticky top-0 z-40">
           {/* Fixed Metrics */}
           <div className="flex items-center px-4 border-r border-border h-full bg-background/50 z-10">
                <div className="flex items-center gap-2 text-xs font-mono mr-4">
                    <span className="text-muted-foreground uppercase">Vol:</span>
                    <span className="font-bold">{marketMetrics.totalVolume}</span>
                </div>
                 <div className="flex items-center gap-2 text-xs font-mono">
                    <span className="text-muted-foreground uppercase">Vel:</span>
                    <span className="font-bold text-emerald-500">{Number(marketMetrics.avgVelocity).toFixed(1)}/d</span>
                </div>
           </div>
           
           {/* Scrolling Ticker */}
           <div className="flex-1 min-w-0">
               <Marquee pauseOnHover className="[--gap:2rem]">
                    {/* Fallback if lists are empty: show top volume items */}
                    {(topGainers.length === 0 && topLosers.length === 0) && topVolume.slice(0, 8).map(c => (
                        <div key={`ticker-vol-${c.id}`} className="flex items-center gap-2 text-xs font-mono cursor-pointer hover:text-primary transition-colors whitespace-nowrap" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: String(c.id) } })}>
                            <span className="font-bold uppercase">{c.name}</span>
                            <span className="text-muted-foreground">${Number(c.latest_price).toFixed(2)}</span>
                        </div>
                    ))}

                    {topGainers.slice(0, 5).map(c => (
                        <div key={`ticker-${c.id}`} className="flex items-center gap-2 text-xs font-mono cursor-pointer hover:text-primary transition-colors whitespace-nowrap" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: String(c.id) } })}>
                            <span className="font-bold uppercase">{c.name}</span>
                            <span className="text-emerald-500">+{Number(c.price_delta_24h).toFixed(1)}%</span>
                        </div>
                    ))}
                    {topLosers.slice(0, 3).map(c => (
                        <div key={`ticker-loss-${c.id}`} className="flex items-center gap-2 text-xs font-mono cursor-pointer hover:text-primary transition-colors whitespace-nowrap" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: String(c.id) } })}>
                            <span className="font-bold uppercase">{c.name}</span>
                            <span className="text-red-500">{Number(c.price_delta_24h).toFixed(1)}%</span>
                        </div>
                    ))}
               </Marquee>
           </div>
        </div>
        
      <div className="p-6 max-w-[1600px] mx-auto space-y-6">
        {/* Main Data Table */}
        <div className="border border-border rounded bg-card overflow-hidden">
            <div className="p-3 md:p-4 border-b border-border flex flex-col xl:flex-row xl:items-center justify-between bg-muted/20 gap-4">
                <div className="flex flex-col md:flex-row md:items-center gap-4 md:gap-8 w-full">
                    <h2 className="text-sm font-bold uppercase tracking-wider flex items-center gap-2 shrink-0">
                        <LayoutDashboard className="w-4 h-4 text-muted-foreground" />
                        Wonders of the First
                    </h2>
                    
                    {/* Filters & Controls inside Header */}
                    <div className="flex flex-col sm:flex-row flex-wrap items-start sm:items-center gap-2 md:gap-4 w-full">
                        <div className="relative w-full flex-1">
                             <Search className="absolute left-3 top-2 h-3.5 w-3.5 text-muted-foreground" />
                 <input 
                    type="text" 
                                placeholder="SEARCH..." 
                                className="w-full bg-background pl-9 pr-4 py-1.5 rounded border border-border text-xs focus:outline-none focus:ring-1 focus:ring-primary placeholder:text-muted-foreground/50"
                    value={globalFilter}
                    onChange={e => setGlobalFilter(e.target.value)}
                 />
            </div>
            
                        <div className="flex items-center gap-2 w-full sm:w-auto shrink-0">
                            <select 
                                className="flex-1 sm:flex-none bg-background px-3 py-1.5 rounded border border-border text-xs focus:outline-none focus:ring-1 focus:ring-primary uppercase font-mono cursor-pointer hover:bg-muted transition-colors"
                                value={productType}
                                onChange={e => setProductType(e.target.value)}
                            >
                                <option value="all">All Types</option>
                                <option value="Single">Singles</option>
                                <option value="Pack">Packs</option>
                                <option value="Box">Boxes</option>
                                <option value="Proof">Proofs</option>
                                <option value="Lot">Lots</option>
                            </select>

                            <div className="relative flex items-center flex-1 sm:flex-none">
                                <Calendar className="absolute left-2.5 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
                <select 
                                    className="w-full bg-background pl-9 pr-3 py-1.5 rounded border border-border text-xs focus:outline-none focus:ring-1 focus:ring-primary uppercase font-mono cursor-pointer hover:bg-muted transition-colors"
                    value={timePeriod}
                    onChange={e => setTimePeriod(e.target.value)}
                >
                    <option value="24h">24 Hours</option>
                    <option value="7d">7 Days</option>
                    <option value="30d">30 Days</option>
                    <option value="90d">90 Days</option>
                    <option value="all">All Time</option>
                </select>
            </div>
        </div>
        </div>
      </div>

                <div className="text-xs text-muted-foreground font-mono hidden xl:block shrink-0">
                    Showing top {cards?.length || 0} assets
                </div>
        </div>
                {isLoading ? (
                    <div className="p-12 text-center">
                        <div className="animate-spin w-6 h-6 border-2 border-primary border-t-transparent rounded-full mx-auto mb-4"></div>
                        <div className="text-xs uppercase text-muted-foreground animate-pulse">Loading market stream...</div>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm text-left">
                            <thead className="text-xs uppercase bg-muted/30 text-muted-foreground border-b border-border">
                                {table.getHeaderGroups().map(headerGroup => (
                                    <tr key={headerGroup.id}>
                                        {headerGroup.headers.map(header => (
                                        <th key={header.id} className="px-4 py-3 font-medium whitespace-nowrap hover:bg-muted/50 transition-colors">
                                                {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                                            </th>
                                        ))}
                                    </tr>
                                ))}
                            </thead>
                            <tbody className="divide-y divide-border/50">
                                {table.getRowModel().rows?.length ? (
                                    table.getRowModel().rows.map(row => (
                                        <tr 
                                            key={row.id} 
                                            className="hover:bg-muted/30 transition-colors cursor-pointer group"
                                            onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: String(row.original.id) } })}
                                        >
                                            {row.getVisibleCells().map(cell => (
                                            <td key={cell.id} className="px-2 md:px-4 py-3 whitespace-nowrap">
                                                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                                </td>
                                            ))}
                                        </tr>
                                    ))
                                ) : (
                                    <tr>
                                        <td colSpan={columns.length} className="h-32 text-center text-muted-foreground text-xs uppercase">
                                            No market data found.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                )}
        </div>
      </div>
    </div>
  )
}