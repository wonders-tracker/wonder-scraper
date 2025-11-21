import { createRoute, redirect, useNavigate, Link } from '@tanstack/react-router'
import { auth } from '../utils/auth'
import { api } from '../utils/auth'
import { useQuery } from '@tanstack/react-query'
import { ColumnDef, flexRender, getCoreRowModel, useReactTable, getSortedRowModel, SortingState, getFilteredRowModel } from '@tanstack/react-table'
import { useState, useMemo } from 'react'
import { ArrowUpDown, Search, ArrowUp, ArrowDown, LayoutDashboard, LineChart, Wallet, Settings, User, Server, Calendar } from 'lucide-react'
import clsx from 'clsx'
import { Route as rootRoute } from './__root'

// Updated Type Definition including placeholder fields
type Card = {
  id: number
  name: string
  set_name: string
  rarity_id: number
  // Optional fields that might come from backend logic or joins
  latest_price?: number
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
    queryKey: ['cards', timePeriod],
    queryFn: async () => {
      const data = await api.get(`cards?limit=100&time_period=${timePeriod}`).json<Card[]>()
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
          volume_usd_24h: (c.volume_24h ?? 0) * (c.latest_price ?? 0), // Calculate dollar volume
          highest_bid: (c as any).highest_bid ?? 0
      })).filter(c => (c.latest_price && c.latest_price > 0) || (c.volume_24h && c.volume_24h > 0)) // Filter out 0 listings
    },
    staleTime: 5 * 60 * 1000, // 5 minutes - data stays fresh
    cacheTime: 30 * 60 * 1000, // 30 minutes - cache persists
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
          <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-foreground">{row.getValue('name')}</span>
                <span className="px-1.5 py-0.5 rounded text-[8px] uppercase font-semibold bg-muted/30 text-muted-foreground border border-border">
                  {productType}
                </span>
              </div>
              <div className="text-xs text-muted-foreground uppercase">{row.original.set_name}</div>
          </div>
        )
      },
    },
    {
      accessorKey: 'latest_price',
      header: ({ column }) => (
        <button
          className="flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs ml-auto"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          Price
          <ArrowUpDown className="h-3 w-3" />
        </button>
      ),
      cell: ({ row }) => {
          const price = row.original.latest_price
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
            className="flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs ml-auto"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Vol ($)
            <ArrowUpDown className="h-3 w-3" />
          </button>
        ),
        cell: ({ row }) => {
            const volUsd = row.original.volume_usd_24h || 0
            return (
                <div className="text-right font-mono text-xs text-muted-foreground">
                    {volUsd > 0 ? `$${volUsd.toFixed(2)}` : '---'}
                </div>
            )
        }
    },
    {
        accessorKey: 'lowest_ask',
        header: ({ column }) => (
          <button
            className="flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs text-muted-foreground ml-auto"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Low Ask
            <ArrowUpDown className="h-3 w-3" />
          </button>
        ),
        cell: ({ row }) => <div className="text-right font-mono text-xs text-muted-foreground">{row.original.lowest_ask ? `$${Number(row.original.lowest_ask).toFixed(2)}` : '---'}</div>
    },
    {
        accessorKey: 'max_price',
        header: ({ column }) => (
          <button
            className="flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs text-muted-foreground ml-auto"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Highest Sale
            <ArrowUpDown className="h-3 w-3" />
          </button>
        ),
        cell: ({ row }) => <div className="text-right font-mono text-xs text-emerald-600">{row.original.max_price ? `$${Number(row.original.max_price).toFixed(2)}` : '---'}</div>
    },
    {
        accessorKey: 'inventory',
        header: ({ column }) => (
          <button
            className="flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs text-muted-foreground ml-auto"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Inv
            <ArrowUpDown className="h-3 w-3" />
          </button>
        ),
        cell: ({ row }) => <div className="text-right font-mono text-xs text-muted-foreground">{row.original.inventory}</div>
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
    <div className="p-4 min-h-screen bg-background text-foreground font-mono">
      {/* Top Bar */}
      <div className="flex items-center justify-between mb-6 border-b border-border pb-4">
        <div className="flex items-center gap-4">
            <h1 className="text-xl font-bold tracking-tight uppercase">Wonder Scraper <span className="text-xs font-normal text-muted-foreground bg-muted px-1 rounded">BETA</span></h1>
        </div>
        
        <div className="flex gap-3">
            <div className="relative w-96">
                 <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                 <input 
                    type="text" 
                    placeholder="SEARCH (CMD+K)" 
                    className="w-full bg-muted/50 pl-9 pr-4 py-2 rounded border border-border text-sm focus:outline-none focus:ring-1 focus:ring-primary placeholder:text-muted-foreground/50"
                    value={globalFilter}
                    onChange={e => setGlobalFilter(e.target.value)}
                 />
            </div>
            
            <div className="relative flex items-center gap-2">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <select 
                    className="bg-muted/50 px-3 py-2 rounded border border-border text-sm focus:outline-none focus:ring-1 focus:ring-primary uppercase font-mono cursor-pointer hover:bg-muted transition-colors"
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
        
        <div className="flex gap-4 items-center">
            <div className="text-xs text-muted-foreground">
                <span className="w-2 h-2 rounded-full bg-green-500 inline-block mr-2"></span>
                System Online
            </div>
            {user ? (
                <>
                    <div className="h-4 w-px bg-border"></div>
                    <div className="text-xs font-bold uppercase">{user.email}</div>
                    <button onClick={() => auth.logout()} className="text-xs uppercase hover:text-primary transition-colors text-muted-foreground">Logout</button>
                </>
            ) : (
                <>
                    <div className="h-4 w-px bg-border"></div>
                    <Link to="/login" className="text-xs uppercase hover:text-primary transition-colors text-muted-foreground font-bold">Login</Link>
                </>
            )}
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Left Sidebar */}
        <div className="col-span-2 border-r border-border pr-4 hidden md:block h-[calc(100vh-100px)] sticky top-20">
            <nav className="space-y-1">
                <Link to="/" className="flex items-center gap-3 px-3 py-2 bg-muted/50 text-foreground rounded border border-border text-xs font-bold uppercase">
                    <LayoutDashboard className="w-4 h-4" />
                    <span>Dashboard</span>
                </Link>
                <Link to="/market" className="flex items-center gap-3 px-3 py-2 text-muted-foreground hover:text-foreground hover:bg-muted/30 rounded transition-colors text-xs uppercase">
                    <LineChart className="w-4 h-4" />
                    Market Analysis
                </Link>
                {user && (
                    <>
                        <Link to="/portfolio" className="flex items-center gap-3 px-3 py-2 text-muted-foreground hover:text-foreground hover:bg-muted/30 rounded transition-colors text-xs uppercase">
                            <Wallet className="w-4 h-4" />
                            Portfolio
                        </Link>
                        <Link to="/profile" className="flex items-center gap-3 px-3 py-2 text-muted-foreground hover:text-foreground hover:bg-muted/30 rounded transition-colors text-xs uppercase">
                            <User className="w-4 h-4" />
                            Profile
                        </Link>
                    </>
                )}
                
                {/* Admin Only Section */}
                {user?.is_superuser && (
                    <>
                        <div className="pt-6 pb-2 text-[10px] uppercase text-muted-foreground font-bold tracking-widest border-t border-border mt-4">System Admin</div>
                        <a href="#" className="flex items-center gap-3 px-3 py-2 text-muted-foreground hover:text-foreground hover:bg-muted/30 rounded transition-colors text-xs uppercase">
                            <Server className="w-4 h-4" />
                            Scraper Status
                        </a>
                        <a href="#" className="flex items-center gap-3 px-3 py-2 text-muted-foreground hover:text-foreground hover:bg-muted/30 rounded transition-colors text-xs uppercase">
                            <Settings className="w-4 h-4" />
                            Settings
                        </a>
                    </>
                )}
            </nav>
        </div>
        
        {/* Main Content */}
        <div className="col-span-12 md:col-span-8">
             <div className="border border-border rounded bg-card overflow-hidden">
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
                                            <th key={header.id} className="px-4 py-3 font-medium">
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
                                                <td key={cell.id} className="px-4 py-3 whitespace-nowrap">
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

        {/* Right Sidebar */}
        <div className="col-span-12 md:col-span-2 border-l border-border pl-4 hidden md:block h-[calc(100vh-100px)] sticky top-20 overflow-y-auto">
            {/* Time Period Selector */}
            <div className="mb-4">
                <select 
                    className="w-full bg-card border border-border rounded px-2 py-1.5 text-[10px] uppercase font-bold focus:outline-none focus:border-primary"
                    value={timePeriod}
                    onChange={(e) => setTimePeriod(e.target.value)}
                >
                    <option value="24h">24 Hours</option>
                    <option value="7d">7 Days</option>
                    <option value="30d">30 Days</option>
                    <option value="90d">90 Days</option>
                    <option value="all">All Time</option>
                </select>
            </div>
            
            <h3 className="text-[10px] font-bold uppercase text-muted-foreground mb-4 tracking-widest border-b border-border pb-2">Market Pulse</h3>
            
            {/* Market Metrics */}
            <div className="mb-6 space-y-2">
                <div className="bg-card border border-border rounded p-2">
                    <div className="text-[9px] text-muted-foreground uppercase mb-1">Total Volume</div>
                    <div className="text-lg font-mono font-bold">{marketMetrics.totalVolume}</div>
                    <div className="text-[9px] text-muted-foreground">${Number(marketMetrics.totalVolumeUSD).toFixed(0)}</div>
                </div>
                <div className="bg-card border border-border rounded p-2">
                    <div className="text-[9px] text-muted-foreground uppercase mb-1">Sale Velocity</div>
                    <div className="text-lg font-mono font-bold">{Number(marketMetrics.avgVelocity).toFixed(2)}</div>
                    <div className="text-[9px] text-muted-foreground">sales/card/day</div>
                </div>
            </div>
            
            <div className="mb-6">
                <h4 className="text-xs font-bold uppercase mb-3 flex items-center gap-2">
                    <ArrowUp className="w-3 h-3 text-emerald-500" /> 
                    Top Gainers ({timePeriod})
                </h4>
                <div className="space-y-2">
                    {topGainers.length > 0 ? topGainers.map(c => (
                        <div key={c.id} className="text-xs border border-border p-2 rounded bg-card/50 cursor-pointer hover:border-primary transition-colors" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: String(c.id) } })}>
                            <div className="flex justify-between items-start mb-1">
                                <span className="font-bold truncate w-20">{c.name}</span>
                                <span className="text-emerald-500 font-mono bg-emerald-900/20 px-1 rounded text-[10px]">+{Number(c.price_delta_24h || 0).toFixed(1)}%</span>
                            </div>
                            <div className="text-[10px] text-muted-foreground uppercase truncate">{c.set_name}</div>
                        </div>
                    )) : <div className="text-xs text-muted-foreground italic p-2">No gainers recorded.</div>}
                </div>
            </div>
            
            <div className="mb-6">
                <h4 className="text-xs font-bold uppercase mb-3 flex items-center gap-2">
                    <ArrowDown className="w-3 h-3 text-red-500" /> 
                    Top Losers ({timePeriod})
                </h4>
                <div className="space-y-2">
                    {topLosers.length > 0 ? topLosers.map(c => (
                        <div key={c.id} className="text-xs border border-border p-2 rounded bg-card/50 cursor-pointer hover:border-primary transition-colors" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: String(c.id) } })}>
                            <div className="flex justify-between items-start mb-1">
                                <span className="font-bold truncate w-20">{c.name}</span>
                                <span className="text-red-500 font-mono bg-red-900/20 px-1 rounded text-[10px]">{Number(c.price_delta_24h || 0).toFixed(1)}%</span>
                            </div>
                            <div className="text-[10px] text-muted-foreground uppercase truncate">{c.set_name}</div>
                        </div>
                    )) : <div className="text-xs text-muted-foreground italic p-2">No losers recorded.</div>}
                </div>
            </div>
            
            <div>
                <h4 className="text-xs font-bold uppercase mb-3 flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full border border-primary flex items-center justify-center">
                        <div className="w-1 h-1 bg-primary rounded-full"></div>
                    </div>
                    Volume Leaders
                </h4>
                <div className="space-y-3">
                    {topVolume.length > 0 ? topVolume.map((c, i) => (
                        <div key={c.id} className="text-xs border border-border p-3 rounded bg-card/50 cursor-pointer hover:border-primary transition-colors" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: String(c.id) } })}>
                            <div className="flex justify-between items-start mb-1">
                                <span className="font-bold truncate w-20">{c.name}</span>
                                <span className="text-foreground font-mono">{c.volume_24h}</span>
                            </div>
                            <div className="w-full bg-muted rounded-full h-1 mt-2 overflow-hidden">
                                <div className="bg-primary h-full" style={{ width: `${Math.min(((c.volume_24h || 0) / (topVolume[0].volume_24h || 1)) * 100, 100)}%` }}></div>
                            </div>
                        </div>
                    )) : <div className="text-xs text-muted-foreground italic">No volume data yet.</div>}
                </div>
            </div>
        </div>
      </div>
    </div>
  )
}
