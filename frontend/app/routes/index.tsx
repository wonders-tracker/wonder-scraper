import { createFileRoute, useNavigate, Link } from '@tanstack/react-router'
import { api, auth } from '../utils/auth'
import { analytics } from '~/services/analytics'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ColumnDef, flexRender, getCoreRowModel, useReactTable, getSortedRowModel, SortingState, getFilteredRowModel, getPaginationRowModel } from '@tanstack/react-table'
import { useState, useMemo, useEffect, useCallback } from 'react'
import { ArrowUpDown, Search, ArrowUp, ArrowDown, Calendar, TrendingUp, DollarSign, BarChart3, LayoutDashboard, ChevronLeft, ChevronRight, Plus, Package, Layers, Gem, Archive, Store, ShoppingCart, ExternalLink, Info } from 'lucide-react'
import clsx from 'clsx'
import { Tooltip } from '../components/ui/tooltip'
import { SimpleDropdown } from '../components/ui/dropdown'
import { useTimePeriod } from '../context/TimePeriodContext'
import { AddToPortfolioModal } from '../components/AddToPortfolioModal'
import { TreatmentBadge } from '../components/TreatmentBadge'

// Card thumbnail that only renders if src provided and loads successfully (prevents layout shift)
function CardThumbnail({ src, alt, className }: { src?: string; alt: string; className: string }) {
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState(false)

  // Don't render anything if no src or error
  if (!src || error) return null

  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      className={clsx(className, !loaded && 'hidden')}
      onLoad={() => setLoaded(true)}
      onError={() => setError(true)}
    />
  )
}

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
  floor_price?: number // Avg of 4 lowest sales - THE standard price (cheapest variant)
  floor_by_variant?: Record<string, number> // Floor price per variant {treatment/subtype: price}
  vwap?: number // Volume Weighted Average Price = SUM(price)/COUNT
  latest_price?: number // Most recent sale price
  lowest_ask?: number // Cheapest active listing (cheapest variant)
  lowest_ask_by_variant?: Record<string, number> // Lowest ask per variant {treatment/subtype: price}
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
  image_url?: string // Card thumbnail URL from blob storage

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

// Individual marketplace listing
type Listing = {
  id: number
  card_id: number
  card_name: string
  card_slug?: string
  card_image_url?: string // Card thumbnail from blob storage
  product_type: string
  title: string
  price: number
  floor_price?: number // Avg of 4 lowest sales for this card
  vwap?: number // Volume weighted avg price (fallback when floor_price unavailable)
  platform: string
  treatment?: string
  traits?: Record<string, string> // NFT traits for OpenSea/Blokpax
  listing_type: 'active' | 'sold'
  condition?: string
  bid_count?: number
  seller_name?: string
  seller_feedback_score?: number
  seller_feedback_percent?: number
  shipping_cost?: number
  grading?: string
  url?: string
  image_url?: string
  sold_date?: string
  scraped_at?: string
  listed_at?: string
}

type ListingsResponse = {
  items: Listing[]
  total: number
  offset: number
  limit: number
  hasMore: boolean
}

export const Route = createFileRoute('/')({
  component: Home,
})

// Tab type for dashboard views
type DashboardTab = 'products' | 'listings'

