import { createFileRoute, useParams, useNavigate, Link } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../utils/auth'
import { analytics } from '~/services/analytics'
import { ArrowLeft, TrendingUp, Wallet, Filter, ChevronLeft, ChevronRight, X, ExternalLink, Calendar, Flag, AlertTriangle } from 'lucide-react'
import { ColumnDef, flexRender, getCoreRowModel, useReactTable, getPaginationRowModel, getFilteredRowModel } from '@tanstack/react-table'
import { useMemo, useState, useEffect, lazy, Suspense } from 'react'
import { Tooltip } from '../components/ui/tooltip'

// Lazy load chart component (378KB recharts bundle) - only loads when needed
const PriceHistoryChart = lazy(() => import('../components/charts/PriceHistoryChart'))
import clsx from 'clsx'
import { AddToPortfolioModal } from '../components/AddToPortfolioModal'
import { TreatmentBadge } from '../components/TreatmentBadge'
import { CardActionSplitButton } from '../components/CardActionSplitButton'
import { ProductSubtypeBadge, getSubtypeColor } from '../components/ProductSubtypeBadge'
import { LoginUpsellButton } from '../components/LoginUpsellOverlay'
import { MetaVote } from '../components/MetaVote'
import { useCurrentUser } from '../context/UserContext'

type CardDetail = {
  id: number
  name: string
  slug?: string
  set_name: string
  rarity_id: number
  rarity_name?: string
  latest_price?: number
  volume_30d?: number
  price_delta_24h?: number
  lowest_ask?: number
  lowest_ask_by_variant?: Record<string, number> // Lowest ask per variant {treatment/subtype: price}
  inventory?: number
  max_price?: number // Added max_price type
  product_type?: string // Single, Box, Pack, Proof, etc.
  floor_price?: number // Avg of 4 lowest sales (30d) - THE standard price (cheapest variant)
  floor_by_variant?: Record<string, number> // Floor price per variant {treatment/subtype: price}
  fair_market_price?: number // FMP calculated from formula
  vwap?: number // Volume-weighted average price
  // Carde.io data
  card_type?: string // Wonder, Item, Spell, Land, Token, Tracker
  orbital?: string // Heliosynth, Thalwind, Petraia, Solfera, Boundless, Umbrathene
  orbital_color?: string // Hex color e.g., #a07836
  card_number?: string // e.g., "143"
  cardeio_image_url?: string // Official high-res card image
  // Calculated fields for display
  market_cap?: number
}

type MarketPrice = {
    id: number
    price: number
    title: string
    sold_date?: string | null  // Can be NULL - use scraped_at as fallback
    scraped_at: string         // Always present - fallback for NULL sold_date
    listed_at?: string | null  // When listing was first seen (for active->sold tracking)
    listing_type: string
    treatment?: string
    product_subtype?: string   // Collector Booster Box, Play Bundle, etc.
    quantity?: number          // Number of units in listing
    bid_count?: number
    url?: string
    image_url?: string
    description?: string
    seller_name?: string
    seller_feedback_score?: number
    seller_feedback_percent?: number
    condition?: string
    shipping_cost?: number
    traits?: Array<{ trait_type: string; value: string }>  // NFT traits from OpenSea
}

type MarketSnapshot = {
    id: number
    card_id: number
    min_price?: number
    max_price?: number
    avg_price?: number
    volume?: number
    lowest_ask?: number
    highest_bid?: number
    inventory?: number
    timestamp: string
    platform?: string
}

// Helper to detect PSA graded cards from title
function isPSAGraded(title: string): { graded: boolean; grade?: string } {
    const match = title.match(/\bPSA\s*(\d+)/i)
    if (match) {
        return { graded: true, grade: match[1] }
    }
    // Also check for BGS, CGC
    const bgsMatch = title.match(/\bBGS\s*(\d+(?:\.\d)?)/i)
    if (bgsMatch) {
        return { graded: true, grade: `BGS ${bgsMatch[1]}` }
    }
    const cgcMatch = title.match(/\bCGC\s*(\d+(?:\.\d)?)/i)
    if (cgcMatch) {
        return { graded: true, grade: `CGC ${cgcMatch[1]}` }
    }
    return { graded: false }
}

// Get treatment color based on category (handles messy treatment names)
// Colors match TreatmentBadge component for consistency
function getTreatmentColor(treatment: string): string {
    const t = (treatment || '').toLowerCase()

    // === ULTRA RARE ===
    // Formless Foil - premium foil (fuchsia/magenta)
    if (t.includes('formless')) return '#d946ef'

    // Serialized / OCM - highest tier (gold/yellow)
    if (t.includes('serial') || t.includes('ocm')) return '#facc15'

    // 1/1 or Legendary (rose/red)
    if (t === '1/1' || t.includes('legendary')) return '#fb7185'

    // === RARE ===
    // Stonefoil (stone/warm gray)
    if (t.includes('stone')) return '#a8a29e'

    // Starfoil (violet)
    if (t.includes('star')) return '#a78bfa'

    // Full Art Foil (emerald)
    if (t.includes('full art') && t.includes('foil')) return '#34d399'

    // Animated NFT (cyan)
    if (t.includes('animated')) return '#22d3ee'

    // === UNCOMMON ===
    // Classic Foil / other foils (sky blue)
    if (t.includes('foil') || t.includes('holo') || t.includes('refractor')) return '#38bdf8'

    // Full Art (indigo)
    if (t.includes('full art') || t.includes('alt art') || t.includes('extended')) return '#818cf8'

    // Prerelease (pink)
    if (t.includes('prerelease')) return '#f472b6'

    // Promo (rose)
    if (t.includes('promo')) return '#fb7185'

    // === GRADED / PRESLAB ===
    // Preslab TAG 10 (premium gold)
    if (t.includes('preslab') && t.includes('10')) return '#fcd34d'

    // Preslab TAG 9 (bright green)
    if (t.includes('preslab') && t.includes('9')) return '#7dd3a8'

    // Preslab TAG 8 (sky blue)
    if (t.includes('preslab') && t.includes('8')) return '#38bdf8'

    // Preslab TAG (ungraded/other - teal)
    if (t.includes('preslab') || t.includes('tag')) return '#2dd4bf'

    // Proof / Sample (amber)
    if (t.includes('proof') || t.includes('sample')) return '#fbbf24'

    // Error / Errata (red)
    if (t.includes('error') || t.includes('errata')) return '#f87171'

    // === SEALED PRODUCTS ===
    // Factory Sealed (green)
    if (t.includes('factory') && t.includes('seal')) return '#7dd3a8'

    // Sealed (emerald)
    if (t.includes('seal')) return '#34d399'

    // === DEFAULT ===
    // Classic Paper / Standard (zinc gray)
    return '#a1a1aa'
}

// Simplify treatment name for display
function simplifyTreatment(treatment: string): string {
    const t = (treatment || '').toLowerCase()
    if (t.includes('serial') || t.includes('ocm')) return 'Serialized'
    if (t.includes('formless')) return 'Formless'
    if (t.includes('foil') || t.includes('holo')) return 'Foil'
    if (t.includes('promo') || t.includes('prerelease')) return 'Promo'
    if (t.includes('alt') || t.includes('alternate')) return 'Alt Art'
    if (t.includes('proof')) return 'Proof'
    if (t.includes('paper') || t === 'classic' || t === 'standard' || t === 'regular' || t === 'normal') return 'Paper'
    // For NFT items, return the treatment as-is (could be token name or actual trait)
    return treatment || 'Paper'
}

// Extract treatment from title for items where treatment field is generic (e.g., "NFT")
function extractTreatmentFromTitle(title: string): string | null {
    if (!title) return null
    const t = title.toLowerCase()
    if (t.includes('serial') || t.includes('ocm') || t.includes('/50') || t.includes('/100') || t.includes('/250')) return 'Serialized'
    if (t.includes('formless')) return 'Formless Foil'
    if (t.includes('foil') || t.includes('holo')) return 'Classic Foil'
    if (t.includes('promo') || t.includes('prerelease')) return 'Promo'
    if (t.includes('proof')) return 'Proof'
    return null
}

// Server-side loader for SEO meta tags
const API_URL = import.meta.env.VITE_API_URL || 'https://wonderstracker.com/api/v1'

async function fetchCardForSEO(cardId: string) {
  try {
    const [cardRes, marketRes] = await Promise.all([
      fetch(`${API_URL}/cards/${cardId}`),
      fetch(`${API_URL}/cards/${cardId}/market`),
    ])

    if (!cardRes.ok) return null

    const card = await cardRes.json()
    const market = marketRes.ok ? await marketRes.json() : {}

    return {
      ...card,
      latest_price: market.avg_price,
      volume_30d: market.volume,
      lowest_ask: market.lowest_ask,
    }
  } catch {
    return null
  }
}

export const Route = createFileRoute('/cards/$cardId')({
  component: CardDetail,
  loader: async ({ params }) => {
    const card = await fetchCardForSEO(params.cardId)
    return { card }
  },
})

// Re-export component for potential lazy loading
export { CardDetail }

type TimeRange = '7d' | '30d' | '90d' | 'all'
type ChartType = 'line' | 'scatter'

