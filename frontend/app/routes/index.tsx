import { createRoute, useNavigate, Link } from '@tanstack/react-router'
import { api, auth } from '../utils/auth'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ColumnDef, flexRender, getCoreRowModel, useReactTable, getSortedRowModel, SortingState, getFilteredRowModel, getPaginationRowModel } from '@tanstack/react-table'
import { useState, useMemo, useEffect } from 'react'
import { ArrowUpDown, Search, ArrowUp, ArrowDown, Calendar, TrendingUp, DollarSign, BarChart3, LayoutDashboard, ChevronLeft, ChevronRight, Plus, X, Package, Layers, Gem, Archive, Info } from 'lucide-react'
import clsx from 'clsx'
import { Route as rootRoute } from './__root'

// Updated Type Definition including placeholder fields
type Card = {
  id: number
  slug?: string // SEO-friendly URL slug
  name: string
  set_name: string
  rarity_id: number
  rarity_name?: string // Rarity display name from backend join
  // Optional fields that might come from backend logic or joins
  latest_price?: number
  vwap?: number // Volume Weighted Average Price
  floor_price?: number // Avg of 4 lowest sales (30d) - THE standard price
  fair_market_price?: number // FMP calculated from formula
  volume_30d?: number
  price_delta_24h?: number // Placeholder for delta
  lowest_ask?: number
  inventory?: number
  volume_usd_24h?: number // New field for dollar volume
  product_type?: string // Single, Box, Pack, Bundle, Proof, Lot
  max_price?: number // Highest confirmed sale
  last_sale_treatment?: string // Treatment/variant of last sale
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
  const [sorting, setSorting] = useState<SortingState>([{ id: 'volume_30d', desc: true }])
  const [globalFilter, setGlobalFilter] = useState('')
  const [timePeriod, setTimePeriod] = useState<string>('24h')
  const [productType, setProductType] = useState<string>('all')
  const [hideLowSignal, setHideLowSignal] = useState<boolean>(true)  // Hide low signal cards by default
  const [trackingCard, setTrackingCard] = useState<Card | null>(null)
  const [trackForm, setTrackForm] = useState({ quantity: 1, purchase_price: 0 })
  const navigate = useNavigate()
  const queryClient = useQueryClient()

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

  // Mutation for adding cards to portfolio
  const addToPortfolioMutation = useMutation({
      mutationFn: async (data: { card_id: number, quantity: number, purchase_price: number }) => {
          return await api.post('portfolio/', { json: data }).json()
      },
      onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ['portfolio'] })
          setTrackingCard(null)
          setTrackForm({ quantity: 1, purchase_price: 0 })
      }
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
          volume_30d: c.volume_30d ?? 0,
          inventory: c.inventory ?? 0,
          // These fields are not yet in schema/DB so we mock them or derive
          // high_bid: (c.lowest_ask ?? c.latest_price ?? 0) * 0.9, // Removed mock high_bid
          // low_ask: c.lowest_ask ?? (c.latest_price ?? 0) * 1.1, // Removed mock low_ask
          // Only show delta if price exists
          price_delta_24h: c.price_delta_24h ?? 0,
          volume_usd_24h: (c.volume_30d ?? 0) * ((c as any).floor_price ?? c.vwap ?? c.latest_price ?? 0), // Calculate dollar volume using floor_price
          highest_bid: (c as any).highest_bid ?? 0
      }))
      .filter(c => (c.latest_price && c.latest_price > 0) || (c.volume_30d && c.volume_30d > 0) || (c.lowest_ask && c.lowest_ask > 0)) // Filter out items with no data
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
        const isSingle = productType === 'Single'
        const rarity = row.original.rarity_name || ''

        // Icon component by product type
        const IconComponent = productType === 'Box' ? Package
          : productType === 'Pack' ? Layers
          : productType === 'Proof' ? Gem
          : productType === 'Lot' ? Archive
          : null

        return (
          <div className="max-w-[180px] md:max-w-none">
              <div className="flex items-center gap-1.5">
                <span className="font-bold text-foreground truncate text-sm" title={row.getValue('name')}>{row.getValue('name')}</span>
                {isSingle && rarity && (
                  <span className={clsx(
                    "shrink-0 text-[8px] font-bold uppercase px-1 py-0.5 rounded",
                    rarity === 'Mythic' ? 'text-amber-900 bg-amber-400' :
                    rarity === 'Legendary' ? 'text-orange-900 bg-orange-400' :
                    rarity === 'Epic' ? 'text-purple-900 bg-purple-400' :
                    rarity === 'Rare' ? 'text-blue-900 bg-blue-400' :
                    rarity === 'Uncommon' ? 'text-emerald-900 bg-emerald-400' :
                    'text-zinc-900 bg-zinc-400'
                  )} title={rarity}>
                    {rarity}
                  </span>
                )}
                {!isSingle && IconComponent && (
                  <span className="shrink-0 text-muted-foreground/40" title={productType}>
                    <IconComponent className="w-3.5 h-3.5" />
                  </span>
                )}
              </div>
              <div className="text-[10px] text-muted-foreground/70 uppercase truncate">{row.original.set_name}</div>
          </div>
        )
      },
    },
    {
      accessorKey: 'floor_price', // Floor price = avg of 4 lowest sales (30d)
      header: ({ column }) => (
        <button
          className="flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs ml-auto"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          Floor
          <ArrowUpDown className="h-3 w-3" />
        </button>
      ),
      cell: ({ row }) => {
          // Price priority: floor_price > vwap > latest_price > lowest_ask
          const floorPrice = row.original.floor_price
          const salePrice = floorPrice || row.original.vwap || row.original.latest_price
          const askPrice = row.original.lowest_ask || 0
          const price = salePrice || askPrice
          const isAskOnly = !salePrice && askPrice > 0
          const delta = row.original.price_delta_24h || 0
          const hasPrice = price && price > 0

          return (
            <div className="text-right flex items-center justify-end gap-2">
                <span className={clsx("font-mono text-sm font-semibold", isAskOnly && "text-muted-foreground")}>
                    {hasPrice ? `$${price.toFixed(2)}` : '---'}
                    {isAskOnly && <span className="text-[9px] ml-1">(ask)</span>}
                </span>
                {hasPrice && delta !== 0 ? (
                    <span className={clsx(
                        "text-[10px] font-mono px-1 py-0.5 rounded",
                        delta > 0 ? "text-emerald-400 bg-emerald-500/10" :
                        "text-red-400 bg-red-500/10"
                    )}>
                        {delta > 0 ? '↑' : '↓'}{Math.abs(delta).toFixed(1)}%
                    </span>
                ) : hasPrice && (
                    <span className="text-muted-foreground/30 cursor-help" title="Stable price - based on recent lowest sales">
                        <Info className="w-3 h-3" />
                    </span>
                )}
            </div>
          )
      }
    },
    {
        accessorKey: 'volume_30d',
        header: ({ column }) => (
          <button
            className="flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs ml-auto"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Vol
            <ArrowUpDown className="h-3 w-3" />
          </button>
        ),
        cell: ({ row }) => {
            const vol = row.original.volume_30d || 0
            // Chevron indicators based on volume thresholds
            let chevrons = ''
            let colorClass = 'text-muted-foreground'
            if (vol >= 30) {
                chevrons = '▲▲'
                colorClass = 'text-emerald-500'
            } else if (vol >= 10) {
                chevrons = '▲'
                colorClass = 'text-emerald-400'
            } else if (vol > 0 && vol < 3) {
                chevrons = '▼'
                colorClass = 'text-red-400'
            } else if (vol === 0) {
                chevrons = '▼▼'
                colorClass = 'text-red-500'
            }

            return (
                <div className="flex items-center justify-end gap-1 font-mono text-sm">
                    <span>{vol}</span>
                    {chevrons && <span className={clsx("text-[10px]", colorClass)}>{chevrons}</span>}
                </div>
            )
        }
    },
    {
        accessorKey: 'latest_price',
        header: ({ column }) => (
          <button
            className="flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs ml-auto"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Last Sale
            <ArrowUpDown className="h-3 w-3" />
          </button>
        ),
        cell: ({ row }) => {
            const price = row.original.latest_price || 0
            const treatment = (row.original as any).last_sale_treatment || ''
            return (
                <div className="flex flex-col items-end">
                    <span className="font-mono text-sm">{price > 0 ? `$${price.toFixed(2)}` : '---'}</span>
                    {treatment && <span className="text-[9px] text-muted-foreground">{treatment}</span>}
                </div>
            )
        }
    },
    {
        accessorKey: 'max_price',
        header: ({ column }) => (
          <button
            className="hidden md:flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs ml-auto"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            High
            <ArrowUpDown className="h-3 w-3" />
          </button>
        ),
        cell: ({ row }) => {
            const high = row.original.max_price || 0
            return <div className="hidden md:block text-right font-mono text-sm text-emerald-500">{high > 0 ? `$${high.toFixed(2)}` : '---'}</div>
        }
    },
    {
        accessorKey: 'lowest_ask',
        header: ({ column }) => (
          <button
            className="hidden md:flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs ml-auto"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Ask
            <ArrowUpDown className="h-3 w-3" />
          </button>
        ),
        cell: ({ row }) => {
            const ask = row.original.lowest_ask || 0
            return <div className="hidden md:block text-right font-mono text-sm">{ask > 0 ? `$${ask.toFixed(2)}` : '---'}</div>
        }
    },
    {
        accessorKey: 'inventory',
        header: ({ column }) => (
          <button
            className="hidden lg:flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs ml-auto"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Listings
            <ArrowUpDown className="h-3 w-3" />
          </button>
        ),
        cell: ({ row }) => {
            const inv = row.original.inventory || 0
            const vol = row.original.volume_30d || 0
            // Time-to-sell: days to clear current inventory at current velocity
            const daysToSell = vol > 0 ? (inv / vol) : null
            const daysDisplay = daysToSell !== null
                ? daysToSell < 1 ? '<1d' : `~${Math.round(daysToSell)}d`
                : '—'
            // Color code: fast sell = green, slow = red
            const daysClass = daysToSell !== null
                ? daysToSell < 3 ? 'text-emerald-500'
                : daysToSell > 14 ? 'text-red-400'
                : 'text-muted-foreground'
                : 'text-muted-foreground'
            return (
                <div className="hidden lg:block text-right">
                    <div className="font-mono text-sm">{inv}</div>
                    <div className={clsx("text-[9px]", daysClass)}>{daysDisplay} sell</div>
                </div>
            )
        }
    },
    {
        id: 'track',
        header: () => <div className="text-xs uppercase tracking-wider text-muted-foreground text-center">Track</div>,
        cell: ({ row }) => {
            return (
                <div className="flex justify-center">
                    <button
                        onClick={(e) => {
                            e.stopPropagation()
                            if (!user) {
                                // Redirect to login if not logged in
                                navigate({ to: '/login' })
                                return
                            }
                            setTrackingCard(row.original)
                            setTrackForm({ quantity: 1, purchase_price: row.original.floor_price || row.original.vwap || row.original.latest_price || row.original.lowest_ask || 0 })
                        }}
                        className="p-1.5 rounded border border-border hover:bg-primary hover:text-primary-foreground transition-colors group"
                        title={user ? "Add to Portfolio" : "Login to track"}
                    >
                        <Plus className="w-3.5 h-3.5" />
                    </button>
                </div>
            )
        }
    }
  ], [user])

  // Filter out low signal cards (no confirmed sales, only ask prices)
  const filteredCards = useMemo(() => {
    if (!cards) return []
    if (!hideLowSignal) return cards
    // Low signal = volume_30d is 0 (no confirmed sales in 30 days)
    return cards.filter(c => (c.volume_30d ?? 0) > 0)
  }, [cards, hideLowSignal])

  const table = useReactTable({
    data: filteredCards,
    columns,
    getCoreRowModel: getCoreRowModel(),
    onSortingChange: setSorting,
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    onGlobalFilterChange: setGlobalFilter,
    state: {
      sorting,
      globalFilter,
    },
    initialState: {
      pagination: {
        pageSize: 75, // Increased from 50 due to compact rows
      },
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
          .sort((a, b) => (b.volume_30d || 0) - (a.volume_30d || 0))
          .slice(0, 5)
  }, [cards])
  
  // Calculate market metrics
  const marketMetrics = useMemo(() => {
      if (!cards) return { totalVolume: 0, totalVolumeUSD: 0, avgVelocity: 0 }

      const totalVolume = cards.reduce((sum, c) => sum + (c.volume_30d || 0), 0)
      const totalVolumeUSD = cards.reduce((sum, c) => sum + ((c.volume_30d || 0) * (c.floor_price || c.latest_price || 0)), 0)
      
      // Sale velocity = avg sales per card per day
      // For time periods other than 24h, normalize to daily rate
      const timePeriodDays = timePeriod === '24h' ? 1 : timePeriod === '7d' ? 7 : timePeriod === '30d' ? 30 : timePeriod === '90d' ? 90 : 1
      const avgVelocity = cards.length > 0 ? (totalVolume / cards.length / timePeriodDays) : 0
      
      return { totalVolume, totalVolumeUSD, avgVelocity }
  }, [cards, timePeriod])

  return (
    <div className="h-[calc(100vh-3.5rem-2rem)] flex flex-col bg-background text-foreground font-mono">
      <div className="p-4 max-w-[1800px] mx-auto w-full flex-1 flex flex-col overflow-hidden">
        {/* Main Data Table */}
        <div className="border border-border rounded bg-card overflow-hidden flex-1 flex flex-col">
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
                                <option value="Box">Boxes</option>
                                <option value="Pack">Packs</option>
                                <option value="Lot">Lots</option>
                                <option value="Proof">Proofs</option>
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
            {/* Low Signal Filter */}
            <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                    type="checkbox"
                    checked={hideLowSignal}
                    onChange={e => setHideLowSignal(e.target.checked)}
                    className="w-3.5 h-3.5 rounded border-border bg-background text-primary focus:ring-1 focus:ring-primary cursor-pointer"
                />
                <span className="text-xs text-muted-foreground whitespace-nowrap">Hide Low Signal</span>
            </label>
        </div>
        </div>
      </div>

                <div className="text-xs text-muted-foreground font-mono hidden xl:block shrink-0">
                    Showing {filteredCards.length} of {cards?.length || 0} assets
                </div>
        </div>
                {isLoading ? (
                    <div className="p-12 text-center">
                        <div className="animate-spin w-6 h-6 border-2 border-primary border-t-transparent rounded-full mx-auto mb-4"></div>
                        <div className="text-xs uppercase text-muted-foreground animate-pulse">Loading market stream...</div>
                    </div>
                ) : (
                    <>
                        <div className="overflow-auto flex-1">
                            <table className="w-full text-sm text-left">
                                <thead className="text-xs uppercase bg-muted/30 text-muted-foreground border-b border-border sticky top-0 z-10">
                                    {table.getHeaderGroups().map(headerGroup => (
                                        <tr key={headerGroup.id}>
                                            {headerGroup.headers.map(header => (
                                            <th key={header.id} className="px-2 py-1.5 font-medium whitespace-nowrap hover:bg-muted/50 transition-colors bg-muted/30">
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
                                                onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: row.original.slug || String(row.original.id) } })}
                                            >
                                                {row.getVisibleCells().map(cell => (
                                                <td key={cell.id} className="px-2 py-1.5 whitespace-nowrap">
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
                        {/* Pagination */}
                        <div className="border-t border-border px-3 py-2 flex items-center justify-between bg-muted/20">
                            <div className="text-xs text-muted-foreground">
                                Showing {table.getState().pagination.pageIndex * table.getState().pagination.pageSize + 1} to {Math.min((table.getState().pagination.pageIndex + 1) * table.getState().pagination.pageSize, table.getFilteredRowModel().rows.length)} of {table.getFilteredRowModel().rows.length} assets
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => table.previousPage()}
                                    disabled={!table.getCanPreviousPage()}
                                    className="px-3 py-1.5 text-xs font-bold uppercase border border-border rounded hover:bg-muted/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    <ChevronLeft className="w-3.5 h-3.5" />
                                </button>
                                <div className="text-xs font-mono">
                                    Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
                                </div>
                                <button
                                    onClick={() => table.nextPage()}
                                    disabled={!table.getCanNextPage()}
                                    className="px-3 py-1.5 text-xs font-bold uppercase border border-border rounded hover:bg-muted/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    <ChevronRight className="w-3.5 h-3.5" />
                                </button>
                            </div>
                        </div>
                    </>
                )}
        </div>
      </div>

      {/* Track Card Dialog */}
      {trackingCard && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setTrackingCard(null)}>
          <div className="bg-background border border-border rounded-lg max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold uppercase tracking-wider">Add to Portfolio</h3>
              <button onClick={() => setTrackingCard(null)} className="text-muted-foreground hover:text-foreground">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="mb-4">
              <div className="text-xs text-muted-foreground uppercase mb-1">Card</div>
              <div className="font-bold">{trackingCard.name}</div>
              <div className="text-xs text-muted-foreground">{trackingCard.set_name}</div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-xs text-muted-foreground uppercase block mb-1">Quantity</label>
                <input
                  type="number"
                  min="1"
                  value={trackForm.quantity}
                  onChange={(e) => setTrackForm({ ...trackForm, quantity: parseInt(e.target.value) || 1 })}
                  className="w-full bg-background border border-border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div>
                <label className="text-xs text-muted-foreground uppercase block mb-1">Purchase Price (per card)</label>
                <div className="relative">
                  <span className="absolute left-3 top-2 text-muted-foreground">$</span>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={trackForm.purchase_price}
                    onChange={(e) => setTrackForm({ ...trackForm, purchase_price: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-background border border-border rounded pl-7 pr-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
              </div>

              <div className="pt-2 border-t border-border">
                <div className="flex items-center justify-between text-xs mb-2">
                  <span className="text-muted-foreground uppercase">Total Cost</span>
                  <span className="font-mono font-bold">${(trackForm.quantity * trackForm.purchase_price).toFixed(2)}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground uppercase">Current Value</span>
                  <span className="font-mono font-bold">${(trackForm.quantity * (trackingCard.floor_price || trackingCard.vwap || trackingCard.latest_price || trackingCard.lowest_ask || 0)).toFixed(2)}</span>
                </div>
              </div>
            </div>

            <div className="flex gap-2 mt-6">
              <button
                onClick={() => setTrackingCard(null)}
                className="flex-1 px-4 py-2 text-sm font-bold uppercase border border-border rounded hover:bg-muted transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  addToPortfolioMutation.mutate({
                    card_id: trackingCard.id,
                    quantity: trackForm.quantity,
                    purchase_price: trackForm.purchase_price
                  })
                }}
                disabled={addToPortfolioMutation.isPending}
                className="flex-1 px-4 py-2 text-sm font-bold uppercase bg-primary text-primary-foreground rounded hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {addToPortfolioMutation.isPending ? 'Adding...' : 'Add to Portfolio'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}