import { createFileRoute, useNavigate, Link } from '@tanstack/react-router'
import { api } from '../utils/auth'
import { analytics } from '~/services/analytics'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ColumnDef, flexRender, getCoreRowModel, useReactTable, getSortedRowModel, SortingState, getFilteredRowModel, getPaginationRowModel } from '@tanstack/react-table'
import { useState, useMemo, useEffect, useRef } from 'react'
import { ArrowUpDown, ArrowUp, ArrowDown, Calendar, DollarSign, BarChart3, LayoutDashboard, ChevronLeft, ChevronRight, Package, Layers, Gem, Archive, Store, ExternalLink, Info, LayoutGrid, List } from 'lucide-react'
// Animated icons for micro-interactions
import { SearchIcon } from '~/components/ui/search'
import { PlusIcon, type PlusIconHandle } from '~/components/ui/plus'
import { TrendingUpIcon } from '~/components/ui/trending-up'
import { RefreshCWIcon } from '~/components/ui/refresh-cw'
import { DollarSignIcon, type DollarSignIconHandle } from '~/components/ui/dollar-sign'
import clsx from 'clsx'
import { Tooltip } from '../components/ui/tooltip'
import { SimpleDropdown } from '../components/ui/dropdown'
import { Button, IconButton, CloseButton } from '../components/ui/button'
import { RarityBadge } from '../components/ui/rarity-badge'
import { PlatformBadge } from '../components/ui/platform-badge'
import { useTimePeriod } from '../context/TimePeriodContext'
import { useCurrentUser } from '../context/UserContext'
import { AddToPortfolioModal } from '../components/AddToPortfolioModal'
import { TreatmentBadge } from '../components/TreatmentBadge'
import { MobileCardList, type MobileCardItem } from '../components/ui/mobile-card-list'
import { ProductListItem, ProductListItemSkeleton } from '../components/ui/product-list-item'
import { ProductsGallery, Hero, CategoryCards } from '../components/home'
import { HomeTableSkeleton, MobileCardListSkeleton, ProductGallerySkeleton } from '../components/ui/skeleton'

// Reduced from 200 to 50 for faster initial load - users can paginate for more
// Balance between completeness and speed - 200 cards loads in ~3s
const CARDS_FETCH_LIMIT = Number(import.meta.env.VITE_CARDS_FETCH_LIMIT ?? '200')