function Home() {
  const [sorting, setSorting] = useState<SortingState>([{ id: 'volume', desc: true }])
  const [globalFilter, setGlobalFilter] = useState('')
  const { timePeriod, setTimePeriod } = useTimePeriod()
  const [productType, setProductType] = useState<string>('all')
  const [platform, setPlatform] = useState<string>('all')
  const [trackingCard, setTrackingCard] = useState<Card | null>(null)
  const [activeTab, setActiveTab] = useState<DashboardTab>('products')
  // Listings tab state
  const [listingType, setListingType] = useState<string>('active')
  const [listingPlatform, setListingPlatform] = useState<string>('all')
  const [listingProductType, setListingProductType] = useState<string>('all')
  const [listingTreatment, setListingTreatment] = useState<string>('all')
  const [listingTimePeriod, setListingTimePeriod] = useState<string>('all')
  const [listingSearch, setListingSearch] = useState<string>('')
  const [listingSortBy, setListingSortBy] = useState<string>('scraped_at')
  const [listingSortOrder, setListingSortOrder] = useState<'asc' | 'desc'>('desc')
  const [listingPage, setListingPage] = useState<number>(0)
  const LISTINGS_PER_PAGE = 100
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

  // User profile is fetched in root layout and cached
  // We just read from cache here (staleTime in root ensures it's fresh)
  const { data: user } = useQuery({
      queryKey: ['me'],
      queryFn: async () => {
          try {
              return await api.get('users/me').json<UserProfile>()
          } catch {
              return null
          }
      },
      retry: false,
      staleTime: 30 * 60 * 1000, // 30 minutes - user data rarely changes
  })


  const { data: cards, isLoading } = useQuery({
    queryKey: ['cards', timePeriod, productType, platform],
    queryFn: async () => {
      const typeParam = productType !== 'all' ? `&product_type=${productType}` : ''
      const platformParam = platform !== 'all' ? `&platform=${platform}` : ''
      // Load all cards - important ones can be deep in the list
      // slim=true reduces payload by ~50% for faster loading
      const data = await api.get(`cards?limit=500&time_period=${timePeriod}${typeParam}${platformParam}&slim=true`).json<Card[]>()
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
    staleTime: 2 * 60 * 1000, // 2 minutes - fresher feel while respecting 15min scrape interval
    gcTime: 30 * 60 * 1000, // 30 minutes - cache persists
    refetchOnWindowFocus: false, // Don't refetch on tab focus
  })

  // Listings query for the Listings tab (server-side pagination)
  const { data: listingsData, isLoading: listingsLoading, isFetching: listingsFetching } = useQuery({
    queryKey: ['listings', listingType, listingPlatform, listingProductType, listingTreatment, listingTimePeriod, listingSearch, listingSortBy, listingSortOrder, listingPage],
    queryFn: async () => {
      const params = new URLSearchParams()
      params.set('listing_type', listingType)
      params.set('limit', String(LISTINGS_PER_PAGE))
      params.set('offset', String(listingPage * LISTINGS_PER_PAGE))
      params.set('sort_by', listingSortBy)
      params.set('sort_order', listingSortOrder)
      if (listingPlatform !== 'all') params.set('platform', listingPlatform)
      if (listingProductType !== 'all') params.set('product_type', listingProductType)
      if (listingTreatment !== 'all') params.set('treatment', listingTreatment)
      if (listingTimePeriod !== 'all') params.set('time_period', listingTimePeriod)
      if (listingSearch) params.set('search', listingSearch)
      const data = await api.get(`market/listings?${params.toString()}`).json<ListingsResponse>()
      return data
    },
    enabled: activeTab === 'listings', // Only fetch when Listings tab is active
    staleTime: 2 * 60 * 1000, // 2 minutes - listings change more frequently
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev, // Keep previous data while fetching new page
  })

  // Reset to page 0 when filters change
  useEffect(() => {
    setListingPage(0)
  }, [listingType, listingPlatform, listingProductType, listingTreatment, listingTimePeriod, listingSearch, listingSortBy, listingSortOrder])

  // Update default sort when listing type changes
  useEffect(() => {
    if (listingType === 'sold') {
      setListingSortBy('sold_date')
    } else if (listingType === 'active') {
      setListingSortBy('listed_at')
    }
  }, [listingType])

  // Helper to toggle listing sort
  const toggleListingSort = (column: string) => {
    if (listingSortBy === column) {
      setListingSortOrder(listingSortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setListingSortBy(column)
      setListingSortOrder('desc')
    }
  }

  const columns = useMemo<ColumnDef<Card>[]>(() => [
    {
      accessorKey: 'name',
      meta: { align: 'left' },
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
          <div className="flex items-center gap-1.5 sm:gap-2 max-w-[140px] sm:max-w-[180px] md:max-w-[250px] lg:max-w-none">
              <CardThumbnail
                  src={row.original.image_url}
                  alt={row.getValue('name')}
                  className="w-6 h-8 sm:w-8 sm:h-11 lg:w-10 lg:h-14 rounded object-cover bg-muted shrink-0"
              />
              <div className="min-w-0 overflow-hidden flex-1">
                  <div className="flex items-center gap-1 sm:gap-1.5">
                    <Tooltip content={row.getValue('name')}>
                        <span className="font-bold text-foreground text-xs sm:text-sm lg:text-base truncate block max-w-[80px] sm:max-w-[120px] md:max-w-[180px] lg:max-w-none">{row.getValue('name')}</span>
                    </Tooltip>
                    {isSingle && rarity && (
                      <Tooltip content={rarity}>
                          <span className={clsx(
                            "shrink-0 text-[8px] lg:text-[10px] font-bold uppercase px-1 py-0.5 rounded",
                            rarity === 'Mythic' ? 'text-amber-900 bg-amber-400' :
                            rarity === 'Legendary' ? 'text-orange-900 bg-orange-400' :
                            rarity === 'Epic' ? 'text-purple-900 bg-purple-400' :
                            rarity === 'Rare' ? 'text-blue-900 bg-blue-400' :
                            rarity === 'Uncommon' ? 'text-brand-800 bg-brand-300' :
                            'text-zinc-900 bg-zinc-400'
                          )}>
                            {rarity}
                          </span>
                      </Tooltip>
                    )}
                    {!isSingle && IconComponent && (
                      <Tooltip content={productType}>
                          <span className="shrink-0 text-muted-foreground/40">
                            <IconComponent className="w-3.5 h-3.5 lg:w-4 lg:h-4" />
                          </span>
                      </Tooltip>
                    )}
                  </div>
                  <div className="text-[9px] sm:text-[10px] lg:text-xs text-muted-foreground/70 uppercase truncate">{row.original.set_name}</div>
              </div>
          </div>
        )
      },
    },
    {
      accessorKey: 'floor_price', // Floor price = avg of 4 lowest sales (30d)
      meta: { align: 'center' },
      sortingFn: (a, b) => ((a.original.floor_price ?? 0) - (b.original.floor_price ?? 0)),
      header: ({ column }) => (
        <Tooltip content="Floor Price (avg of 4 lowest sales in 30d)">
            <button
              className="inline-flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs"
              onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
            >
              Floor
              <ArrowUpDown className="h-3 w-3" />
            </button>
        </Tooltip>
      ),
      cell: ({ row }) => {
          // Use floor_price, fallback to vwap if no floor
          const floorPrice = row.original.floor_price || row.original.vwap
          const hasFloor = !!floorPrice && floorPrice > 0
          const delta = row.original.price_delta ?? row.original.price_delta_24h ?? 0

          // Check for variant price range for sealed products
          const floorByVariant = row.original.floor_by_variant
          const askByVariant = row.original.lowest_ask_by_variant
          const variantCount = Object.keys(floorByVariant || {}).length + Object.keys(askByVariant || {}).length
          const hasMultipleVariants = variantCount > 1 || (row.original.product_type && row.original.product_type !== 'Single' && variantCount > 0)

          // Get price range if multiple variants
          let priceRange = ''
          if (hasMultipleVariants) {
              const allPrices = [
                  ...Object.values(floorByVariant || {}),
                  ...Object.values(askByVariant || {})
              ].filter(p => p > 0)
              if (allPrices.length > 1) {
                  const min = Math.min(...allPrices)
                  const max = Math.max(...allPrices)
                  if (min !== max) {
                      priceRange = `$${min.toFixed(0)}-$${max.toFixed(0)}`
                  }
              }
          }

          return (
            <div className="inline-flex flex-col items-center gap-0.5">
                <div className="inline-flex items-center gap-1 md:gap-2">
                    <span className="font-mono text-sm lg:text-base">
                        {hasFloor ? `$${floorPrice.toFixed(2)}` : '---'}
                    </span>
                    {/* Hide delta badge on mobile to save space */}
                    {hasFloor && delta !== 0 && (
                        <span className={clsx(
                            "hidden sm:inline text-[10px] lg:text-xs font-mono px-1 py-0.5 rounded",
                            delta > 0 ? "text-brand-300 bg-brand-300/10" :
                            "text-red-400 bg-red-500/10"
                        )}>
                            {delta > 0 ? '↑' : '↓'}{Math.abs(delta).toFixed(1)}%
                        </span>
                    )}
                </div>
                {/* Hide price range on mobile */}
                {priceRange && (
                    <Tooltip content="Price range across variants - click for breakdown">
                        <span className="hidden sm:inline text-[9px] text-muted-foreground font-mono">
                            {priceRange}
                        </span>
                    </Tooltip>
                )}
            </div>
          )
      }
    },
    {
        accessorKey: 'volume',
        meta: { align: 'center' },
        sortingFn: (a, b) => ((a.original.volume ?? 0) - (b.original.volume ?? 0)),
        header: ({ column }) => (
          <Tooltip content="Sales volume in selected time period">
              <button
                className="flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs mx-auto"
                onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
              >
                Vol
                <ArrowUpDown className="h-3 w-3" />
              </button>
          </Tooltip>
        ),
        cell: ({ row }) => {
            const vol = row.original.volume ?? row.original.volume_30d ?? 0
            // Chevron indicators based on volume thresholds
            let chevrons = ''
            let colorClass = 'text-muted-foreground'
            let chevronTooltip = ''
            if (vol >= 30) {
                chevrons = '▲▲'
                colorClass = 'text-brand-300'
                chevronTooltip = 'High volume (30+ sales)'
            } else if (vol >= 10) {
                chevrons = '▲'
                colorClass = 'text-brand-300'
                chevronTooltip = 'Good volume (10-29 sales)'
            } else if (vol > 0 && vol < 3) {
                chevrons = '▼'
                colorClass = 'text-red-400'
                chevronTooltip = 'Low volume (1-2 sales)'
            } else if (vol === 0) {
                chevrons = '▼▼'
                colorClass = 'text-red-500'
                chevronTooltip = 'No sales in period'
            }

            return (
                <div className="flex items-center justify-center gap-1 font-mono text-sm lg:text-base">
                    <span>{vol}</span>
                    {/* Hide chevrons on mobile to save space */}
                    {chevrons && (
                        <Tooltip content={chevronTooltip}>
                            <span className={clsx("hidden sm:inline text-[10px] lg:text-xs", colorClass)}>{chevrons}</span>
                        </Tooltip>
                    )}
                </div>
            )
        }
    },
    {
        accessorKey: 'latest_price',
        meta: { align: 'center' },
        sortingFn: (a, b) => ((a.original.latest_price ?? 0) - (b.original.latest_price ?? 0)),
        header: ({ column }) => (
          <Tooltip content="Most recent sale price and treatment">
              <button
                className="flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs mx-auto"
                onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
              >
                Last Sale
                <ArrowUpDown className="h-3 w-3" />
              </button>
          </Tooltip>
        ),
        cell: ({ row }) => {
            const price = row.original.latest_price || 0
            const rawTreatment = row.original.last_treatment ?? row.original.last_sale_treatment ?? ''
            const treatment = simplifyTreatmentForDisplay(rawTreatment)
            return (
                <div className="text-center">
                    <div className="font-mono text-sm lg:text-base">{price > 0 ? `$${price.toFixed(2)}` : '---'}</div>
                    {/* Hide treatment on mobile to save space */}
                    {treatment && (
                        <Tooltip content={rawTreatment}>
                            <div className="hidden sm:block text-[9px] lg:text-[11px] text-muted-foreground truncate">
                                {treatment}
                            </div>
                        </Tooltip>
                    )}
                </div>
            )
        }
    },
    {
        accessorKey: 'max_price',
        meta: { align: 'center' },
        sortingFn: (a, b) => ((a.original.max_price ?? 0) - (b.original.max_price ?? 0)),
        header: ({ column }) => (
          <Tooltip content="Highest confirmed sale price">
              <button
                className="hidden md:flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs mx-auto"
                onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
              >
                High
                <ArrowUpDown className="h-3 w-3" />
              </button>
          </Tooltip>
        ),
        cell: ({ row }) => {
            const high = row.original.max_price || 0
            return <div className="hidden md:block text-center font-mono text-sm lg:text-base text-brand-300">{high > 0 ? `$${high.toFixed(2)}` : '---'}</div>
        }
    },
    {
        accessorKey: 'lowest_ask',
        meta: { align: 'center' },
        sortingFn: (a, b) => ((a.original.lowest_ask ?? 0) - (b.original.lowest_ask ?? 0)),
        header: ({ column }) => (
          <Tooltip content="Lowest active asking price">
              <button
                className="hidden md:flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs mx-auto"
                onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
              >
                Ask
                <ArrowUpDown className="h-3 w-3" />
              </button>
          </Tooltip>
        ),
        cell: ({ row }) => {
            const ask = row.original.lowest_ask || 0
            return <div className="hidden md:block text-center font-mono text-sm lg:text-base">{ask > 0 ? `$${ask.toFixed(2)}` : '---'}</div>
        }
    },
    {
        accessorKey: 'inventory',
        meta: { align: 'center' },
        sortingFn: (a, b) => ((a.original.inventory ?? 0) - (b.original.inventory ?? 0)),
        header: ({ column }) => (
          <Tooltip content="Active listings count and estimated days to sell">
              <button
                className="hidden lg:flex items-center gap-1 hover:text-primary uppercase tracking-wider text-xs mx-auto"
                onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
              >
                Listings
                <ArrowUpDown className="h-3 w-3" />
              </button>
          </Tooltip>
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
                ? daysToSell < 3 ? 'text-brand-300'
                : daysToSell > 14 ? 'text-red-400'
                : 'text-muted-foreground'
                : 'text-muted-foreground'
            return (
                <div className="hidden lg:block text-center">
                    <div className="font-mono text-sm lg:text-base">{inv}</div>
                    <Tooltip content="Estimated days to sell current inventory at current sales velocity">
                        <div className={clsx("text-[9px] lg:text-[11px]", daysClass)}>{daysDisplay} sell</div>
                    </Tooltip>
                </div>
            )
        }
    },
    {
        id: 'track',
        meta: { align: 'center' },
        header: () => <div className="text-xs uppercase tracking-wider text-muted-foreground text-center">Track</div>,
        cell: ({ row }) => {
            return (
                <div className="flex justify-center">
                    <Tooltip content={user ? "Add to Portfolio" : "Login to track"}>
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
                        >
                            <Plus className="w-3.5 h-3.5" />
                        </button>
                    </Tooltip>
                </div>
            )
        }
    }
  ], [user])

  // Cards data (no filtering)
  const filteredCards = useMemo(() => {
    if (!cards) return []
    return cards
  }, [cards])

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
                    {/* Dashboard Tabs */}
                    <div className="flex items-center gap-1 shrink-0">
                        <button
                            onClick={() => setActiveTab('products')}
                            className={clsx(
                                "flex items-center gap-2 px-3 py-1.5 text-sm font-bold uppercase tracking-wider rounded-l border transition-colors",
                                activeTab === 'products'
                                    ? "bg-primary text-primary-foreground border-primary"
                                    : "bg-background text-muted-foreground border-border hover:bg-muted/50 hover:text-foreground"
                            )}
                        >
                            <Package className="w-4 h-4" />
                            Products
                        </button>
                        <button
                            onClick={() => setActiveTab('listings')}
                            className={clsx(
                                "flex items-center gap-2 px-3 py-1.5 text-sm font-bold uppercase tracking-wider rounded-r border border-l-0 transition-colors",
                                activeTab === 'listings'
                                    ? "bg-primary text-primary-foreground border-primary"
                                    : "bg-background text-muted-foreground border-border hover:bg-muted/50 hover:text-foreground"
                            )}
                        >
                            <ShoppingCart className="w-4 h-4" />
                            Listings
                        </button>
                    </div>
                    
                    {/* Filters & Controls inside Header - conditional based on tab */}
                    {activeTab === 'products' ? (
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
                              <SimpleDropdown
                                  value={productType}
                                  onChange={(value) => {
                                      setProductType(value)
                                      analytics.trackFilterApplied('product_type', value)
                                  }}
                                  options={[
                                      { value: 'all', label: 'All Types' },
                                      { value: 'Single', label: 'Singles' },
                                      { value: 'Box', label: 'Boxes' },
                                      { value: 'Pack', label: 'Packs' },
                                      { value: 'Lot', label: 'Lots' },
                                      { value: 'Proof', label: 'Proofs' },
                                  ]}
                                  size="sm"
                                  className="flex-1 sm:w-[110px]"
                                  triggerClassName="uppercase font-mono text-xs"
                              />

                              <SimpleDropdown
                                  value={platform}
                                  onChange={(value) => {
                                      setPlatform(value)
                                      analytics.trackFilterApplied('platform', value)
                                  }}
                                  options={[
                                      { value: 'all', label: 'All Platforms' },
                                      { value: 'ebay', label: 'eBay' },
                                      { value: 'blokpax', label: 'Blokpax' },
                                      { value: 'opensea', label: 'OpenSea' },
                                  ]}
                                  size="sm"
                                  className="flex-1 sm:w-[120px]"
                                  triggerClassName="uppercase font-mono text-xs"
                              />

                              <SimpleDropdown
                                  value={timePeriod}
                                  onChange={(value) => {
                                      setTimePeriod(value)
                                      analytics.trackFilterApplied('time_period', value)
                                  }}
                                  options={[
                                      { value: '7d', label: '7 Days' },
                                      { value: '30d', label: '30 Days' },
                                      { value: '90d', label: '90 Days' },
                                      { value: 'all', label: 'All Time' },
                                  ]}
                                  size="sm"
                                  className="flex-1 sm:w-[100px]"
                                  triggerClassName="uppercase font-mono text-xs"
                              />
                          </div>
                      </div>
                    ) : (
                      /* Listings tab filters */
                      <div className="flex flex-col sm:flex-row flex-wrap items-start sm:items-center gap-2 md:gap-4 w-full">
                          <div className="relative w-full flex-1">
                               <Search className="absolute left-3 top-2 h-3.5 w-3.5 text-muted-foreground" />
                              <input
                                  type="text"
                                  placeholder="SEARCH LISTINGS..."
                                  className="w-full bg-background pl-9 pr-4 py-1.5 rounded border border-border text-xs focus:outline-none focus:ring-1 focus:ring-primary placeholder:text-muted-foreground/50"
                                  value={listingSearch}
                                  onChange={e => setListingSearch(e.target.value)}
                              />
                          </div>

                          <div className="flex items-center gap-2 w-full sm:w-auto shrink-0 flex-wrap">
                              <SimpleDropdown
                                  value={listingType}
                                  onChange={(value) => {
                                      setListingType(value)
                                      analytics.trackFilterApplied('listing_type', value)
                                  }}
                                  options={[
                                      { value: 'active', label: 'Active' },
                                      { value: 'sold', label: 'Sold' },
                                      { value: 'all', label: 'All' },
                                  ]}
                                  size="sm"
                                  className="flex-1 sm:w-[90px]"
                                  triggerClassName="uppercase font-mono text-xs"
                              />

                              <SimpleDropdown
                                  value={listingPlatform}
                                  onChange={(value) => {
                                      setListingPlatform(value)
                                      analytics.trackFilterApplied('listing_platform', value)
                                  }}
                                  options={[
                                      { value: 'all', label: 'All Platforms' },
                                      { value: 'ebay', label: 'eBay' },
                                      { value: 'blokpax', label: 'Blokpax' },
                                      { value: 'opensea', label: 'OpenSea' },
                                  ]}
                                  size="sm"
                                  className="flex-1 sm:w-[120px]"
                                  triggerClassName="uppercase font-mono text-xs"
                              />

                              <SimpleDropdown
                                  value={listingProductType}
                                  onChange={(value) => {
                                      setListingProductType(value)
                                      analytics.trackFilterApplied('listing_product_type', value)
                                  }}
                                  options={[
                                      { value: 'all', label: 'All Types' },
                                      { value: 'Single', label: 'Singles' },
                                      { value: 'Box', label: 'Boxes' },
                                      { value: 'Pack', label: 'Packs' },
                                  ]}
                                  size="sm"
                                  className="flex-1 sm:w-[100px]"
                                  triggerClassName="uppercase font-mono text-xs"
                              />

                              <SimpleDropdown
                                  value={listingTreatment}
                                  onChange={(value) => {
                                      setListingTreatment(value)
                                      analytics.trackFilterApplied('listing_treatment', value)
                                  }}
                                  options={[
                                      { value: 'all', label: 'All Treatments' },
                                      { value: 'Classic Paper', label: 'Classic Paper' },
                                      { value: 'Classic Foil', label: 'Classic Foil' },
                                      { value: 'Foil', label: 'Foil' },
                                  ]}
                                  size="sm"
                                  className="flex-1 sm:w-[130px]"
                                  triggerClassName="uppercase font-mono text-xs"
                              />

                              <SimpleDropdown
                                  value={listingTimePeriod}
                                  onChange={(value) => {
                                      setListingTimePeriod(value)
                                      analytics.trackFilterApplied('listing_time_period', value)
                                  }}
                                  options={[
                                      { value: 'all', label: 'All Time' },
                                      { value: '7d', label: '7 Days' },
                                      { value: '30d', label: '30 Days' },
                                      { value: '90d', label: '90 Days' },
                                  ]}
                                  size="sm"
                                  className="flex-1 sm:w-[100px]"
                                  triggerClassName="uppercase font-mono text-xs"
                              />
                          </div>
                      </div>
                    )}
      </div>

                <div className="text-xs text-muted-foreground font-mono hidden xl:block shrink-0">
                    {activeTab === 'products'
                      ? `Showing ${filteredCards.length} of ${cards?.length || 0} assets`
                      : `Showing ${listingsData?.items.length || 0} of ${listingsData?.total || 0} listings`
                    }
                </div>
        </div>
                {/* Tab Content - Products or Listings */}
                {activeTab === 'products' ? (
                  /* Products Tab Content */
                  isLoading ? (
                      <div className="p-12 text-center">
                          <div className="animate-spin w-6 h-6 border-2 border-primary border-t-transparent rounded-full mx-auto mb-4"></div>
                          <div className="text-xs uppercase text-muted-foreground animate-pulse">Loading market stream...</div>
                      </div>
                  ) : (
                      <>
                          <div className="overflow-x-auto flex-1 scrollbar-thin scrollbar-thumb-border scrollbar-track-transparent">
                              <table className="w-full text-sm text-left min-w-[480px]">
                                  <thead className="text-xs uppercase bg-muted/30 text-muted-foreground border-b border-border sticky top-0 z-10">
                                      {table.getHeaderGroups().map(headerGroup => (
                                          <tr key={headerGroup.id}>
                                              {headerGroup.headers.map(header => {
                                              const align = (header.column.columnDef.meta as { align?: string })?.align || 'left'
                                              return (
                                              <th key={header.id} className={clsx(
                                                  "px-1 sm:px-2 py-1 sm:py-1.5 font-medium whitespace-nowrap hover:bg-muted/50 transition-colors bg-muted/30",
                                                  align === 'center' && 'text-center',
                                                  align === 'right' && 'text-right'
                                              )}>
                                                      {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                                                  </th>
                                              )
                                              })}
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
                                                  {row.getVisibleCells().map(cell => {
                                                      const align = (cell.column.columnDef.meta as { align?: string })?.align || 'left'
                                                      return (
                                                  <td key={cell.id} className={clsx(
                                                      "px-1 sm:px-2 py-1 sm:py-1.5 whitespace-nowrap",
                                                      align === 'center' && 'text-center',
                                                      align === 'right' && 'text-right'
                                                  )}>
                                                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                                      </td>
                                                      )
                                                  })}
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
                  )
                ) : (
                  /* Listings Tab Content */
                  listingsLoading ? (
                      <div className="p-12 text-center">
                          <div className="animate-spin w-6 h-6 border-2 border-primary border-t-transparent rounded-full mx-auto mb-4"></div>
                          <div className="text-xs uppercase text-muted-foreground animate-pulse">Loading listings...</div>
                      </div>
                  ) : (
                      <>
                          <div className="overflow-x-auto flex-1 scrollbar-thin scrollbar-thumb-border scrollbar-track-transparent">
                              <table className="w-full text-sm text-left min-w-[400px]">
                                  <thead className="text-xs uppercase bg-muted/30 text-muted-foreground border-b border-border sticky top-0 z-10">
                                      <tr>
                                          <th className="px-2 py-1.5 font-medium whitespace-nowrap bg-muted/30">Card</th>
                                          <th className="px-2 py-1.5 font-medium whitespace-nowrap bg-muted/30 text-right">
                                              <button
                                                  className="flex items-center gap-1 hover:text-primary ml-auto"
                                                  onClick={() => toggleListingSort('price')}
                                              >
                                                  Price
                                                  {listingSortBy === 'price' ? (
                                                      listingSortOrder === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />
                                                  ) : (
                                                      <ArrowUpDown className="h-3 w-3 opacity-50" />
                                                  )}
                                              </button>
                                          </th>
                                          <th className="px-2 py-1.5 font-medium whitespace-nowrap bg-muted/30 text-center hidden md:table-cell">
                                              <button
                                                  className="flex items-center gap-1 hover:text-primary mx-auto"
                                                  onClick={() => toggleListingSort('floor_price')}
                                              >
                                                  Floor
                                                  {listingSortBy === 'floor_price' ? (
                                                      listingSortOrder === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />
                                                  ) : (
                                                      <ArrowUpDown className="h-3 w-3 opacity-50" />
                                                  )}
                                              </button>
                                          </th>
                                          <th className="px-2 py-1.5 font-medium whitespace-nowrap bg-muted/30 text-center hidden md:table-cell">Treatment</th>
                                          <th className="px-2 py-1.5 font-medium whitespace-nowrap bg-muted/30 hidden lg:table-cell">Listing</th>
                                          <th className="px-2 py-1.5 font-medium whitespace-nowrap bg-muted/30 hidden lg:table-cell">Seller</th>
                                          <th className="px-2 py-1.5 font-medium whitespace-nowrap bg-muted/30 hidden xl:table-cell">
                                              <button
                                                  className="flex items-center gap-1 hover:text-primary"
                                                  onClick={() => toggleListingSort('scraped_at')}
                                              >
                                                  Listed
                                                  {listingSortBy === 'scraped_at' ? (
                                                      listingSortOrder === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />
                                                  ) : (
                                                      <ArrowUpDown className="h-3 w-3 opacity-50" />
                                                  )}
                                              </button>
                                          </th>
                                          <th className="px-2 py-1.5 font-medium whitespace-nowrap bg-muted/30 text-center">Links</th>
                                      </tr>
                                  </thead>
                                  <tbody className="divide-y divide-border/50">
                                      {listingsData?.items.length ? (
                                          listingsData.items.map(listing => (
                                              <tr
                                                  key={listing.id}
                                                  className="hover:bg-muted/30 transition-colors cursor-pointer"
                                                  onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: listing.card_slug || String(listing.card_id) } })}
                                              >
                                                  {/* Card with thumbnail */}
                                                  <td className="px-2 py-1.5">
                                                      <div className="flex items-center gap-2">
                                                          <CardThumbnail
                                                              src={listing.card_image_url}
                                                              alt={listing.card_name}
                                                              className="w-8 h-11 lg:w-10 lg:h-14 rounded object-cover bg-muted shrink-0"
                                                          />
                                                          <div className="min-w-0">
                                                              <div className="font-bold text-sm lg:text-base truncate max-w-[120px] md:max-w-none">{listing.card_name}</div>
                                                              <div className="flex items-center gap-1.5">
                                                                  <span className="text-[10px] lg:text-xs text-muted-foreground uppercase">{listing.product_type}</span>
                                                                  <span className={clsx(
                                                                      "text-[9px] lg:text-[10px] font-bold uppercase px-1 py-0.5 rounded",
                                                                      listing.platform === 'ebay' ? 'bg-blue-500/20 text-blue-400' :
                                                                      listing.platform === 'blokpax' ? 'bg-purple-500/20 text-purple-400' :
                                                                      listing.platform === 'opensea' ? 'bg-cyan-500/20 text-cyan-400' :
                                                                      'bg-muted text-muted-foreground'
                                                                  )}>
                                                                      {listing.platform}
                                                                  </span>
                                                              </div>
                                                          </div>
                                                      </div>
                                                  </td>
                                                  {/* Price */}
                                                  <td className="px-2 py-1.5 text-right">
                                                      {(() => {
                                                          const refPrice = listing.floor_price || listing.vwap
                                                          const priceDelta = refPrice && refPrice > 0
                                                            ? ((listing.price - refPrice) / refPrice) * 100
                                                            : null
                                                          return (
                                                            <>
                                                              <div className="font-mono text-sm lg:text-base font-bold">${listing.price.toFixed(2)}</div>
                                                              {priceDelta !== null && Math.abs(priceDelta) >= 1 && (
                                                                <div className={clsx(
                                                                  "text-[10px] lg:text-xs font-mono",
                                                                  priceDelta < -5 ? "text-brand-300" :
                                                                  priceDelta > 20 ? "text-red-400" :
                                                                  "text-muted-foreground"
                                                                )}>
                                                                  {priceDelta > 0 ? '+' : ''}{priceDelta.toFixed(0)}%
                                                                </div>
                                                              )}
                                                              {listing.shipping_cost !== null && listing.shipping_cost !== undefined && (
                                                                <div className="text-[10px] lg:text-xs text-muted-foreground">
                                                                    {listing.shipping_cost === 0 ? 'Free' : `+$${listing.shipping_cost.toFixed(0)}`}
                                                                </div>
                                                              )}
                                                            </>
                                                          )
                                                      })()}
                                                  </td>
                                                  {/* Floor price (with VWAP fallback) */}
                                                  <td className="px-2 py-1.5 text-center hidden md:table-cell">
                                                      {listing.floor_price ? (
                                                        <div className="font-mono text-sm lg:text-base text-muted-foreground">
                                                          ${listing.floor_price.toFixed(2)}
                                                        </div>
                                                      ) : listing.vwap ? (
                                                        <Tooltip content="VWAP - avg of all recent sales (floor unavailable)">
                                                          <div className="font-mono text-sm lg:text-base text-muted-foreground/70 italic">
                                                            ~${listing.vwap.toFixed(2)}
                                                          </div>
                                                        </Tooltip>
                                                      ) : (
                                                        <div className="font-mono text-sm lg:text-base text-muted-foreground">---</div>
                                                      )}
                                                  </td>
                                                  {/* Treatment / Traits / Subtype */}
                                                  <td className="px-2 py-1.5 text-center hidden md:table-cell">
                                                      {listing.treatment ? (
                                                        <TreatmentBadge treatment={listing.treatment} size="xs" />
                                                      ) : (listing.platform === 'opensea' || listing.platform === 'blokpax') && listing.traits ? (
                                                        <Tooltip content={Object.entries(listing.traits).map(([k, v]) => `${k}: ${v}`).join(', ')}>
                                                          <div className="flex flex-wrap gap-0.5 max-w-[120px]">
                                                            {Object.entries(listing.traits).slice(0, 2).map(([key, val]) => (
                                                              <span key={key} className="text-[9px] bg-purple-500/20 text-purple-400 px-1 py-0.5 rounded truncate max-w-[60px]">
                                                                {String(val)}
                                                              </span>
                                                            ))}
                                                            {Object.keys(listing.traits).length > 2 && (
                                                              <span className="text-[9px] text-muted-foreground">+{Object.keys(listing.traits).length - 2}</span>
                                                            )}
                                                          </div>
                                                        </Tooltip>
                                                      ) : (
                                                        <span className="text-xs text-muted-foreground">-</span>
                                                      )}
                                                  </td>
                                                  {/* Listing title */}
                                                  <td className="px-2 py-1.5 hidden lg:table-cell">
                                                      <Tooltip content={listing.title}>
                                                          <div className="text-xs lg:text-sm truncate max-w-[180px] lg:max-w-[220px]">{listing.title}</div>
                                                      </Tooltip>
                                                      {listing.listing_type === 'sold' && listing.sold_date && (
                                                          <div className="text-[10px] lg:text-xs text-brand-300">
                                                              Sold {new Date(listing.sold_date).toLocaleDateString()}
                                                          </div>
                                                      )}
                                                  </td>
                                                  {/* Seller */}
                                                  <td className="px-2 py-1.5 hidden lg:table-cell">
                                                      <div className="text-xs lg:text-sm truncate max-w-[100px] lg:max-w-[120px]">
                                                          {listing.seller_name || (listing.seller_feedback_percent ? '' : '-')}
                                                      </div>
                                                      {listing.seller_feedback_percent && (
                                                          <div className="text-[10px] lg:text-xs text-muted-foreground">{listing.seller_feedback_percent}%</div>
                                                      )}
                                                  </td>
                                                  {/* Listed Date */}
                                                  <td className="px-2 py-1.5 hidden xl:table-cell">
                                                      <div className="text-xs lg:text-sm text-muted-foreground">
                                                          {listing.listed_at
                                                            ? new Date(listing.listed_at).toLocaleDateString()
                                                            : listing.scraped_at
                                                            ? new Date(listing.scraped_at).toLocaleDateString()
                                                            : '-'
                                                          }
                                                      </div>
                                                  </td>
                                                  {/* Link buttons */}
                                                  <td className="px-2 py-1.5" onClick={(e) => e.stopPropagation()}>
                                                      <div className="flex items-center justify-center gap-1">
                                                          {listing.url && (
                                                              <Tooltip content={`View on ${listing.platform}`}>
                                                                  <a
                                                                      href={listing.url}
                                                                      target="_blank"
                                                                      rel="noopener noreferrer"
                                                                      onClick={() => {
                                                                          analytics.trackExternalLinkClick(listing.platform, listing.card_id, listing.title)
                                                                      }}
                                                                      className="p-1.5 rounded border border-border hover:bg-muted/50 hover:text-primary transition-colors"
                                                                  >
                                                                      <ExternalLink className="w-3.5 h-3.5" />
                                                                  </a>
                                                              </Tooltip>
                                                          )}
                                                          <Tooltip content="Card details">
                                                              <button
                                                                  onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: listing.card_slug || String(listing.card_id) } })}
                                                                  className="p-1.5 rounded border border-border hover:bg-muted/50 hover:text-primary transition-colors"
                                                              >
                                                                  <Info className="w-3.5 h-3.5" />
                                                              </button>
                                                          </Tooltip>
                                                      </div>
                                                  </td>
                                              </tr>
                                          ))
                                      ) : (
                                          <tr>
                                              <td colSpan={8} className="h-32 text-center text-muted-foreground text-xs uppercase">
                                                  No listings found.
                                              </td>
                                          </tr>
                                      )}
                                  </tbody>
                              </table>
                          </div>
                          {/* Listings count footer */}
                          <div className="border-t border-border px-3 py-2 flex items-center justify-between bg-muted/20">
                              <div className="text-xs text-muted-foreground">
                                  Showing {listingPage * LISTINGS_PER_PAGE + 1} to {Math.min((listingPage + 1) * LISTINGS_PER_PAGE, listingsData?.total || 0)} of {listingsData?.total || 0} listings
                                  {listingsFetching && <span className="ml-2 text-primary">Loading...</span>}
                              </div>
                              <div className="flex items-center gap-2">
                                  <button
                                      onClick={() => setListingPage(p => Math.max(0, p - 1))}
                                      disabled={listingPage === 0}
                                      className="p-1 rounded hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed"
                                  >
                                      <ChevronLeft className="w-4 h-4" />
                                  </button>
                                  <span className="text-xs text-muted-foreground">
                                      Page {listingPage + 1} of {Math.ceil((listingsData?.total || 0) / LISTINGS_PER_PAGE)}
                                  </span>
                                  <button
                                      onClick={() => setListingPage(p => p + 1)}
                                      disabled={!listingsData?.hasMore}
                                      className="p-1 rounded hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed"
                                  >
                                      <ChevronRight className="w-4 h-4" />
                                  </button>
                              </div>
                          </div>
                      </>
                  )
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