function CardDetail() {
  const { cardId } = useParams({ from: Route.id })
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [treatmentFilter, setTreatmentFilter] = useState<string>('all')
  const [selectedListing, setSelectedListing] = useState<MarketPrice | null>(null)
  const [timeRange, setTimeRange] = useState<TimeRange>('all')
  const [chartType, setChartType] = useState<ChartType>('line')
  const [showAddModal, setShowAddModal] = useState(false)
  const [showReportModal, setShowReportModal] = useState(false)
  const [reportReason, setReportReason] = useState<string>('')
  const [reportNotes, setReportNotes] = useState<string>('')
  const [reportSubmitting, setReportSubmitting] = useState(false)
  const [reportSubmitted, setReportSubmitted] = useState(false)

  const { user: currentUser } = useCurrentUser()
  const isLoggedIn = !!currentUser

  // Track card listing view (with session-based milestone tracking)
  useEffect(() => {
    if (cardId) {
      analytics.trackCardViewWithSession(cardId)
    }
  }, [cardId])

  // Fetch Card Data
  const { data: card, isLoading: isLoadingCard } = useQuery({
    queryKey: ['card', cardId],
    queryFn: async () => {
      // First get card basic info
      const basic = await api.get(`cards/${cardId}`).json<CardDetail>()
      // Then get market snapshot
      try {
          const market = await api.get(`cards/${cardId}/market`).json<any>()
          // Consistent priority: prefer live data from /cards/{id} over snapshot from /cards/{id}/market
          // basic.* = computed live from MarketPrice table
          // market.* = from MarketSnapshot (historical aggregate)
          return {
              ...basic,
              latest_price: basic.latest_price ?? market.avg_price,
              volume_30d: basic.volume_30d ?? market.volume,
              lowest_ask: basic.lowest_ask ?? market.lowest_ask,
              inventory: basic.inventory ?? market.inventory,
              max_price: basic.max_price ?? market.max_price,
              product_type: basic.product_type,
              market_cap: (basic.floor_price || basic.latest_price || market.avg_price || 0) * (basic.volume_30d || market.volume || 0)
          }
      } catch (e) {
          // If market data fails (404 or 401), return basic info
          return basic
      }
    },
    staleTime: 2 * 60 * 1000, // 2 minutes - card data updates infrequently
  })

  // Fetch Sales History (sold + active listings) - paginated for performance
  // Initial load: 100 recent sales (enough for chart), load more on demand
  const { data: historyData, isLoading: isLoadingHistory } = useQuery({
      queryKey: ['card-history', cardId],
      queryFn: async () => {
          try {
            // Fetch recent sold listings (paginated=true returns {items, total, hasMore})
            const soldResponse = await api.get(`cards/${cardId}/history?limit=100&paginated=true`).json<{items: MarketPrice[], total: number, hasMore: boolean}>()
            const activeData = await api.get(`cards/${cardId}/active?limit=100`).json<MarketPrice[]>().catch(() => [])
            // Combine: active listings first, then sold by date
            return {
              items: [...activeData, ...soldResponse.items],
              total: soldResponse.total,
              hasMore: soldResponse.hasMore,
              activeCount: activeData.length
            }
          } catch (e) {
              return { items: [], total: 0, hasMore: false, activeCount: 0 }
          }
      },
      staleTime: 2 * 60 * 1000, // 2 minutes
  })

  // Backwards compat: extract items array for existing code
  const history = historyData?.items ?? []

  // Fetch Snapshot History (for OpenSea/NFT items that don't have individual sales)
  const { data: snapshots } = useQuery({
      queryKey: ['card-snapshots', cardId],
      queryFn: async () => {
          try {
            return await api.get(`cards/${cardId}/snapshots?days=365&limit=500`).json<MarketSnapshot[]>()
          } catch (e) {
              return []
          }
      },
      // Only fetch if we have no sales history (OpenSea items)
      enabled: !isLoadingHistory,
      staleTime: 5 * 60 * 1000, // 5 minutes - snapshots change slowly
  })

  // Fetch FMP by Treatment data
  type TreatmentFMP = {
      treatment: string
      fmp: number | null
      median_price: number | null
      min_price: number | null
      max_price: number | null
      avg_price: number | null
      sales_count: number
      treatment_multiplier: number
      liquidity_adjustment: number
  }
  type PricingData = {
      card_id: number
      card_name: string
      product_type: string
      fair_market_price: number | null
      floor_price: number | null
      calculation_method: 'formula' | 'median'  // formula for Singles, median for others
      breakdown: {
          base_set_price: number | null
          rarity_multiplier: number
          treatment_multiplier: number
          condition_multiplier: number
          liquidity_adjustment: number
      } | null
      by_treatment: TreatmentFMP[]
  }
  const { data: pricingData, isLoading: isLoadingPricing } = useQuery({
      queryKey: ['card-pricing', cardId],
      queryFn: async () => {
          try {
            return await api.get(`cards/${cardId}/pricing`).json<PricingData>()
          } catch (e) {
              return null
          }
      },
      staleTime: 5 * 60 * 1000, // 5 minutes - pricing is computed, changes slowly
  })

  // Determine if this is an OpenSea/NFT item (no individual sales, only snapshots)
  const isOpenSeaItem = useMemo(() => {
      if (!history || history.length === 0) return true
      // Check if it's a Proof type or has opensea platform in snapshots
      if (card?.product_type === 'Proof') return true
      return false
  }, [history, card])

  // Track Card (now opens modal instead of direct mutation)

  const columns = useMemo<ColumnDef<MarketPrice>[]>(() => [
      {
          accessorKey: 'sold_date',
          header: 'Date',
          cell: ({ row }) => {
              const soldDate = row.original.sold_date
              const listedAt = row.original.listed_at
              const scrapedAt = row.original.scraped_at
              const isActive = row.original.listing_type === 'active'

              if (soldDate) {
                  return new Date(soldDate).toLocaleDateString()
              } else if (isActive && listedAt) {
                  // For active listings, show when it was first listed
                  return (
                      <Tooltip content="First seen">
                          <span className="text-muted-foreground">
                              {new Date(listedAt).toLocaleDateString()}
                          </span>
                      </Tooltip>
                  )
              } else if (scrapedAt) {
                  // Fallback to scraped_at
                  return (
                      <span className="text-muted-foreground">
                          {new Date(scrapedAt).toLocaleDateString()}
                      </span>
                  )
              }
              return 'N/A'
          }
      },
      {
          accessorKey: 'price',
          header: () => <div className="text-right">Price</div>,
          cell: ({ row }) => <div className="text-right font-mono font-bold">${row.original.price.toFixed(2)}</div>
      },
      {
          accessorKey: 'treatment',
          header: 'Treatment',
          cell: ({ row }) => {
              // If treatment is "NFT" or empty, try to extract from title
              const rawTreatment = row.original.treatment
              const isGeneric = !rawTreatment || rawTreatment.toLowerCase() === 'nft'
              const effectiveTreatment = isGeneric
                  ? (extractTreatmentFromTitle(row.original.title) || 'Classic Paper')
                  : rawTreatment

              return <TreatmentBadge treatment={effectiveTreatment} size="xs" />
          }
      },
      {
          accessorKey: 'product_subtype',
          header: 'Subtype',
          cell: ({ row }) => {
              const subtype = row.original.product_subtype
              if (!subtype) return null
              return <ProductSubtypeBadge subtype={subtype} size="xs" />
          }
      },
      {
          accessorKey: 'title',
          header: 'Listing Title',
          cell: ({ row }) => {
              const grading = isPSAGraded(row.original.title)
              return (
                  <div className="flex items-center gap-2">
                      {grading.graded && (
                          <span className="px-1.5 py-0.5 rounded text-[9px] uppercase font-bold border border-amber-700 bg-amber-900/30 text-amber-400 shrink-0">
                              PSA {grading.grade}
                          </span>
                      )}
                      <Tooltip content={row.original.title}>
                          <div className="truncate max-w-lg text-xs text-muted-foreground">{row.original.title}</div>
                      </Tooltip>
                  </div>
              )
          }
      },
      {
          accessorKey: 'listing_type',
          header: () => <div className="text-right text-xs">Type</div>,
          cell: ({ row }) => (
            <div className="text-right">
                <span className={clsx("px-1.5 py-0.5 rounded text-[10px] uppercase font-bold border", 
                    row.original.listing_type === 'sold' ? "border-brand-700 bg-brand-800/20 text-brand-400" : "border-blue-800 bg-blue-900/20 text-blue-500")}>
                    {row.original.listing_type || 'Sold'}
                </span>
            </div>
          )
      }
  ], [])

  const filteredData = useMemo(() => {
      if (!history) return []
      if (treatmentFilter === 'all') return history
      // Handle subtype filter (prefixed with "subtype:")
      if (treatmentFilter.startsWith('subtype:')) {
          const subtype = treatmentFilter.replace('subtype:', '')
          return history.filter(h => h.product_subtype === subtype)
      }
      // Handle treatment filter
      return history.filter(h => {
          const t = h.treatment || 'Classic Paper'
          return t === treatmentFilter
      })
  }, [history, treatmentFilter])

  const table = useReactTable({
      data: filteredData,
      columns,
      getCoreRowModel: getCoreRowModel(),
      getPaginationRowModel: getPaginationRowModel(),
      initialState: {
          pagination: {
              pageSize: 10,
          },
      },
  })

  // Prepare Chart Data - Individual points per sale with time range filtering
  const chartData = useMemo(() => {
      if (!history) return []

      // Calculate time range cutoff
      const now = new Date()
      let cutoffDate: Date | null = null
      switch (timeRange) {
          case '7d':
              cutoffDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
              break
          case '30d':
              cutoffDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
              break
          case '90d':
              cutoffDate = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000)
              break
          case 'all':
          default:
              cutoffDate = null
      }

      // 1. Filter valid sold listings first
      // Use sold_date OR scraped_at as fallback (matches backend COALESCE logic)
      const validSold = history.filter(h => {
          const validPrice = h.price !== undefined && h.price !== null && !isNaN(Number(h.price)) && Number(h.price) > 0
          const effectiveDate = h.sold_date || h.scraped_at
          const validDate = effectiveDate && !isNaN(new Date(effectiveDate).getTime())
          const isSold = h.listing_type === 'sold' || !h.listing_type
          if (!validPrice || !validDate || !isSold) return false

          // Apply time range filter
          if (cutoffDate) {
              const saleDate = new Date(effectiveDate)
              return saleDate >= cutoffDate
          }
          return true
      })

      // 2. Sort sold by date, then by price (using effectiveDate pattern)
      const sortedSold = validSold.sort((a, b) => {
          const aDate = a.sold_date || a.scraped_at
          const bDate = b.sold_date || b.scraped_at
          const dateCompare = new Date(aDate).getTime() - new Date(bDate).getTime()
          if (dateCompare !== 0) return dateCompare
          return a.price - b.price
      })

      // 3. Map sold listings to chart format
      const dateCount: Record<string, number> = {}
      const soldData = sortedSold.map((h, index) => {
          const effectiveDate = h.sold_date || h.scraped_at
          const saleDate = new Date(effectiveDate)
          const dateKey = saleDate.toISOString().split('T')[0]

          dateCount[dateKey] = (dateCount[dateKey] || 0) + 1
          const offsetIndex = dateCount[dateKey] - 1
          const offsetMs = offsetIndex * 2 * 60 * 60 * 1000
          const adjustedTimestamp = saleDate.getTime() + offsetMs

          const treatment = h.treatment || 'Classic Paper'
          const isCardSealed = card?.rarity_name?.toUpperCase() === 'SEALED'
          // For sealed products, use subtype color; otherwise use treatment color
          const pointColor = isCardSealed ? getSubtypeColor(h.product_subtype) : getTreatmentColor(treatment)
          return {
              id: `${h.id}-${index}`,
              date: saleDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' }),
              timestamp: adjustedTimestamp,
              x: index,
              price: Number(h.price),
              treatment,
              product_subtype: h.product_subtype,
              treatmentColor: pointColor,
              treatmentSimple: simplifyTreatment(treatment),
              title: h.title,
              listing_type: 'sold',
              isGraded: isPSAGraded(h.title).graded,
              grade: isPSAGraded(h.title).grade,
              isActive: false
          }
      })

      // 4. Add active listings at the right edge (current time)
      const activeListings = history.filter(h => {
          const validPrice = h.price !== undefined && h.price !== null && !isNaN(Number(h.price)) && Number(h.price) > 0
          return h.listing_type === 'active' && validPrice
      })

      // Place active listings at the right side of chart, spaced out by price
      // Sort by price to spread vertically, then space horizontally
      const sortedActive = [...activeListings].sort((a, b) => a.price - b.price)
      const nowTime = now.getTime()
      // Calculate spacing: use 6 hours between each active listing for visual clarity
      const activeData = sortedActive.map((h, index) => {
          const treatment = h.treatment || 'Classic Paper'
          const isCardSealed = card?.rarity_name?.toUpperCase() === 'SEALED'
          const pointColor = isCardSealed ? getSubtypeColor(h.product_subtype) : getTreatmentColor(treatment)
          return {
              id: `active-${h.id}-${index}`,
              date: 'Active',
              timestamp: nowTime + (index * 6 * 60 * 60 * 1000), // 6 hours offset per listing
              x: soldData.length + index,
              price: Number(h.price),
              treatment,
              product_subtype: h.product_subtype,
              treatmentColor: pointColor,
              treatmentSimple: simplifyTreatment(treatment),
              title: h.title,
              listing_type: 'active',
              isGraded: isPSAGraded(h.title).graded,
              grade: isPSAGraded(h.title).grade,
              isActive: true
          }
      })

      return [...soldData, ...activeData]
  }, [history, timeRange, card?.rarity_name])

  // Calculate total sales count (ignoring time filter) for context
  const totalAllTimeSales = useMemo(() => {
      if (!history) return 0
      return history.filter(h => {
          const validPrice = h.price !== undefined && h.price !== null && !isNaN(Number(h.price)) && Number(h.price) > 0
          const validDate = h.sold_date && !isNaN(new Date(h.sold_date).getTime())
          const isSold = h.listing_type === 'sold' || !h.listing_type
          return validPrice && validDate && isSold
      }).length
  }, [history])

  // Calculate chart statistics
  const chartStats = useMemo(() => {
      if (!chartData.length) return null
      const prices = chartData.map(d => d.price)
      const minPrice = Math.min(...prices)
      const maxPrice = Math.max(...prices)
      const avgPrice = prices.reduce((a, b) => a + b, 0) / prices.length
      const firstPrice = prices[0]
      const lastPrice = prices[prices.length - 1]
      let priceChange = firstPrice > 0 ? ((lastPrice - firstPrice) / firstPrice) * 100 : 0

      // Cap trend at ±100% to avoid crazy numbers
      priceChange = Math.max(-100, Math.min(100, priceChange))

      // Only show meaningful trends (at least 2 data points)
      if (chartData.length < 2) {
          priceChange = 0
      }

      return { minPrice, maxPrice, avgPrice, priceChange, totalSales: chartData.length }
  }, [chartData])
  
  // Get all unique treatments for creating lines
  const chartTreatments = useMemo(() => {
      if (!history) return []
      const treatments = new Set(history.map(h => h.treatment || 'Classic Paper'))
      return Array.from(treatments)
  }, [history])

  // Extract unique treatments for filter
  const uniqueTreatments = useMemo(() => {
      if (!history) return []
      const s = new Set(history.map(h => h.treatment || 'Classic Paper'))
      return Array.from(s)
  }, [history])

  // Check if this is a sealed product (uses subtypes instead of treatments)
  const isSealed = card?.rarity_name?.toUpperCase() === 'SEALED'

  // Get unique subtypes for sealed products
  const uniqueSubtypes = useMemo(() => {
      if (!history || !isSealed) return []
      const s = new Set(history.map(h => h.product_subtype).filter(Boolean))
      return Array.from(s) as string[]
  }, [history, isSealed])

  if (isLoadingCard) {
    return (
        <div className="min-h-screen flex items-center justify-center bg-background text-foreground font-mono">
            <div className="text-center animate-pulse">
                <div className="text-xl uppercase tracking-widest mb-2">Loading Market Data</div>
                <div className="text-xs text-muted-foreground">Accessing secure stream...</div>
            </div>
        </div>
    )
  }

  if (!card) {
    return (
        <div className="min-h-screen flex items-center justify-center bg-background text-foreground font-mono">
            <div className="text-center text-red-500 border border-red-900 p-8 rounded bg-red-950/10">
                <div className="text-xl uppercase tracking-widest mb-2">Card Not Found</div>
                <Link to="/" className="text-sm underline hover:text-foreground">Return to Dashboard</Link>
            </div>
        </div>
    )
  }

  return (
      <>
          <div className="min-h-screen bg-background text-foreground font-mono flex flex-col">
            <div className="flex-1 p-6">
                <div className="max-w-7xl mx-auto">
                    {/* Navigation */}
                    <div className="flex justify-between items-center mb-8">
                        <Link to="/" className="flex items-center gap-2 text-xs uppercase text-muted-foreground hover:text-primary transition-colors border border-transparent hover:border-border rounded px-3 py-1">
                            <ArrowLeft className="w-3 h-3" /> Dashboard
                        </Link>
                        
                        <CardActionSplitButton
                            cardId={card.id}
                            cardName={card.name}
                            onAddToPortfolio={() => setShowAddModal(true)}
                        />
                    </div>
                    
                    {/* Header Section with Background Image */}
                    <div className="mb-10 border-b border-border pb-8 relative overflow-hidden rounded-lg -mx-6 px-6">
                        {/* Background Image with Gradient Scrim */}
                        {card.cardeio_image_url && (
                            <>
                                <div
                                    className="absolute inset-0 bg-cover bg-center bg-no-repeat opacity-50"
                                    style={{ backgroundImage: `url(${card.cardeio_image_url})` }}
                                />
                                <div className="absolute inset-0 bg-gradient-to-r from-background via-background/90 to-background/60" />
                                <div className="absolute inset-0 bg-gradient-to-t from-background via-transparent to-background/30" />
                            </>
                        )}

                        {/* Content */}
                        <div className="relative z-10">
                        {/* Title Section */}
                        <div className="mb-6">
                            <div className="flex items-center gap-3 mb-2 flex-wrap">
                                <span className="bg-muted text-muted-foreground px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider">
                                    ID: {card.id.toString().padStart(4, '0')}
                                </span>
                                {/* Orbital Badge with dynamic color */}
                                {card.orbital && (
                                    <span
                                        className="px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider text-white border"
                                        style={{
                                            backgroundColor: card.orbital_color ? `${card.orbital_color}40` : undefined,
                                            borderColor: card.orbital_color || 'transparent'
                                        }}
                                    >
                                        {card.orbital}
                                    </span>
                                )}
                                {/* Card Type Badge */}
                                {card.card_type && (
                                    <span className="bg-zinc-800/80 text-zinc-300 px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider border border-zinc-700">
                                        {card.card_type}
                                    </span>
                                )}
                                {/* Show different badges for NFT vs regular products */}
                                {card.product_type === 'Proof' || card.name?.toLowerCase().includes('proof') || card.name?.toLowerCase().includes('collector box') ? (
                                    <>
                                        <span className="bg-cyan-900/50 text-cyan-400 px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider border border-cyan-700">
                                            NFT
                                        </span>
                                        <Tooltip content={
                                            card.name?.toLowerCase().includes('character proof') ? '0x05f08b01971cf70bcd4e743a8906790cfb9a8fb8' :
                                            card.name?.toLowerCase().includes('collector box') ? '0x28a11da34a93712b1fde4ad15da217a3b14d9465' : 'Contract Address'
                                        }>
                                            <span className="bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded text-[10px] font-mono tracking-wider border border-zinc-700">
                                                {card.name?.toLowerCase().includes('character proof') ? '0x05f0...a8fb' :
                                                 card.name?.toLowerCase().includes('collector box') ? '0x28a1...d9465' : 'Contract'}
                                                </span>
                                            </Tooltip>
                                        </>
                                    ) : (
                                        <span className="bg-zinc-800/80 text-zinc-300 px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider border border-zinc-700">
                                            Rarity: {card.rarity_name || card.rarity_id}
                                        </span>
                                    )}
                            </div>
                            <h1 className="text-4xl md:text-5xl font-black uppercase tracking-tighter mb-2">
                                {card.card_number && <span className="text-muted-foreground">#{card.card_number} </span>}
                                {card.name}
                            </h1>
                            <div className="text-sm text-muted-foreground uppercase tracking-[0.2em] flex items-center gap-2">
                                <span className="w-2 h-2 bg-primary rounded-full"></span>
                                {card.set_name}
                                {/* Platform indicator for NFTs */}
                                {(card.product_type === 'Proof' || card.name?.toLowerCase().includes('proof') || card.name?.toLowerCase().includes('collector box')) && (
                                    <span className="text-cyan-400 text-[10px] ml-2">• OpenSea</span>
                                )}
                            </div>
                        </div>

                        {/* Metrics Row - Left aligned below title */}
                        <div className="flex flex-wrap gap-8">
                            <div>
                                <div className="text-[10px] text-muted-foreground uppercase mb-1 tracking-wider">
                                    Floor Price
                                    {treatmentFilter !== 'all' && (
                                        <span className="ml-2 text-brand-300">
                                            ({treatmentFilter.startsWith('subtype:') ? treatmentFilter.replace('subtype:', '') : treatmentFilter})
                                        </span>
                                    )}
                                </div>
                                <div className="text-4xl font-mono font-bold text-brand-300">
                                    ${(() => {
                                        // Get variant-specific price if filter is active
                                        const variantKey = treatmentFilter === 'all' ? null :
                                            treatmentFilter.startsWith('subtype:') ? treatmentFilter.replace('subtype:', '') : treatmentFilter
                                        const variantFloor = variantKey ? card.floor_by_variant?.[variantKey] : null
                                        const variantAsk = variantKey ? card.lowest_ask_by_variant?.[variantKey] : null

                                        // Use variant-specific price if available
                                        if (variantFloor) return variantFloor.toFixed(2)
                                        if (variantAsk) return variantAsk.toFixed(2)

                                        // Fall back to overall prices
                                        if (card.floor_price) return card.floor_price.toFixed(2)
                                        if (card.lowest_ask && card.lowest_ask > 0) return card.lowest_ask.toFixed(2)
                                        return card.latest_price?.toFixed(2) || '---'
                                    })()}
                                </div>
                            </div>
                            <div className="border-l border-border pl-8">
                                <div className="text-[10px] text-muted-foreground uppercase mb-1 tracking-wider">
                                    Fair Price
                                </div>
                                {isLoggedIn ? (
                                    <div className="text-4xl font-mono font-bold">
                                        ${pricingData?.fair_market_price?.toFixed(2) || card.vwap?.toFixed(2) || '---'}
                                    </div>
                                ) : (
                                    <Tooltip content="Log in to see our Fair Market Price">
                                        <div className="text-4xl font-mono font-bold blur-sm select-none cursor-help">
                                            $XX.XX
                                        </div>
                                    </Tooltip>
                                )}
                            </div>
                            <div className="border-l border-border pl-8">
                                <div className="text-[10px] text-muted-foreground uppercase mb-1 tracking-wider">30d Vol</div>
                                <div className="text-4xl font-mono font-bold">
                                    {(card.volume_30d || 0).toLocaleString()}
                                </div>
                            </div>
                            {/* Highest Confirmed Sale */}
                            <div className="border-l border-border pl-8">
                                <div className="text-[10px] text-muted-foreground uppercase mb-1 tracking-wider">Highest Sale</div>
                                <div className="text-4xl font-mono font-bold text-brand-400">
                                    ${card.max_price ? card.max_price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '---'}
                                </div>
                            </div>
                            {/* Is Meta - only for single cards, not sealed products */}
                            {!isSealed && <MetaVote cardId={card.id} />}
                        </div>
                        </div>{/* Close z-10 content wrapper */}
                    </div>

                    {/* Stats Grid - Compact inline layout */}
                    <div className="flex flex-wrap items-center gap-6 mb-4 text-sm">
                        <div className="flex items-center gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-brand-300"></div>
                            <span className="text-[10px] text-muted-foreground uppercase">Lowest Ask</span>
                            <span className="font-mono font-bold">
                                {(() => {
                                    // Get variant-specific ask if filter is active
                                    const variantKey = treatmentFilter === 'all' ? null :
                                        treatmentFilter.startsWith('subtype:') ? treatmentFilter.replace('subtype:', '') : treatmentFilter
                                    const variantAsk = variantKey ? card.lowest_ask_by_variant?.[variantKey] : null

                                    // Use variant-specific price if available
                                    if (variantAsk) return `$${variantAsk.toFixed(2)}`

                                    // Fall back to overall prices
                                    return (card.lowest_ask && card.lowest_ask > 0) ? `$${card.lowest_ask.toFixed(2)}` : "---"
                                })()}
                            </span>
                        </div>
                        <div className="flex items-center gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-blue-500"></div>
                            <span className="text-[10px] text-muted-foreground uppercase">Active Listings</span>
                            <span className="font-mono font-bold">{(card.inventory || 0).toLocaleString()}</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-amber-500"></div>
                            <span className="text-[10px] text-muted-foreground uppercase">Vol (USD)</span>
                            <span className="font-mono font-bold">${((card.volume_30d || 0) * (card.floor_price || card.latest_price || 0)).toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})}</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <TrendingUp className="w-3 h-3 text-muted-foreground" />
                            <span className="text-[10px] text-muted-foreground uppercase">{timeRange} Trend</span>
                            {(chartStats?.priceChange ?? 0) === 0 ? (
                                <span className="font-mono text-muted-foreground">-</span>
                            ) : (
                                <span className={clsx("font-mono font-bold", (chartStats?.priceChange ?? 0) > 0 ? "text-brand-300" : "text-red-500")}>
                                    {(chartStats?.priceChange ?? 0) > 0 ? '↑' : '↓'}{Math.abs(chartStats?.priceChange ?? 0).toFixed(1)}%
                                </span>
                            )}
                        </div>
                    </div>

                    {/* Stacked Layout: Chart -> Variant Prices -> FMP -> Sales */}
                    <div className="space-y-4">

                        {/* Chart Section (Full Width) - MOVED TO TOP */}
                        <div>
                            <div className="border border-border rounded bg-card p-1">
                                <div className="w-full bg-muted/10 rounded flex flex-col">
                                    {/* Chart Header with Time Range Buttons */}
                                    <div className="p-4 border-b border-border/50 flex justify-between items-center">
                                        <div className="flex items-center gap-4">
                                            <h3 className="text-xs font-bold uppercase tracking-widest">Price History</h3>
                                            <div className="flex items-center gap-3 text-[10px]">
                                                {chartStats ? (
                                                    <>
                                                        <span className="text-muted-foreground">{chartStats.totalSales} sales</span>
                                                        {chartStats.priceChange !== 0 && (
                                                            <span className={chartStats.priceChange >= 0 ? "text-brand-300" : "text-rose-400"}>
                                                                {chartStats.priceChange >= 0 ? '+' : ''}{chartStats.priceChange.toFixed(1)}%
                                                            </span>
                                                        )}
                                                    </>
                                                ) : null}
                                            </div>
                                        </div>

                                        <div className="flex items-center gap-2">
                                            {/* Chart Type Toggle */}
                                            <div className="flex items-center bg-background rounded border border-border overflow-hidden mr-2">
                                                <button
                                                    onClick={() => setChartType('line')}
                                                    className={clsx(
                                                        "px-3 py-1.5 text-[10px] font-bold uppercase transition-colors",
                                                        chartType === 'line' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'
                                                    )}
                                                >
                                                    Line
                                                </button>
                                                <button
                                                    onClick={() => setChartType('scatter')}
                                                    className={clsx(
                                                        "px-3 py-1.5 text-[10px] font-bold uppercase transition-colors",
                                                        chartType === 'scatter' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'
                                                    )}
                                                >
                                                    Scatter
                                                </button>
                                            </div>

                                            {/* Time Range */}
                                            <div className="flex items-center bg-background rounded border border-border overflow-hidden">
                                                {['7d', '30d', '90d', 'all'].map((range) => (
                                                    <button
                                                        key={range}
                                                        onClick={() => setTimeRange(range as TimeRange)}
                                                        className={clsx(
                                                            "px-3 py-1.5 text-[10px] font-bold uppercase transition-colors",
                                                            timeRange === range ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
                                                        )}
                                                    >
                                                        {range}
                                                    </button>
                                                ))}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Chart Stats Row */}
                                    <div className="px-4 py-2 border-b border-border/30 flex items-center justify-between text-[10px]">
                                        <div className="flex items-center gap-6">
                                            <div className="flex items-center gap-2">
                                                <span className="text-muted-foreground uppercase">Low:</span>
                                                <span className="font-mono text-rose-400">${chartStats?.minPrice?.toFixed(2) || "---"}</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <span className="text-muted-foreground uppercase">High:</span>
                                                <span className="font-mono text-brand-300">${chartStats?.maxPrice?.toFixed(2) || "---"}</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <span className="text-muted-foreground uppercase">Avg:</span>
                                                <span className="font-mono">${chartStats?.avgPrice?.toFixed(2) || "---"}</span>
                                            </div>
                                        </div>

                                        {/* Legend */}
                                        <div className="flex items-center gap-4 flex-wrap">
                                            {chartType === 'scatter' && (
                                                isSealed && uniqueSubtypes.length > 0 ? (
                                                    // Show subtypes for sealed products
                                                    (uniqueSubtypes.map(subtype => (
                                                        <div key={subtype} className="flex items-center gap-1">
                                                            <div
                                                                className="w-2 h-2 rounded-full"
                                                                style={{ backgroundColor: getSubtypeColor(subtype) }}
                                                            />
                                                            <span className="text-muted-foreground text-xs">{subtype}</span>
                                                        </div>
                                                    )))
                                                ) : (
                                                    // Show treatments for regular cards
                                                    (<>
                                                        <div className="flex items-center gap-1">
                                                            <div className="w-2 h-2 rounded-full bg-gray-400"></div>
                                                            <span className="text-muted-foreground">Paper</span>
                                                        </div>
                                                        <div className="flex items-center gap-1">
                                                            <div className="w-2 h-2 rounded-full bg-cyan-400"></div>
                                                            <span className="text-muted-foreground">Foil</span>
                                                        </div>
                                                        <div className="flex items-center gap-1">
                                                            <div className="w-2 h-2 rounded-full bg-pink-400"></div>
                                                            <span className="text-muted-foreground">Formless</span>
                                                        </div>
                                                        <div className="flex items-center gap-1">
                                                            <div className="w-2 h-2 rounded-full bg-amber-400"></div>
                                                            <span className="text-muted-foreground">Serialized</span>
                                                        </div>
                                                    </>)
                                                )
                                            )}
                                            <div className="flex items-center gap-1">
                                                <div className="w-2 h-2 bg-brand-300" style={{ clipPath: "polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)" }}></div>
                                                <span className="text-muted-foreground">Active</span>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Chart - lazy loaded */}
                                    <div className="h-[300px] p-4">
                                        {chartData.length > 0 ? (
                                            <Suspense fallback={
                                                <div className="flex items-center justify-center h-full">
                                                    <div className="text-muted-foreground text-sm">Loading chart...</div>
                                                </div>
                                            }>
                                                <PriceHistoryChart
                                                    data={chartData}
                                                    chartType={chartType}
                                                    floorPrice={card.floor_price ?? undefined}
                                                    fmpPrice={pricingData?.fair_market_price ?? undefined}
                                                />
                                            </Suspense>
                                        ) : (
                                            <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
                                                <div className="text-xs uppercase mb-2">
                                                    {timeRange !== 'all' && totalAllTimeSales > 0
                                                        ? `No sales in last ${timeRange}`
                                                        : 'No sales data available'}
                                                </div>
                                                <div className="text-[10px]">
                                                    {timeRange !== 'all' && totalAllTimeSales > 0 ? (
                                                        <button
                                                            onClick={() => setTimeRange('all')}
                                                            className="text-primary hover:underline"
                                                        >
                                                            View all {totalAllTimeSales} sale{totalAllTimeSales !== 1 ? 's' : ''}
                                                        </button>
                                                    ) : timeRange !== 'all' ? (
                                                        <button
                                                            onClick={() => setTimeRange('all')}
                                                            className="text-primary hover:underline"
                                                        >
                                                            View all time data
                                                        </button>
                                                    ) : (
                                                        'Check back later for price history'
                                                    )}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Variant Price Table - Shows floor and ask per treatment/subtype */}
                        {(card.floor_by_variant && Object.keys(card.floor_by_variant).length > 0) ||
                         (card.lowest_ask_by_variant && Object.keys(card.lowest_ask_by_variant).length > 0) ? (
                            <div className="border border-border rounded bg-card p-4">
                                <h3 className="text-xs font-bold uppercase tracking-widest mb-4 flex items-center gap-2">
                                    Price by Variant
                                    <Tooltip content="Floor = avg of 4 lowest sales. Ask = cheapest active listing.">
                                        <span className="text-muted-foreground cursor-help">ⓘ</span>
                                    </Tooltip>
                                </h3>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-xs">
                                        <thead>
                                            <tr className="border-b border-border">
                                                <th className="text-left py-2 text-muted-foreground uppercase tracking-wider">Variant</th>
                                                <th className="text-right py-2 text-muted-foreground uppercase tracking-wider">Floor</th>
                                                <th className="text-right py-2 text-muted-foreground uppercase tracking-wider">Ask</th>
                                                <th className="text-right py-2 text-muted-foreground uppercase tracking-wider">Δ</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {/* Combine all variants from both floor and ask maps */}
                                            {Array.from(new Set([
                                                ...Object.keys(card.floor_by_variant || {}),
                                                ...Object.keys(card.lowest_ask_by_variant || {})
                                            ])).sort((a, b) => {
                                                // Sort by floor price ascending, then by ask if no floor
                                                const floorA = card.floor_by_variant?.[a] ?? Infinity
                                                const floorB = card.floor_by_variant?.[b] ?? Infinity
                                                if (floorA !== floorB) return floorA - floorB
                                                const askA = card.lowest_ask_by_variant?.[a] ?? Infinity
                                                const askB = card.lowest_ask_by_variant?.[b] ?? Infinity
                                                return askA - askB
                                            }).map((variant) => {
                                                const floor = card.floor_by_variant?.[variant]
                                                const ask = card.lowest_ask_by_variant?.[variant]
                                                const delta = floor && ask ? ((ask - floor) / floor * 100) : null

                                                return (
                                                    <tr key={variant} className="border-b border-border/50 hover:bg-muted/20 transition-colors">
                                                        <td className="py-2">
                                                            <TreatmentBadge treatment={variant} size="xs" />
                                                        </td>
                                                        <td className="text-right py-2 font-mono">
                                                            {floor ? `$${floor.toFixed(2)}` : <span className="text-muted-foreground">---</span>}
                                                        </td>
                                                        <td className="text-right py-2 font-mono">
                                                            {ask ? `$${ask.toFixed(2)}` : <span className="text-muted-foreground">---</span>}
                                                        </td>
                                                        <td className="text-right py-2 font-mono">
                                                            {delta !== null ? (
                                                                <span className={clsx(
                                                                    delta > 0 ? 'text-red-400' : delta < 0 ? 'text-brand-300' : 'text-muted-foreground'
                                                                )}>
                                                                    {delta > 0 ? '+' : ''}{delta.toFixed(0)}%
                                                                </span>
                                                            ) : (
                                                                <span className="text-muted-foreground">---</span>
                                                            )}
                                                        </td>
                                                    </tr>
                                                )
                                            })}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        ) : null}

                        {/* Fair Market Price by Treatment - Horizontal Text Row */}
                        {pricingData?.by_treatment && pricingData.by_treatment.length > 0 && (
                            <div className="border border-border rounded bg-card px-4 py-3 relative">
                                {/* Login gate overlay */}
                                {!isLoggedIn && <LoginUpsellButton title="Sign in to view" />}
                                <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
                                    <div className="flex items-center gap-2">
                                        <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
                                        <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                                            Fair Market Price by {card.product_type === 'Single' ? 'Treatment' : 'Variant'}
                                        </span>
                                    </div>
                                    <div className="h-4 w-px bg-border hidden sm:block"></div>
                                    {pricingData.by_treatment.map((item, idx) => (
                                        <div key={idx} className="flex items-center gap-2">
                                            <span
                                                className="px-1.5 py-0.5 rounded text-[9px] uppercase font-bold"
                                                style={{
                                                    backgroundColor: `${getTreatmentColor(item.treatment)}20`,
                                                    color: getTreatmentColor(item.treatment)
                                                }}
                                            >
                                                {simplifyTreatment(item.treatment)}
                                            </span>
                                            <span className="font-mono font-bold text-blue-400">
                                                ${item.fmp?.toFixed(2) || '---'}
                                            </span>
                                            <span className="text-[10px] text-muted-foreground font-mono">
                                                ({item.sales_count})
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Sales Table (Full Width) */}
                        <div className="border border-border rounded bg-card overflow-hidden">
                            <div className="px-6 py-4 border-b border-border flex justify-between items-center bg-muted/20">
                                <div className="flex items-center gap-4">
                                    <h3 className="text-xs font-bold uppercase tracking-widest flex items-center gap-2">
                                        Sales & Listings
                                        <span className="bg-primary/20 text-primary px-1.5 py-0.5 rounded text-[10px]">{filteredData.length || 0}</span>
                                    </h3>

                                    {/* Filters */}
                                    <div className="flex items-center gap-2">
                                        <Filter className="w-3 h-3 text-muted-foreground" />
                                        <select
                                            className="bg-background border border-border rounded text-[10px] uppercase px-2 py-1 focus:outline-none focus:border-primary"
                                            value={treatmentFilter}
                                            onChange={(e) => setTreatmentFilter(e.target.value)}
                                        >
                                            <option value="all">{isSealed && uniqueSubtypes.length > 0 ? "All Subtypes" : "All Treatments"}</option>
                                            {uniqueTreatments.map(t => (
                                                <option key={t} value={t}>{t}</option>
                                            ))}
                                            {isSealed && uniqueSubtypes.length > 0 && uniqueSubtypes.map(s => (
                                                <option key={`subtype-${s}`} value={`subtype:${s}`}>{s}</option>
                                            ))}
                                        </select>
                                    </div>
                                </div>
                            </div>

                            <div className="overflow-x-auto">
                                <table className="w-full text-sm text-left">
                                    <thead className="text-xs uppercase bg-muted/30 text-muted-foreground sticky top-0">
                                        {table.getHeaderGroups().map(headerGroup => (
                                            <tr key={headerGroup.id}>
                                                {headerGroup.headers.map(header => (
                                                    <th key={header.id} className="px-4 py-3 font-medium border-b border-border whitespace-nowrap">
                                                        {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                                                    </th>
                                                ))}
                                            </tr>
                                        ))}
                                    </thead>
                                    <tbody className="divide-y divide-border/50">
                                        {isLoadingHistory ? (
                                            <tr><td colSpan={5} className="p-12 text-center text-muted-foreground animate-pulse">Fetching ledger data...</td></tr>
                                        ) : table.getRowModel().rows?.length ? (
                                            table.getRowModel().rows.map(row => (
                                                <tr
                                                    key={row.id}
                                                    className="hover:bg-muted/30 transition-colors cursor-pointer group"
                                                    onClick={() => setSelectedListing(row.original)}
                                                >
                                                    {row.getVisibleCells().map(cell => (
                                                        <td key={cell.id} className="px-4 py-3">
                                                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                                        </td>
                                                    ))}
                                                </tr>
                                            ))
                                        ) : (
                                            <tr>
                                                <td colSpan={5} className="p-12 text-center text-muted-foreground text-xs uppercase border-dashed">
                                                    No verified sales recorded in this period.
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>

                            {/* Pagination Controls */}
                            {table.getPageCount() > 1 && (
                                <div className="flex items-center justify-between px-4 py-3 border-t border-border bg-muted/10">
                                    <div className="flex-1 flex justify-between sm:hidden">
                                        <button
                                            onClick={() => table.previousPage()}
                                            disabled={!table.getCanPreviousPage()}
                                            className="relative inline-flex items-center px-4 py-2 border border-border text-sm font-medium rounded-md text-muted-foreground bg-card hover:bg-muted/50 disabled:opacity-50"
                                        >
                                            Previous
                                        </button>
                                        <button
                                            onClick={() => table.nextPage()}
                                            disabled={!table.getCanNextPage()}
                                            className="ml-3 relative inline-flex items-center px-4 py-2 border border-border text-sm font-medium rounded-md text-muted-foreground bg-card hover:bg-muted/50 disabled:opacity-50"
                                        >
                                            Next
                                        </button>
                                    </div>
                                    <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
                                        <div>
                                            <p className="text-xs text-muted-foreground">
                                                Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
                                            </p>
                                        </div>
                                        <div className="flex gap-1">
                                            <button
                                                onClick={() => table.previousPage()}
                                                disabled={!table.getCanPreviousPage()}
                                                className="px-2 py-1 rounded border border-border bg-card text-xs font-medium text-muted-foreground hover:bg-muted/50 disabled:opacity-50"
                                            >
                                                <ChevronLeft className="h-4 w-4" />
                                            </button>
                                            <button
                                                onClick={() => table.nextPage()}
                                                disabled={!table.getCanNextPage()}
                                                className="px-2 py-1 rounded border border-border bg-card text-xs font-medium text-muted-foreground hover:bg-muted/50 disabled:opacity-50"
                                            >
                                                <ChevronRight className="h-4 w-4" />
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>

                    </div>
                </div>
            </div>

            {/* Promotional Banner */}
            <div className="border-t border-border bg-black py-8 mt-auto">
                <div className="max-w-7xl mx-auto px-6">
                    <div className="flex flex-col md:flex-row items-center justify-between gap-4 text-center md:text-left">
                        <div className="flex-1">
                            <h3 className="text-xl font-bold uppercase tracking-tight mb-2 text-white">
                                Track Your Collection in Real-Time
                            </h3>
                            <p className="text-sm text-zinc-400">
                                Get instant market data, price alerts, and portfolio analytics for Wonders of the First TCG at{' '}
                                <span className="text-brand-300 font-bold">WondersTracker.com</span>
                            </p>
                        </div>
                        <div className="flex gap-3">
                            <Link
                                to="/"
                                className="px-6 py-3 bg-brand-300 hover:bg-brand-400 text-black font-bold uppercase text-sm rounded transition-colors"
                            >
                                View Market
                            </Link>
                            <Link
                                to="/portfolio"
                                className="px-6 py-3 border border-brand-300 text-brand-300 hover:bg-brand-300/10 font-bold uppercase text-sm rounded transition-colors"
                            >
                                Track Portfolio
                            </Link>
                        </div>
                    </div>
                </div>
            </div>

            {/* SEO Footer */}
            <footer className="border-t border-border py-8 bg-muted/10">
                <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row justify-between items-center gap-4">
                    <div className="text-xs text-muted-foreground uppercase tracking-wider">
                        © 2025 Wonder Scraper Inc. Market Data for TCG "Wonders of the First".
                    </div>
                    <div className="flex gap-6 text-xs text-muted-foreground uppercase font-bold">
                        <Link to="/" className="hover:text-primary">Market</Link>
                        <a href="#" className="hover:text-primary">Terms</a>
                        <a href="#" className="hover:text-primary">Privacy</a>
                        <a href="#" className="hover:text-primary">API</a>
                    </div>
                </div>
            </footer>

            {/* Listing Details Drawer */}
            <div 
                className={clsx(
                    "fixed inset-y-0 right-0 w-full md:w-96 bg-card border-l border-border shadow-2xl transform transition-transform duration-300 ease-in-out z-50 flex flex-col",
                    selectedListing ? "translate-x-0" : "translate-x-full"
                )}
            >
                {selectedListing && (
                    <>
                        <div className="p-6 border-b border-border flex justify-between items-start">
                            <div>
                                <h2 className="text-lg font-bold uppercase tracking-tight">Listing Details</h2>
                                <div className="text-xs text-muted-foreground uppercase">ID: {selectedListing.id}</div>
                            </div>
                            <button onClick={() => setSelectedListing(null)} className="text-muted-foreground hover:text-foreground transition-colors">
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                        
                        <div className="flex-1 overflow-y-auto p-6 space-y-6">
                            {/* Product Image (if available) */}
                            {selectedListing.image_url && (
                                <div className="rounded-lg overflow-hidden border border-border">
                                    <img
                                        src={selectedListing.image_url}
                                        alt={selectedListing.title}
                                        className="w-full h-48 object-cover"
                                        loading="lazy"
                                        width={400}
                                        height={192}
                                        onError={(e) => (e.currentTarget.style.display = 'none')}
                                    />
                                </div>
                            )}

                            <div>
                                <div className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest mb-2">Listing Title</div>
                                <div className="text-sm font-medium leading-relaxed border border-border p-3 rounded bg-muted/20">
                                    {selectedListing.title}
                                </div>
                                {/* PSA Grading Badge */}
                                {isPSAGraded(selectedListing.title).graded && (
                                    <div className="mt-3 inline-flex items-center gap-2 px-3 py-2 rounded border border-amber-600 bg-amber-900/30">
                                        <div className="w-3 h-3 rounded-full bg-amber-500" />
                                        <span className="text-amber-400 text-xs font-bold uppercase">
                                            Graded: PSA {isPSAGraded(selectedListing.title).grade}
                                        </span>
                                    </div>
                                )}
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <div className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest mb-1">Price</div>
                                    <div className="text-2xl font-mono font-bold text-brand-300">
                                        ${selectedListing.price.toFixed(2)}
                                    </div>
                                </div>
                                <div>
                                    <div className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest mb-1">
                                        {selectedListing.listing_type === 'active' ? 'Listed' : 'Sold'}
                                    </div>
                                    <div className="text-sm font-mono">
                                        {selectedListing.sold_date
                                            ? new Date(selectedListing.sold_date).toLocaleDateString()
                                            : selectedListing.listed_at
                                                ? new Date(selectedListing.listed_at).toLocaleDateString()
                                                : selectedListing.scraped_at
                                                    ? new Date(selectedListing.scraped_at).toLocaleDateString()
                                                    : 'N/A'}
                                    </div>
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <div className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest mb-1">Type</div>
                                    <span className={clsx("px-2 py-1 rounded text-[10px] uppercase font-bold border inline-block", 
                                        selectedListing.listing_type === 'sold' ? 'border-brand-700 bg-brand-800/20 text-brand-400' : 'border-blue-800 bg-blue-900/20 text-blue-500')}>
                                        {selectedListing.listing_type || 'Sold'}
                                    </span>
                                </div>
                                <div>
                                    <div className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest mb-1">Treatment</div>
                                    <TreatmentBadge treatment={selectedListing.treatment || 'Classic Paper'} size='xs' />
                                </div>
                            </div>

                            <div>
                                 <div className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest mb-1">Bid Count</div>
                                 <div className="text-sm font-mono font-bold">
                                    {selectedListing.bid_count ?? '0'}
                                 </div>
                            </div>

                            {/* Traits/Treatment Section */}
                            {(selectedListing.traits || selectedListing.treatment) && (
                                <div className="pt-6 border-t border-border">
                                    <h3 className="text-xs font-bold uppercase tracking-widest mb-4 flex items-center gap-2">
                                        <div className={clsx("w-1 h-4 rounded-full", selectedListing.traits ? "bg-cyan-500" : "bg-purple-500")}></div>
                                        {selectedListing.traits ? 'Traits' : 'Treatment'}
                                        {selectedListing.traits && selectedListing.traits.length > 3 && (
                                            <span className="text-[10px] text-muted-foreground font-normal ml-2">
                                                ({selectedListing.traits.length} total)
                                            </span>
                                        )}
                                    </h3>
                                    <div className="bg-muted/10 rounded p-4 border border-border space-y-3">
                                        {/* Show traits if available (max 3, then +N more) */}
                                        {selectedListing.traits && selectedListing.traits.length > 0 ? (
                                            <div className="space-y-2">
                                                {selectedListing.traits.slice(0, 3).map((trait, idx) => (
                                                    <div key={idx} className="flex justify-between items-center">
                                                        <span className="text-[10px] text-muted-foreground uppercase">
                                                            {trait.trait_type}
                                                        </span>
                                                        <span
                                                            className="px-2 py-0.5 rounded text-[10px] font-bold border"
                                                            style={{
                                                                borderColor: trait.trait_type.toLowerCase() === 'hierarchy' ? '#06b6d450' :
                                                                            trait.trait_type.toLowerCase() === 'legendary' && trait.value.toLowerCase() === 'yes' ? '#f59e0b50' :
                                                                            trait.trait_type.toLowerCase() === 'artist' ? '#a855f750' :
                                                                            '#71717a50',
                                                                backgroundColor: trait.trait_type.toLowerCase() === 'hierarchy' ? '#06b6d415' :
                                                                                trait.trait_type.toLowerCase() === 'legendary' && trait.value.toLowerCase() === 'yes' ? '#f59e0b15' :
                                                                                trait.trait_type.toLowerCase() === 'artist' ? '#a855f715' :
                                                                                '#71717a15',
                                                                color: trait.trait_type.toLowerCase() === 'hierarchy' ? '#06b6d4' :
                                                                       trait.trait_type.toLowerCase() === 'legendary' && trait.value.toLowerCase() === 'yes' ? '#f59e0b' :
                                                                       trait.trait_type.toLowerCase() === 'artist' ? '#a855f7' :
                                                                       '#a1a1aa'
                                                            }}
                                                        >
                                                            {trait.value}
                                                        </span>
                                                    </div>
                                                ))}
                                                {selectedListing.traits.length > 3 && (
                                                    <div className="text-[10px] text-muted-foreground text-center pt-1">
                                                        + {selectedListing.traits.length - 3} more attributes
                                                    </div>
                                                )}
                                            </div>
                                        ) : (
                                            /* Fallback to treatment if no traits */
                                            (<div className="flex flex-wrap gap-2">
                                                <span
                                                    className="px-2 py-1 rounded text-[10px] uppercase font-bold border"
                                                    style={{
                                                        borderColor: `${getTreatmentColor(selectedListing.treatment || ``)}50`,
                                                        backgroundColor: `${getTreatmentColor(selectedListing.treatment || ``)}15`,
                                                        color: getTreatmentColor(selectedListing.treatment || '')
                                                    }}
                                                >
                                                    {selectedListing.treatment}
                                                </span>
                                            </div>)
                                        )}
                                        {/* Show PSA grade as trait if graded */}
                                        {isPSAGraded(selectedListing.title).graded && (
                                            <div className="flex justify-between items-center pt-2 border-t border-border/50">
                                                <span className="text-[10px] text-muted-foreground uppercase">Grading</span>
                                                <span className="px-2 py-0.5 rounded text-[10px] font-bold border border-amber-700 bg-amber-900/30 text-amber-400">
                                                    PSA {isPSAGraded(selectedListing.title).grade}
                                                </span>
                                            </div>
                                        )}
                                        {/* Note about viewing on OpenSea if no traits loaded yet */}
                                        {!selectedListing.traits && selectedListing.url?.includes('opensea') && (
                                            <p className="text-[10px] text-muted-foreground pt-2 border-t border-border/50">
                                                View full traits on the OpenSea listing.
                                            </p>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* Card Metadata Context */}
                            <div className="pt-6 border-t border-border">
                                <h3 className="text-xs font-bold uppercase tracking-widest mb-4 flex items-center gap-2">
                                    <Wallet className="w-3 h-3" /> Linked Card Info
                                </h3>
                                <div className="bg-muted/10 rounded p-4 border border-border space-y-3">
                                    <div className="flex justify-between">
                                        <span className="text-xs text-muted-foreground uppercase">Name</span>
                                        <span className="text-xs font-bold">{card?.name}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-xs text-muted-foreground uppercase">Set</span>
                                        <span className="text-xs font-bold">
                                            {card?.set_name}
                                            {selectedListing.url?.includes('opensea') && (
                                                <span className="text-[10px] text-cyan-400 ml-1">* OpenSea</span>
                                            )}
                                            {selectedListing.url?.includes('ebay') && (
                                                <span className="text-[10px] text-blue-400 ml-1">* eBay</span>
                                            )}
                                            {selectedListing.url?.includes('blokpax') && (
                                                <span className="text-[10px] text-purple-400 ml-1">* Blokpax</span>
                                            )}
                                        </span>
                                    </div>
                                    {/* Show Collection Address for NFTs, Rarity for others */}
                                    {selectedListing.url?.includes('opensea') ? (
                                        <div className="flex justify-between">
                                            <span className="text-xs text-muted-foreground uppercase">Collection</span>
                                            <span className="text-xs font-bold font-mono">
                                                {(() => {
                                                    // Extract contract address from OpenSea URL
                                                    const match = selectedListing.url?.match(/opensea\.io\/(?:item|assets)\/[^/]+\/([^/]+)/)
                                                    if (match && match[1]) {
                                                        const addr = match[1]
                                                        // Truncate address: 0x1234...5678
                                                        if (addr.startsWith('0x') && addr.length > 12) {
                                                            return `${addr.slice(0, 6)}...${addr.slice(-4)}`
                                                        }
                                                        return addr.length > 15 ? `${addr.slice(0, 12)}...` : addr
                                                    }
                                                    return 'N/A'
                                                })()}
                                            </span>
                                        </div>
                                    ) : (
                                        <div className="flex justify-between">
                                            <span className="text-xs text-muted-foreground uppercase">Rarity</span>
                                            <span className="text-xs font-bold">{card?.rarity_name || card?.rarity_id}</span>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Seller Info */}
                            {(selectedListing.seller_name || selectedListing.condition || selectedListing.shipping_cost != null) && (
                            <div className="pt-6 border-t border-border">
                                <h3 className="text-xs font-bold uppercase tracking-widest mb-4 flex items-center gap-2">
                                    <div className="w-1 h-4 bg-purple-500 rounded-full"></div>
                                    Seller Info
                                </h3>
                                <div className="bg-muted/10 rounded p-4 border border-border space-y-3 text-xs">
                                    {selectedListing.seller_name && (
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground">Seller</span>
                                            <span className="font-bold">{selectedListing.seller_name}</span>
                                        </div>
                                    )}
                                    {selectedListing.seller_feedback_score != null && (
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground">Feedback Score</span>
                                            <span className="font-bold">{selectedListing.seller_feedback_score.toLocaleString()}</span>
                                        </div>
                                    )}
                                    {selectedListing.seller_feedback_percent != null && (
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground">Positive Feedback</span>
                                            <span className={clsx("font-bold", selectedListing.seller_feedback_percent >= 99 ? "text-brand-300" : selectedListing.seller_feedback_percent >= 95 ? "text-yellow-500" : "text-red-500")}>{selectedListing.seller_feedback_percent}%</span>
                                        </div>
                                    )}
                                    {selectedListing.condition && (
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground">Condition</span>
                                            <span className="font-bold">{selectedListing.condition}</span>
                                        </div>
                                    )}
                                    {selectedListing.shipping_cost != null && (
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground">Shipping</span>
                                            <span className={clsx("font-bold", selectedListing.shipping_cost === 0 ? "text-brand-300" : "")}>{selectedListing.shipping_cost === 0 ? "Free" : "$${selectedListing.shipping_cost.toFixed(2)}"}</span>
                                        </div>
                                    )}
                                </div>
                            </div>
                            )}

                            {/* Report Listing Button */}
                            <div className="pt-6 border-t border-border">
                                <button
                                    onClick={() => {
                                        setReportReason('')
                                        setReportNotes('')
                                        setReportSubmitted(false)
                                        setShowReportModal(true)
                                    }}
                                    className="flex items-center justify-center gap-2 w-full border border-amber-700/50 hover:border-amber-600 bg-amber-900/10 hover:bg-amber-900/20 text-amber-500 text-xs uppercase font-bold py-3 rounded transition-colors"
                                >
                                    <Flag className="w-3 h-3" /> Report Listing
                                </button>
                                <p className="text-[10px] text-center text-muted-foreground mt-2">
                                    Flag incorrect, fake, or duplicate listings
                                </p>
                            </div>

                            {/* Listing Info */}
                            <div className="pt-6 border-t border-border">
                                <h3 className="text-xs font-bold uppercase tracking-widest mb-4 flex items-center gap-2">
                                    <div className="w-1 h-4 bg-blue-500 rounded-full"></div>
                                    Listing Info
                                </h3>
                                <div className="bg-muted/10 rounded p-4 border border-border space-y-3 text-xs">
                                    {selectedListing.description && (
                                        <p className="text-muted-foreground italic">"{selectedListing.description}"</p>
                                    )}
                                    {/* Platform Info */}
                                    <div className={selectedListing.description ? "pt-2 border-t border-border/50 mt-2" : ""}>
                                        <div className="flex justify-between items-center">
                                            <span className="text-muted-foreground">Platform</span>
                                            <span className={clsx("font-bold",
                                                selectedListing.url?.includes('opensea') ? 'text-cyan-400' :
                                                selectedListing.url?.includes('ebay') ? 'text-blue-400' :
                                                selectedListing.url?.includes('blokpax') ? 'text-purple-400' :
                                                "text-muted-foreground"
                                            )}>
                                                {selectedListing.url?.includes('opensea') ? 'OpenSea' :
                                                 selectedListing.url?.includes('ebay') ? 'eBay' :
                                                 selectedListing.url?.includes('blokpax') ? 'Blokpax' :
                                                 'External'}
                                            </span>
                                        </div>
                                    </div>
                                    {/* Scraped timestamp */}
                                    <div className="flex justify-between items-center">
                                        <span className="text-muted-foreground">Data Updated</span>
                                        <span className="font-mono text-muted-foreground">
                                            {selectedListing.scraped_at
                                                ? new Date(selectedListing.scraped_at).toLocaleDateString()
                                                : 'N/A'}
                                        </span>
                                    </div>
                                    {/* External ID if available */}
                                    {selectedListing.url && (
                                        <div className="flex justify-between items-center">
                                            <span className="text-muted-foreground">Listing ID</span>
                                            <span className="font-mono text-[10px] text-muted-foreground truncate max-w-[150px]">
                                                {selectedListing.id}
                                            </span>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* External Link */}
                            <div className="pt-4">
                                <a
                                    href={selectedListing.url || `https://www.ebay.com/sch/i.html?_nkw=${encodeURIComponent(selectedListing.title)}&LH_Complete=1`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-center justify-center gap-2 w-full border border-border hover:bg-muted/50 text-xs uppercase font-bold py-3 rounded transition-colors"
                                    onClick={() => {
                                        const platform = selectedListing.url?.includes('ebay') ? 'ebay' : 'external'
                                        analytics.trackExternalLinkClick(platform, cardId, selectedListing.title)
                                    }}
                                >
                                    <ExternalLink className="w-3 h-3" /> View Original Listing
                                </a>
                                <div className="text-[10px] text-center text-muted-foreground mt-2">
                                    *Redirects to the original marketplace listing.
                                </div>
                            </div>
                        </div>
                    </>
                )}
            </div>
            
            {/* Backdrop */}
            {selectedListing && (
                <div
                    className="fixed inset-0 bg-black/50 z-40 backdrop-blur-sm"
                    onClick={() => setSelectedListing(null)}
                />
            )}

            {/* Add to Portfolio Modal */}
            {card && (
                <AddToPortfolioModal
                    card={{
                        id: card.id,
                        name: card.name,
                        set_name: card.set_name,
                        floor_price: card.floor_price,
                        latest_price: card.latest_price,
                        product_type: card.product_type
                    }}
                    isOpen={showAddModal}
                    onClose={() => setShowAddModal(false)}
                />
            )}

            {/* Report Listing Modal */}
            {showReportModal && selectedListing && (
                <>
                    <div className="fixed inset-0 bg-black/70 z-[60] backdrop-blur-sm" onClick={() => setShowReportModal(false)} />
                    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
                        <div className="bg-card border border-border rounded-lg shadow-2xl w-full max-w-md">
                            <div className="p-6 border-b border-border flex justify-between items-center">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-full bg-amber-900/30 border border-amber-700 flex items-center justify-center">
                                        <AlertTriangle className="w-5 h-5 text-amber-500" />
                                    </div>
                                    <div>
                                        <h2 className="text-lg font-bold uppercase tracking-tight">Report Listing</h2>
                                        <p className="text-xs text-muted-foreground">ID: {selectedListing.id}</p>
                                    </div>
                                </div>
                                <button
                                    onClick={() => setShowReportModal(false)}
                                    className="text-muted-foreground hover:text-foreground transition-colors"
                                >
                                    <X className="w-5 h-5" />
                                </button>
                            </div>

                            <div className="p-6 space-y-6">
                                {reportSubmitted ? (
                                    <div className="text-center py-8">
                                        <div className="w-16 h-16 rounded-full bg-brand-800/30 border border-brand-600 flex items-center justify-center mx-auto mb-4">
                                            <svg className="w-8 h-8 text-brand-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                            </svg>
                                        </div>
                                        <h3 className="text-lg font-bold mb-2">Report Submitted</h3>
                                        <p className="text-sm text-muted-foreground mb-6">
                                            Thank you for helping us maintain data quality. We'll review this listing.
                                        </p>
                                        <button
                                            onClick={() => setShowReportModal(false)}
                                            className="px-6 py-2 bg-primary text-primary-foreground rounded text-sm font-bold uppercase hover:bg-primary/90 transition-colors"
                                        >
                                            Close
                                        </button>
                                    </div>
                                ) : (
                                    <>
                                        {/* Listing Preview */}
                                        <div className="bg-muted/20 rounded p-3 border border-border">
                                            <div className="text-[10px] uppercase text-muted-foreground mb-1">Reporting:</div>
                                            <div className="text-sm font-medium truncate">{selectedListing.title}</div>
                                            <div className="text-xs text-brand-300 font-mono mt-1">${selectedListing.price.toFixed(2)}</div>
                                        </div>

                                        {/* Reason Selection */}
                                        <div>
                                            <label className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest mb-3 block">
                                                Reason for Report *
                                            </label>
                                            <div className="space-y-2">
                                                {[
                                                    { value: 'wrong_price', label: 'Incorrect Price', desc: "The price doesn't match the actual sale" },
                                                    { value: 'fake_listing', label: 'Fake/Scam Listing', desc: 'This listing appears to be fraudulent' },
                                                    { value: 'duplicate', label: 'Duplicate Entry', desc: 'This listing is already recorded' },
                                                    { value: 'wrong_card', label: 'Wrong Card', desc: 'This is a different card or product' },
                                                    { value: 'other', label: 'Other', desc: 'Another issue not listed above' }
                                                ].map((option) => (
                                                    <label
                                                        key={option.value}
                                                        className={clsx(
                                                            "flex items-start gap-3 p-3 rounded border cursor-pointer transition-colors",
                                                            reportReason === option.value
                                                                ? "border-primary bg-primary/10"
                                                                : "border-border hover:border-muted-foreground/50"
                                                        )}
                                                    >
                                                        <input
                                                            type="radio"
                                                            name="reportReason"
                                                            value={option.value}
                                                            checked={reportReason === option.value}
                                                            onChange={(e) => setReportReason(e.target.value)}
                                                            className="mt-1"
                                                        />
                                                        <div>
                                                            <div className="text-sm font-bold">{option.label}</div>
                                                            <div className="text-xs text-muted-foreground">{option.desc}</div>
                                                        </div>
                                                    </label>
                                                ))}
                                            </div>
                                        </div>

                                        {/* Additional Notes */}
                                        <div>
                                            <label className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest mb-2 block">
                                                Additional Details (Optional)
                                            </label>
                                            <textarea
                                                value={reportNotes}
                                                onChange={(e) => setReportNotes(e.target.value)}
                                                placeholder="Provide any additional context..."
                                                className="w-full bg-background border border-border rounded p-3 text-sm resize-none h-20 focus:outline-none focus:border-primary"
                                            />
                                        </div>

                                        {/* Submit Button */}
                                        <div className="flex gap-3">
                                            <button
                                                onClick={() => setShowReportModal(false)}
                                                className="flex-1 px-4 py-3 border border-border rounded text-sm font-bold uppercase hover:bg-muted/50 transition-colors"
                                            >
                                                Cancel
                                            </button>
                                            <button
                                                onClick={async () => {
                                                    if (!reportReason) return
                                                    setReportSubmitting(true)
                                                    try {
                                                        await api.post('market/reports', {
                                                            json: {
                                                                listing_id: selectedListing.id,
                                                                card_id: parseInt(cardId),
                                                                reason: reportReason,
                                                                notes: reportNotes || null,
                                                                listing_title: selectedListing.title,
                                                                listing_price: selectedListing.price,
                                                                listing_url: selectedListing.url
                                                            }
                                                        }).json()
                                                        setReportSubmitted(true)
                                                    } catch (err) {
                                                        console.error('Failed to submit report:', err)
                                                        alert('Failed to submit report. Please try again.')
                                                    } finally {
                                                        setReportSubmitting(false)
                                                    }
                                                }}
                                                disabled={!reportReason || reportSubmitting}
                                                className="flex-1 px-4 py-3 bg-brand-400 hover:bg-brand-300 disabled:bg-brand-400/50 disabled:cursor-not-allowed text-gray-900 rounded text-sm font-bold uppercase transition-colors flex items-center justify-center gap-2"
                                            >
                                                {reportSubmitting ? (
                                                    <>
                                                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                                        Submitting...
                                                    </>
                                                ) : (
                                                    <>
                                                        <Flag className="w-4 h-4" />
                                                        Submit Report
                                                    </>
                                                )}
                                            </button>
                                        </div>
                                    </>
                                )}
                            </div>
                        </div>
                    </div>
                </>
            )}
          </div>
      </>
  )
}