// Card thumbnail with placeholder fallback for missing/failed images
// Uses image_url from API response (blob storage URLs with hash)
function CardThumbnail({ src, alt, className }: { src?: string; alt: string; className: string }) {
  const [error, setError] = useState(false)

  // Show placeholder if no src or image failed to load
  if (!src || error) {
    return (
      <div className={clsx(className, "bg-muted flex items-center justify-center")}>
        <svg className="w-4 h-4 text-muted-foreground/40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      className={className}
      onError={() => setError(true)}
    />
  )
}

// Track button with animated PlusIcon that responds to button hover
function TrackButton({ onClick, tooltip }: { onClick: () => void; tooltip: string }) {
  const iconRef = useRef<PlusIconHandle>(null)

  return (
    <Tooltip content={tooltip}>
      <button
        onClick={(e) => {
          e.stopPropagation()
          onClick()
        }}
        onMouseEnter={() => iconRef.current?.startAnimation()}
        onMouseLeave={() => iconRef.current?.stopAnimation()}
        className="flex items-center gap-1.5 px-3 py-2 rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors font-medium text-sm"
      >
        <PlusIcon ref={iconRef} size={14} />
        <span className="hidden sm:inline">Track</span>
      </button>
    </Tooltip>
  )
}

// Dashboard tab button styles
const DASH_TAB_BASE = "flex items-center gap-2 px-4 h-9 text-xs font-bold uppercase tracking-wider border transition-colors"
const DASH_TAB_ACTIVE = "bg-primary text-primary-foreground border-primary"
const DASH_TAB_INACTIVE = "bg-background text-muted-foreground border-border hover:bg-muted/50 hover:text-foreground"

// Dashboard tab buttons with animated icons
function ProductsTabButton({ isActive, onClick }: { isActive: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={isActive}
      className={clsx(DASH_TAB_BASE, "rounded-l", isActive ? DASH_TAB_ACTIVE : DASH_TAB_INACTIVE)}
    >
      <Package className="w-4 h-4 transition-transform hover:scale-110" />
      Products
    </button>
  )
}

function ListingsTabButton({ isActive, onClick }: { isActive: boolean; onClick: () => void }) {
  const iconRef = useRef<DollarSignIconHandle>(null)
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => iconRef.current?.startAnimation()}
      onMouseLeave={() => iconRef.current?.stopAnimation()}
      aria-pressed={isActive}
      className={clsx(DASH_TAB_BASE, "rounded-r border-l-0", isActive ? DASH_TAB_ACTIVE : DASH_TAB_INACTIVE)}
    >
      <DollarSignIcon ref={iconRef} size={16} />
      Listings
    </button>
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

  // === CARDE.IO DATA ===
  orbital?: string // Heliosynth, Thalwind, Petraia, Solfera, Boundless, Umbrathene
  orbital_color?: string // Hex color e.g., #a07836

  // === DEPRECATED (backwards compat) ===
  volume_30d?: number // @deprecated: use 'volume'
  price_delta_24h?: number // @deprecated: use 'price_delta'
  last_sale_treatment?: string // @deprecated: use 'last_treatment'
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
  // Time period removed from UI - using 'all' for comprehensive data
  // const { timePeriod, setTimePeriod } = useTimePeriod()
  const [productType, setProductType] = useState<string>('all')
  const [platform, setPlatform] = useState<string>('all')
  const [treatment, setTreatment] = useState<string>('all')
  const [rarity, setRarity] = useState<string>('all')
  const [setFilter, setSetFilter] = useState<string>('all')
  const [trackingCard, setTrackingCard] = useState<Card | null>(null)
  const [activeTab, setActiveTabState] = useState<DashboardTab>('products')

  // Preserve scroll position when switching tabs
  const setActiveTab = (tab: DashboardTab) => {
    const scrollY = window.scrollY
    setActiveTabState(tab)
    // Wait for React to re-render and browser to re-layout, then restore scroll
    // Double requestAnimationFrame ensures the layout has settled
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        window.scrollTo(0, scrollY)
      })
    })
  }
  // Products tab view mode (table or list)
  const [viewMode, setViewMode] = useState<'table' | 'list'>('list')
  // Listings tab state
  const [listingType, setListingType] = useState<string>('active')
  const [listingPlatform, setListingPlatform] = useState<string>('all')
  const [listingProductType, setListingProductType] = useState<string>('all')
  const [listingTreatment, setListingTreatment] = useState<string>('all')
  const [listingTimePeriod, setListingTimePeriod] = useState<string>('all')
  const [listingSearch, setListingSearch] = useState<string>('')
  const [debouncedListingSearch, setDebouncedListingSearch] = useState<string>('')
  const [listingSortBy, setListingSortBy] = useState<string>('scraped_at')
  const [listingSortOrder, setListingSortOrder] = useState<'asc' | 'desc'>('desc')
  const [listingPage, setListingPage] = useState<number>(0)
  const [listingViewMode, setListingViewMode] = useState<'table' | 'list'>('list')
  const LISTINGS_PER_PAGE = 100
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // Prefetch card detail data on hover for faster navigation
  const prefetchCardDetail = (cardSlug: string) => {
    // Prefetch card data
    queryClient.prefetchQuery({
      queryKey: ['card', cardSlug],
      queryFn: async () => api.get(`cards/${cardSlug}`).json(),
      staleTime: 2 * 60 * 1000,
    })
    // Prefetch listings data (most expensive query)
    queryClient.prefetchQuery({
      queryKey: ['card-listings', cardSlug],
      queryFn: async () => api.get(`cards/${cardSlug}/listings?sold_limit=100&active_limit=100`).json(),
      staleTime: 2 * 60 * 1000,
    })
  }

  // Debounced search tracking
  useEffect(() => {
    if (!globalFilter || globalFilter.length < 2) return
    const timer = setTimeout(() => {
      analytics.trackSearch(globalFilter)
    }, 1000) // Track after 1s of no typing
    return () => clearTimeout(timer)
  }, [globalFilter])

  // Debounced listing search - immediate UI feedback, delayed API call
  useEffect(() => {
    // If search is cleared, update immediately
    if (!listingSearch) {
      setDebouncedListingSearch('')
      return
    }
    // Debounce search queries by 300ms
    const timer = setTimeout(() => {
      setDebouncedListingSearch(listingSearch)
    }, 300)
    return () => clearTimeout(timer)
  }, [listingSearch])

  const { user } = useCurrentUser()


  // Use 'all' time period for comprehensive data (no stale data filtering)
  const { data: cards, isLoading, isFetching } = useQuery({
    queryKey: ['cards', 'all', platform],
    queryFn: async () => {
      const platformParam = platform !== 'all' ? `&platform=${platform}` : ''
      // Load all cards - important ones can be deep in the list
      // slim=true reduces payload by ~50% for faster loading
      const data = await api.get(`cards?limit=${CARDS_FETCH_LIMIT}&time_period=all${platformParam}&slim=true`).json<Card[]>()
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
    placeholderData: (prev) => prev,
  })

  // Listings query for the Listings tab (server-side pagination)
  // Uses debouncedListingSearch to avoid firing requests on every keystroke
  const { data: listingsData, isLoading: listingsLoading, isFetching: listingsFetching } = useQuery({
    queryKey: ['listings', listingType, listingPlatform, listingProductType, listingTreatment, listingTimePeriod, debouncedListingSearch, listingSortBy, listingSortOrder, listingPage],
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
      if (debouncedListingSearch) params.set('search', debouncedListingSearch)
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
                          <RarityBadge rarity={rarity} variant="solid" size="xs" className="shrink-0" />
                      </Tooltip>
                    )}
                    {isSingle && row.original.orbital && (
                      <Tooltip content={row.original.orbital}>
                          <span
                            className="shrink-0 text-[8px] lg:text-[10px] font-bold uppercase px-1 py-0.5 rounded border hidden sm:inline-block"
                            style={{
                              backgroundColor: row.original.orbital_color ? `${row.original.orbital_color}30` : undefined,
                              borderColor: row.original.orbital_color || 'transparent',
                              color: row.original.orbital_color || undefined
                            }}
                          >
                            {row.original.orbital.substring(0, 4)}
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
                    <span className="font-mono text-base lg:text-lg font-semibold">
                        {hasFloor ? `$${floorPrice.toFixed(2)}` : '---'}
                    </span>
                    {/* Hide delta badge on mobile to save space */}
                    {hasFloor && delta !== 0 && (
                        <span className={clsx(
                            "hidden sm:inline text-[10px] lg:text-xs font-mono px-1 py-0.5 rounded",
                            delta > 0 ? "text-brand-300 bg-brand-300/10" :
                            "text-rose-500 bg-rose-500/10"
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
                colorClass = 'text-rose-500'
                chevronTooltip = 'Low volume (1-2 sales)'
            } else if (vol === 0) {
                chevrons = '▼▼'
                colorClass = 'text-rose-500'
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
                : daysToSell > 14 ? 'text-rose-500'
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
                    <TrackButton
                      tooltip={user ? "Add to Portfolio" : "Login to track"}
                      onClick={() => {
                        if (!user) {
                          navigate({ to: '/login' })
                          return
                        }
                        setTrackingCard(row.original)
                      }}
                    />
                </div>
            )
        }
    }
  ], [user])

  // Cards data (no filtering)
  const filteredCards = useMemo(() => {
    if (!cards) return []
    return cards.filter(card => {
      // Product type filter
      if (productType !== 'all') {
        const normalizedType = productType.toLowerCase()
        if ((card.product_type || 'single').toLowerCase() !== normalizedType) return false
      }
      // Treatment filter
      if (treatment !== 'all') {
        if ((card.last_treatment || '').toLowerCase() !== treatment.toLowerCase()) return false
      }
      // Rarity filter
      if (rarity !== 'all') {
        if ((card.rarity_name || '').toLowerCase() !== rarity.toLowerCase()) return false
      }
      // Set filter
      if (setFilter !== 'all') {
        if ((card.set_name || '').toLowerCase() !== setFilter.toLowerCase()) return false
      }
      return true
    })
  }, [cards, productType, treatment, rarity, setFilter])

  // Extract unique filter options from cards data
  const filterOptions = useMemo(() => {
    if (!cards) return { treatments: [], rarities: [], sets: [] }

    const treatments = [...new Set(cards.map(c => c.last_treatment).filter(Boolean))]
      .sort((a, b) => a!.localeCompare(b!))
    const rarities = [...new Set(cards.map(c => c.rarity_name).filter(Boolean))]
      .sort((a, b) => {
        // Custom rarity order
        const order = ['Mythic', 'Legendary', 'Epic', 'Rare', 'Uncommon', 'Common']
        return order.indexOf(a!) - order.indexOf(b!)
      })
    const sets = [...new Set(cards.map(c => c.set_name).filter(Boolean))]
      .sort((a, b) => a!.localeCompare(b!))

    return { treatments, rarities, sets }
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

  // Transform table data to mobile card format
  const mobileItems: MobileCardItem[] = useMemo(() => {
    return table.getRowModel().rows.map(row => ({
      id: row.original.id,
      name: row.original.name,
      subtitle: row.original.set_name,
      treatment: row.original.last_treatment,
      price: row.original.floor_price || row.original.vwap,
      priceChange: row.original.price_delta ?? row.original.price_delta_24h,
      secondaryValue: row.original.volume ? `${row.original.volume} sales` : undefined,
      imageUrl: row.original.image_url,
      onClick: () => navigate({ to: '/cards/$cardId', params: { cardId: row.original.slug || String(row.original.id) } }),
    }))
  }, [table.getRowModel().rows, navigate])

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
      // Use 30 days as default for velocity calculation
      const timePeriodDays = 30
      const avgVelocity = cards.length > 0 ? (totalVolume / cards.length / timePeriodDays) : 0

      return { totalVolume, totalVolumeUSD, avgVelocity }
  }, [cards])

  // Extract card images for hero background (28 for 4x7 grid)
  const heroImages = useMemo(() => {
    if (!cards) return []
    return cards
      .filter(c => c.image_url)
      .map(c => c.image_url!)
      .slice(0, 28)
  }, [cards])

  return (
    <div className="min-h-[calc(100vh-3.5rem-2rem)] flex flex-col bg-background text-foreground font-mono">
      <div className="p-4 max-w-[1800px] mx-auto w-full flex-1 flex flex-col">
        {/* Hero Section - hidden instead of unmounted to prevent layout shift */}
        <div className={activeTab === 'products' ? '' : 'hidden'}>
          <Hero cardImages={heroImages} />
        </div>

        {/* Category Quick Links */}
        {/* Category Cards - always visible */}
        <CategoryCards />

        {/* Products Gallery - show skeleton when loading, data when ready */}
        {isLoading ? (
          <ProductGallerySkeleton />
        ) : cards && cards.length > 0 ? (
          <ProductsGallery cards={cards} isLoading={false} />
        ) : null}

        {/* Main Data Table */}
        <div className="border border-border rounded-lg bg-card overflow-hidden flex-1 flex flex-col min-h-[400px]">
            {/* Row 1: Tab Navigation */}
            <div className="border-b border-border bg-muted/10">
                <div className="flex items-center">
                    <ProductsTabButton
                        isActive={activeTab === 'products'}
                        onClick={() => setActiveTab('products')}
                    />
                    <ListingsTabButton
                        isActive={activeTab === 'listings'}
                        onClick={() => setActiveTab('listings')}
                    />
                </div>
            </div>

            {/* Row 2: Filters - Products Tab */}
            <div className={activeTab === 'products' ? '' : 'hidden'}>
                <div className="p-3 border-b border-border bg-background/50">
                    <div className="flex flex-wrap items-center gap-2">
                        {/* Search */}
                        <div className="relative">
                            <SearchIcon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
                            <input
                                type="text"
                                placeholder="Search cards..."
                                className="h-9 w-[180px] bg-background pl-9 pr-4 rounded-full border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary placeholder:text-muted-foreground/60"
                                value={globalFilter}
                                onChange={e => setGlobalFilter(e.target.value)}
                            />
                        </div>

                        {/* Filter Pills */}
                        <SimpleDropdown
                            value={productType}
                            onChange={(value) => {
                                setProductType(value)
                                analytics.trackFilterApplied('product_type', value)
                            }}
                            options={[
                                { value: 'all', label: 'Product Type' },
                                { value: 'Single', label: 'Singles' },
                                { value: 'Box', label: 'Boxes' },
                                { value: 'Pack', label: 'Packs' },
                                { value: 'Lot', label: 'Lots' },
                                { value: 'Proof', label: 'Proofs' },
                            ]}
                        />

                        <SimpleDropdown
                            value={setFilter}
                            onChange={(value) => {
                                setSetFilter(value)
                                analytics.trackFilterApplied('set', value)
                            }}
                            options={[
                                { value: 'all', label: 'Set' },
                                ...filterOptions.sets.map(s => ({ value: s!, label: s! }))
                            ]}
                        />

                        <SimpleDropdown
                            value={rarity}
                            onChange={(value) => {
                                setRarity(value)
                                analytics.trackFilterApplied('rarity', value)
                            }}
                            options={[
                                { value: 'all', label: 'Rarity' },
                                ...filterOptions.rarities.map(r => ({ value: r!, label: r! }))
                            ]}
                        />

                        <SimpleDropdown
                            value={treatment}
                            onChange={(value) => {
                                setTreatment(value)
                                analytics.trackFilterApplied('treatment', value)
                            }}
                            options={[
                                { value: 'all', label: 'Treatment' },
                                ...filterOptions.treatments.map(t => ({ value: t!, label: t! }))
                            ]}
                        />

                        <SimpleDropdown
                            value={platform}
                            onChange={(value) => {
                                setPlatform(value)
                                analytics.trackFilterApplied('platform', value)
                            }}
                            options={[
                                { value: 'all', label: 'Platform' },
                                { value: 'ebay', label: 'eBay' },
                                { value: 'blokpax', label: 'Blokpax' },
                                { value: 'opensea', label: 'OpenSea' },
                            ]}
                        />

                        {/* Clear Filters */}
                        {(productType !== 'all' || platform !== 'all' || treatment !== 'all' || rarity !== 'all' || setFilter !== 'all' || globalFilter) && (
                            <button
                                onClick={() => {
                                    setProductType('all')
                                    setPlatform('all')
                                    setTreatment('all')
                                    setRarity('all')
                                    setSetFilter('all')
                                    setGlobalFilter('')
                                }}
                                className="text-sm text-primary hover:underline"
                            >
                                Clear Filters
                            </button>
                        )}
                    </div>
                </div>

                {/* Row 3: Results Bar */}
                <div className="px-4 py-2 border-b border-border bg-background/30 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground flex-wrap">
                        <span className="font-medium text-foreground">{filteredCards.length}</span>
                        <span>results</span>
                        {productType !== 'all' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs">
                                {productType}
                                <button onClick={() => setProductType('all')} className="hover:text-primary/70">×</button>
                            </span>
                        )}
                        {setFilter !== 'all' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs">
                                {setFilter}
                                <button onClick={() => setSetFilter('all')} className="hover:text-primary/70">×</button>
                            </span>
                        )}
                        {rarity !== 'all' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs">
                                {rarity}
                                <button onClick={() => setRarity('all')} className="hover:text-primary/70">×</button>
                            </span>
                        )}
                        {treatment !== 'all' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs">
                                {treatment}
                                <button onClick={() => setTreatment('all')} className="hover:text-primary/70">×</button>
                            </span>
                        )}
                        {platform !== 'all' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs">
                                {platform}
                                <button onClick={() => setPlatform('all')} className="hover:text-primary/70">×</button>
                            </span>
                        )}
                        {isFetching && !isLoading && (
                            <RefreshCWIcon size={14} className="animate-spin text-muted-foreground" />
                        )}
                    </div>

                    {/* Sort & View Toggle */}
                    <div className="flex items-center gap-3">
                        <SimpleDropdown
                            value={sorting[0]?.id || 'volume'}
                            onChange={(value) => {
                                setSorting([{ id: value, desc: value !== 'name' && value !== 'floor_price' }])
                            }}
                            options={[
                                { value: 'volume', label: 'Best Sellers' },
                                { value: 'floor_price', label: 'Price: Low to High' },
                                { value: 'latest_price', label: 'Price: High to Low' },
                                { value: 'name', label: 'Name' },
                            ]}
                        />

                        {/* View Toggle */}
                        <div className="flex items-center rounded-lg border border-border overflow-hidden">
                            <button
                                onClick={() => setViewMode('list')}
                                className={clsx(
                                    'p-2 transition-colors',
                                    viewMode === 'list'
                                        ? 'bg-primary text-primary-foreground'
                                        : 'bg-background hover:bg-muted text-muted-foreground'
                                )}
                                title="Grid view"
                            >
                                <LayoutGrid className="w-4 h-4" />
                            </button>
                            <button
                                onClick={() => setViewMode('table')}
                                className={clsx(
                                    'p-2 transition-colors',
                                    viewMode === 'table'
                                        ? 'bg-primary text-primary-foreground'
                                        : 'bg-background hover:bg-muted text-muted-foreground'
                                )}
                                title="List view"
                            >
                                <List className="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Row 2: Filters - Listings Tab */}
            <div className={activeTab === 'listings' ? '' : 'hidden'}>
                <div className="p-3 border-b border-border bg-background/50">
                    <div className="flex flex-wrap items-center gap-2">
                        {/* Search */}
                        <div className="relative">
                            <SearchIcon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
                            <input
                                type="text"
                                placeholder="Search listings..."
                                className="h-9 w-[200px] bg-background pl-9 pr-4 rounded-full border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary placeholder:text-muted-foreground/60"
                                value={listingSearch}
                                onChange={e => setListingSearch(e.target.value)}
                            />
                        </div>

                        {/* Filter Pills */}
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
                        />

                        <SimpleDropdown
                            value={listingPlatform}
                            onChange={(value) => {
                                setListingPlatform(value)
                                analytics.trackFilterApplied('listing_platform', value)
                            }}
                            options={[
                                { value: 'all', label: 'Platform' },
                                { value: 'ebay', label: 'eBay' },
                                { value: 'blokpax', label: 'Blokpax' },
                                { value: 'opensea', label: 'OpenSea' },
                            ]}
                        />

                        <SimpleDropdown
                            value={listingProductType}
                            onChange={(value) => {
                                setListingProductType(value)
                                analytics.trackFilterApplied('listing_product_type', value)
                            }}
                            options={[
                                { value: 'all', label: 'Product Type' },
                                { value: 'Single', label: 'Singles' },
                                { value: 'Box', label: 'Boxes' },
                                { value: 'Pack', label: 'Packs' },
                            ]}
                        />

                        <SimpleDropdown
                            value={listingTreatment}
                            onChange={(value) => {
                                setListingTreatment(value)
                                analytics.trackFilterApplied('listing_treatment', value)
                            }}
                            options={[
                                { value: 'all', label: 'Treatment' },
                                { value: 'Classic Paper', label: 'Classic Paper' },
                                { value: 'Classic Foil', label: 'Classic Foil' },
                                { value: 'Foil', label: 'Foil' },
                            ]}
                        />
                    </div>
                </div>

                {/* Results Bar */}
                <div className="px-4 py-2 border-b border-border bg-background/30 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        {listingsLoading ? (
                            <>
                                <RefreshCWIcon size={14} className="animate-spin text-muted-foreground" />
                                <span>Loading listings...</span>
                            </>
                        ) : (
                            <>
                                <span className="font-medium text-foreground">{listingsData?.total || 0}</span>
                                <span>listings</span>
                                {listingsFetching && (
                                    <RefreshCWIcon size={14} className="animate-spin text-muted-foreground" />
                                )}
                            </>
                        )}
                    </div>
                    <div className="flex items-center gap-3">
                        <SimpleDropdown
                            value={listingSortBy}
                            onChange={(value) => setListingSortBy(value)}
                            options={[
                                { value: 'date', label: 'Most Recent' },
                                { value: 'price', label: 'Price' },
                            ]}
                        />
                        {/* View Toggle */}
                        <div className="flex items-center rounded-lg border border-border overflow-hidden">
                            <button
                                onClick={() => setListingViewMode('list')}
                                className={clsx(
                                    'p-2 transition-colors',
                                    listingViewMode === 'list'
                                        ? 'bg-primary text-primary-foreground'
                                        : 'bg-background hover:bg-muted text-muted-foreground'
                                )}
                                title="Grid view"
                            >
                                <LayoutGrid className="w-4 h-4" />
                            </button>
                            <button
                                onClick={() => setListingViewMode('table')}
                                className={clsx(
                                    'p-2 transition-colors',
                                    listingViewMode === 'table'
                                        ? 'bg-primary text-primary-foreground'
                                        : 'bg-background hover:bg-muted text-muted-foreground'
                                )}
                                title="List view"
                            >
                                <List className="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                </div>
            </div>

                {/* Tab Content - Products */}
                <div className={activeTab === 'products' ? 'flex-1 flex flex-col' : 'hidden'}>
                  {isLoading ? (
                      <>
                          {/* Mobile skeleton */}
                          <div className="md:hidden">
                              <MobileCardListSkeleton count={8} />
                          </div>
                          {/* Desktop skeleton */}
                          <div className="hidden md:block">
                              <HomeTableSkeleton rows={10} />
                          </div>
                      </>
                  ) : (
                      <>
                          {/* Mobile: Card list view */}
                          <div className="md:hidden p-3 flex-1 overflow-y-auto">
                              <MobileCardList
                                  items={mobileItems}
                                  emptyState={
                                      <div className="text-center text-muted-foreground text-xs uppercase py-12">
                                          No market data found.
                                      </div>
                                  }
                              />
                          </div>
                          {/* Desktop: Table or List view based on viewMode */}
                          {viewMode === 'table' ? (
                          <div className="hidden md:block flex-1 min-h-0 overflow-x-auto scrollbar-thin scrollbar-thumb-border scrollbar-track-transparent">
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
                                                  onMouseEnter={() => prefetchCardDetail(row.original.slug || String(row.original.id))}
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
                          ) : (
                          /* Grid view - TCGPlayer style 2-column cards */
                          <div className="flex-1 overflow-y-auto p-4">
                              {filteredCards.length > 0 ? (
                                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4">
                                      {filteredCards.slice(0, table.getState().pagination.pageSize).map(card => (
                                          <div
                                              key={card.id}
                                              onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: card.slug || String(card.id) } })}
                                              className="flex gap-4 p-4 rounded-lg border border-border bg-card hover:border-primary/50 hover:shadow-lg transition-all cursor-pointer"
                                          >
                                              {/* Card Image - Trading card aspect ratio */}
                                              <div className="shrink-0 w-[120px] h-[168px] rounded-lg overflow-hidden bg-muted border border-border">
                                                  {card.image_url ? (
                                                      <img src={card.image_url} alt={card.name} className="w-full h-full object-cover" loading="lazy" />
                                                  ) : (
                                                      <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                                                          <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                                          </svg>
                                                      </div>
                                                  )}
                                              </div>
                                              {/* Card Info */}
                                              <div className="flex-1 min-w-0 flex flex-col">
                                                  {/* Name */}
                                                  <h3 className="font-bold text-base hover:underline truncate">
                                                      {card.name}
                                                  </h3>
                                                  {/* Set name */}
                                                  <div className="text-sm text-primary hover:underline mt-1">
                                                      {card.set_name}
                                                  </div>
                                                  {/* Rarity */}
                                                  {card.rarity_name && (
                                                      <div className="mt-0.5">
                                                          <RarityBadge rarity={card.rarity_name} size="sm" />
                                                      </div>
                                                  )}
                                                  {/* Listings count */}
                                                  <div className="text-sm text-muted-foreground mt-3 underline">
                                                      {card.inventory || 0} listings from
                                                  </div>
                                                  {/* Price */}
                                                  <div className="text-2xl font-bold mt-1">
                                                      {(card.floor_price || card.vwap) ? `$${(card.floor_price || card.vwap)?.toFixed(2)}` : '—'}
                                                  </div>
                                                  {/* Market Price */}
                                                  {card.latest_price && card.latest_price > 0 && (
                                                      <div className="text-sm text-muted-foreground mt-1">
                                                          Market Price: <span className="text-primary">${card.latest_price.toFixed(2)}</span>
                                                      </div>
                                                  )}
                                              </div>
                                          </div>
                                      ))}
                                  </div>
                              ) : (
                                  <div className="h-32 flex items-center justify-center text-muted-foreground text-xs uppercase">
                                      No market data found.
                                  </div>
                              )}
                          </div>
                          )}
                          {/* Pagination - hidden on mobile */}
                          <div className="border-t border-border px-3 py-2 hidden md:flex items-center justify-between bg-muted/20">
                              <div className="text-xs text-muted-foreground">
                                  Showing {table.getState().pagination.pageIndex * table.getState().pagination.pageSize + 1} to {Math.min((table.getState().pagination.pageIndex + 1) * table.getState().pagination.pageSize, table.getFilteredRowModel().rows.length)} of {table.getFilteredRowModel().rows.length} assets
                              </div>
                              <div className="flex items-center gap-2">
                                  <IconButton
                                      icon={<ChevronLeft />}
                                      aria-label="Previous page"
                                      variant="outline-subtle"
                                      size="icon-sm"
                                      onClick={() => table.previousPage()}
                                      disabled={!table.getCanPreviousPage()}
                                  />
                                  <div className="text-xs font-mono">
                                      Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
                                  </div>
                                  <IconButton
                                      icon={<ChevronRight />}
                                      aria-label="Next page"
                                      variant="outline-subtle"
                                      size="icon-sm"
                                      onClick={() => table.nextPage()}
                                      disabled={!table.getCanNextPage()}
                                  />
                              </div>
                          </div>
                      </>
                  )}
                </div>

                {/* Tab Content - Listings */}
                <div className={activeTab === 'listings' ? 'flex-1 flex flex-col' : 'hidden'}>
                  {listingsLoading ? (
                      <div className="p-12 text-center">
                          <div className="animate-spin w-6 h-6 border-2 border-primary border-t-transparent rounded-full mx-auto mb-4"></div>
                          <div className="text-xs uppercase text-muted-foreground animate-pulse">Loading listings...</div>
                      </div>
                  ) : (
                      <>
                          {listingViewMode === 'list' ? (
                          /* Grid view - similar to Products */
                          <div className="flex-1 overflow-y-auto p-4">
                              {listingsData?.items.length ? (
                                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4">
                                      {listingsData.items.map(listing => (
                                          <div
                                              key={listing.id}
                                              className="flex gap-4 p-4 rounded-lg border border-border bg-card"
                                          >
                                              {/* Card Image */}
                                              <div className="shrink-0 w-[100px] h-[140px] rounded-lg overflow-hidden bg-muted border border-border">
                                                  {listing.card_image_url ? (
                                                      <img src={listing.card_image_url} alt={listing.card_name} className="w-full h-full object-cover" loading="lazy" />
                                                  ) : (
                                                      <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                                                          <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                                          </svg>
                                                      </div>
                                                  )}
                                              </div>
                                              {/* Listing Info */}
                                              <div className="flex-1 min-w-0 flex flex-col">
                                                  {/* Card name */}
                                                  <h3 className="font-bold text-base truncate">
                                                      {listing.card_name}
                                                  </h3>
                                                  {/* Platform badge */}
                                                  <div className="flex items-center gap-2 mt-1">
                                                      <PlatformBadge platform={listing.platform} size="sm" />
                                                      <span className="text-xs text-muted-foreground">{listing.product_type}</span>
                                                  </div>
                                                  {/* Treatment */}
                                                  {listing.treatment && (
                                                      <div className="text-sm text-muted-foreground mt-1">
                                                          {listing.treatment}
                                                      </div>
                                                  )}
                                                  {/* Seller */}
                                                  {listing.seller_name && (
                                                      <div className="text-xs text-muted-foreground mt-auto">
                                                          {listing.seller_name}
                                                          {listing.seller_feedback_percent && ` (${listing.seller_feedback_percent}%)`}
                                                      </div>
                                                  )}
                                                  {/* Price */}
                                                  <div className="text-2xl font-bold mt-2">
                                                      ${listing.price.toFixed(2)}
                                                  </div>
                                                  {/* Floor comparison */}
                                                  {listing.floor_price && (
                                                      <div className="text-sm text-muted-foreground">
                                                          Floor: <span className="text-primary">${listing.floor_price.toFixed(2)}</span>
                                                      </div>
                                                  )}
                                                  {/* View listing button */}
                                                  {listing.url && (
                                                      <a
                                                          href={listing.url}
                                                          target="_blank"
                                                          rel="noopener noreferrer"
                                                          onClick={(e) => e.stopPropagation()}
                                                          className="mt-2 flex items-center justify-center gap-2 px-3 py-2 bg-brand-700 hover:bg-brand-800 text-white rounded-lg text-sm font-bold uppercase"
                                                      >
                                                          View Listing
                                                          <ExternalLink className="w-4 h-4" />
                                                      </a>
                                                  )}
                                              </div>
                                          </div>
                                      ))}
                                  </div>
                              ) : (
                                  <div className="h-32 flex items-center justify-center text-muted-foreground text-xs uppercase">
                                      No listings found.
                                  </div>
                              )}
                          </div>
                          ) : (
                          /* Table view */
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
                                                  className="hover:bg-muted/30 transition-colors"
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
                                                                  priceDelta > 20 ? "text-rose-500" :
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
                          )}
                          {/* Listings count footer */}
                          <div className="border-t border-border px-3 py-2 flex items-center justify-between bg-muted/20">
                              <div className="text-xs text-muted-foreground">
                                  {listingsData?.total ? (
                                      <>
                                          Showing {listingPage * LISTINGS_PER_PAGE + 1} to {Math.min((listingPage + 1) * LISTINGS_PER_PAGE, listingsData.total)} of {listingsData.total} listings
                                          {listingsFetching && <span className="ml-2 text-primary">Loading...</span>}
                                      </>
                                  ) : (
                                      <span>No listings found</span>
                                  )}
                              </div>
                              <div className="flex items-center gap-2">
                                  <IconButton
                                      icon={<ChevronLeft />}
                                      aria-label="Previous page"
                                      variant="ghost"
                                      size="icon-sm"
                                      onClick={() => setListingPage(p => Math.max(0, p - 1))}
                                      disabled={listingPage === 0}
                                  />
                                  <span className="text-xs text-muted-foreground">
                                      Page {listingPage + 1} of {Math.ceil((listingsData?.total || 0) / LISTINGS_PER_PAGE)}
                                  </span>
                                  <IconButton
                                      icon={<ChevronRight />}
                                      aria-label="Next page"
                                      variant="ghost"
                                      size="icon-sm"
                                      onClick={() => setListingPage(p => p + 1)}
                                      disabled={!listingsData?.hasMore}
                                  />
                              </div>
                          </div>
                      </>
                  )}
                </div>
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
