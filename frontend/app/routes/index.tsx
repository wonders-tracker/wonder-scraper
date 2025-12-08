import { createRoute, useNavigate, Link } from '@tanstack/react-router'
import { api, auth } from '../utils/auth'
import { analytics } from '~/services/analytics'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ColumnDef, flexRender, getCoreRowModel, useReactTable, getSortedRowModel, SortingState, getFilteredRowModel, getPaginationRowModel } from '@tanstack/react-table'
import { useState, useMemo, useEffect, useCallback } from 'react'
import { ArrowUpDown, Search, ArrowUp, ArrowDown, Calendar, TrendingUp, DollarSign, BarChart3, LayoutDashboard, ChevronLeft, ChevronRight, Plus, Package, Layers, Gem, Archive, Info } from 'lucide-react'
import clsx from 'clsx'
import { Route as rootRoute } from './__root'
import { useTimePeriod } from '../context/TimePeriodContext'
import { AddToPortfolioModal } from '../components/AddToPortfolioModal'

// Truncate treatment for display if too long
function simplifyTreatmentForDisplay(treatment: string): string {
    if (!treatment) return ''
    // Truncate if longer than 25 chars
    if (treatment.length > 25) {
        return treatment.substring(0, 22) + '...'
    }
    return treatment
}

// Updated Type Definition with clean field names
type Card = {
  id: number
  slug?: string // SEO-friendly URL slug
  name: string
  set_name: string
  rarity_id: number
  rarity_name?: string // Rarity display name from backend join
  product_type?: string // Single, Box, Pack, Bundle, Proof, Lot

  // === PRICES (clear hierarchy) ===
  floor_price?: number // Avg of 4 lowest sales - THE standard price
  vwap?: number // Volume Weighted Average Price = SUM(price)/COUNT
  latest_price?: number // Most recent sale price
  lowest_ask?: number // Cheapest active listing
  max_price?: number // Highest confirmed sale
  fair_market_price?: number // FMP calculated from formula

  // === VOLUME & INVENTORY ===
  volume?: number // Sales count for selected time period
  inventory?: number
  volume_usd?: number // Calculated dollar volume

  // === DELTAS (% changes) ===
  price_delta?: number // Last sale vs rolling avg (%)
  floor_delta?: number // Last sale vs floor price (%)

  // === METADATA ===
  last_treatment?: string // Treatment of last sale (e.g., "Classic Foil")

  // === DEPRECATED (backwards compat) ===
  volume_30d?: number // @deprecated: use 'volume'
  price_delta_24h?: number // @deprecated: use 'price_delta'
  last_sale_treatment?: string // @deprecated: use 'last_treatment'
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
  const [sorting, setSorting] = useState<SortingState>([{ id: 'volume', desc: true }])
  const [globalFilter, setGlobalFilter] = useState('')
  const { timePeriod, setTimePeriod } = useTimePeriod()
  const [productType, setProductType] = useState<string>('all')
  const [hideLowSignal, setHideLowSignal] = useState<boolean>(true)  // Hide low signal cards by default
  const [trackingCard, setTrackingCard] = useState<Card | null>(null)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // Debounced search tracking
  useEffect(() => {
    if (!globalFilter || globalFilter.length < 2) return
    const timer = setTimeout(() => {
      analytics.trackSearch(globalFilter)
    }, 1000) // Track after 1s of no typing
    return () => clearTimeout(timer)
  }, [globalFilter])

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
      const data = await api.get(`cards/?limit=500&time_period=${timePeriod}${typeParam}`).json<Card[]>()
      return data.map(c => ({
          ...c,
          // Use new field names with fallback to deprecated for backwards compat
          latest_price: c.latest_price ?? 0,
          volume: c.volume ?? c.volume_30d ?? 0,
          inventory: c.inventory ?? 0,
          price_delta: c.price_delta ?? c.price_delta_24h ?? 0,
          last_treatment: c.last_treatment ?? c.last_sale_treatment ?? '',
          // Calculate dollar volume
          volume_usd: (c.volume ?? c.volume_30d ?? 0) * (c.floor_price ?? c.vwap ?? c.latest_price ?? 0),
      }))
      .filter(c => (c.latest_price && c.latest_price > 0) || ((c.volume ?? c.volume_30d ?? 0) > 0) || (c.lowest_ask && c.lowest_ask > 0)) // Filter out items with no data
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
      sortingFn: (a, b) => ((a.original.floor_price ?? 0) - (b.original.floor_price ?? 0)),
      header: ({ column }) => (
        <button
          className="flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs ml-auto"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          title="Floor Price (avg of 4 lowest sales in 30d)"
        >
          Floor
          <ArrowUpDown className="h-3 w-3" />
        </button>
      ),
      cell: ({ row }) => {
          // Use floor_price, fallback to vwap if no floor
          const floorPrice = row.original.floor_price || row.original.vwap
          const hasFloor = !!floorPrice && floorPrice > 0
          const delta = row.original.price_delta ?? row.original.price_delta_24h ?? 0
          return (
            <div className="text-right flex items-center justify-end gap-2">
                <span className="font-mono text-sm">
                    {hasFloor ? `$${floorPrice.toFixed(2)}` : '---'}
                </span>
                {hasFloor && delta !== 0 && (
                    <span className={clsx(
                        "text-[10px] font-mono px-1 py-0.5 rounded",
                        delta > 0 ? "text-emerald-400 bg-emerald-500/10" :
                        "text-red-400 bg-red-500/10"
                    )}>
                        {delta > 0 ? '↑' : '↓'}{Math.abs(delta).toFixed(1)}%
                    </span>
                )}
            </div>
          )
      }
    },
    {
      accessorKey: 'vwap', // Volume Weighted Average Price
      sortingFn: (a, b) => ((a.original.vwap ?? 0) - (b.original.vwap ?? 0)),
      header: ({ column }) => (
        <div className="relative group flex items-center justify-center gap-1">
          <button
            className="flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            VWAP
            <ArrowUpDown className="h-3 w-3" />
          </button>
          <Info className="h-3 w-3 text-muted-foreground cursor-help" />
          <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-2 bg-zinc-900 text-white text-xs rounded shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-[100]">
            Volume Weighted Average Price
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 border-4 border-transparent border-b-zinc-900"></div>
          </div>
        </div>
      ),
      cell: ({ row }) => {
          const vwap = row.original.vwap
          const hasVwap = !!vwap && vwap > 0
          return (
            <div className="text-center font-mono text-sm">
                {hasVwap ? `$${vwap.toFixed(2)}` : '---'}
            </div>
          )
      }
    },
    {
        accessorKey: 'volume',
        sortingFn: (a, b) => ((a.original.volume ?? 0) - (b.original.volume ?? 0)),
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
            const vol = row.original.volume ?? row.original.volume_30d ?? 0
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
        sortingFn: (a, b) => ((a.original.latest_price ?? 0) - (b.original.latest_price ?? 0)),
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
            const rawTreatment = row.original.last_treatment ?? row.original.last_sale_treatment ?? ''
            const treatment = simplifyTreatmentForDisplay(rawTreatment)
            return (
                <div className="flex flex-col items-end">
                    <span className="font-mono text-sm">{price > 0 ? `$${price.toFixed(2)}` : '---'}</span>
                    {treatment && (
                        <span
                            className="text-[9px] text-muted-foreground max-w-[80px] truncate"
                            title={rawTreatment}
                        >
                            {treatment}
                        </span>
                    )}
                </div>
            )
        }
    },
    {
        accessorKey: 'max_price',
        sortingFn: (a, b) => ((a.original.max_price ?? 0) - (b.original.max_price ?? 0)),
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
        sortingFn: (a, b) => ((a.original.lowest_ask ?? 0) - (b.original.lowest_ask ?? 0)),
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
        sortingFn: (a, b) => ((a.original.inventory ?? 0) - (b.original.inventory ?? 0)),
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
            const vol = row.original.volume ?? row.original.volume_30d ?? 0
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
    // Low signal = volume is 0 (no confirmed sales in selected period)
    return cards.filter(c => (c.volume ?? c.volume_30d ?? 0) > 0)
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
      const getDelta = (c: Card) => c.price_delta ?? c.price_delta_24h ?? 0
      return [...cards]
          .filter(c => (c.latest_price || 0) > 0 && getDelta(c) > 0.01)
          .sort((a, b) => getDelta(b) - getDelta(a))
          .slice(0, 5)
  }, [cards])

  const topLosers = useMemo(() => {
      if (!cards) return []
      // Lower threshold to -0.01% to capture more losers
      const getDelta = (c: Card) => c.price_delta ?? c.price_delta_24h ?? 0
      return [...cards]
          .filter(c => (c.latest_price || 0) > 0 && getDelta(c) < -0.01)
          .sort((a, b) => getDelta(a) - getDelta(b))
          .slice(0, 5)
  }, [cards])

  const topVolume = useMemo(() => {
      if (!cards) return []
      const getVolume = (c: Card) => c.volume ?? c.volume_30d ?? 0
      return [...cards]
          .sort((a, b) => getVolume(b) - getVolume(a))
          .slice(0, 5)
  }, [cards])
  
  // Calculate market metrics
  const marketMetrics = useMemo(() => {
      if (!cards) return { totalVolume: 0, totalVolumeUSD: 0, avgVelocity: 0 }

      const getVolume = (c: Card) => c.volume ?? c.volume_30d ?? 0
      const totalVolume = cards.reduce((sum, c) => sum + getVolume(c), 0)
      const totalVolumeUSD = cards.reduce((sum, c) => sum + (getVolume(c) * (c.floor_price || c.latest_price || 0)), 0)

      // Sale velocity = avg sales per card per day
      // Normalize to daily rate based on time period
      const timePeriodDays = timePeriod === '7d' ? 7 : timePeriod === '30d' ? 30 : timePeriod === '90d' ? 90 : 30
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
                                onChange={e => {
                                    setProductType(e.target.value)
                                    analytics.trackFilterApplied('product_type', e.target.value)
                                }}
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
                    onChange={e => {
                        setTimePeriod(e.target.value)
                        analytics.trackFilterApplied('time_period', e.target.value)
                    }}
                >
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

      {/* Add to Portfolio Drawer */}
      {trackingCard && (
        <AddToPortfolioModal
          card={{
            id: trackingCard.id,
            name: trackingCard.name,
            set_name: trackingCard.set_name,
            floor_price: trackingCard.floor_price,
            latest_price: trackingCard.latest_price,
            product_type: trackingCard.product_type
          }}
          isOpen={!!trackingCard}
          onClose={() => setTrackingCard(null)}
        />
      )}
    </div>
  )
}