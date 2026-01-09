import { createFileRoute, useParams, useNavigate, Link, useSearch } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../utils/auth'
import { analytics } from '~/services/analytics'
import { ArrowLeft, TrendingUp, Wallet, Filter, ChevronLeft, ChevronRight, X, ExternalLink, Calendar, Flag, AlertTriangle } from 'lucide-react'
import { ColumnDef, flexRender, getCoreRowModel, useReactTable, getPaginationRowModel, getFilteredRowModel } from '@tanstack/react-table'
import { useMemo, useState, useEffect, lazy, Suspense, useRef } from 'react'
import { Tooltip } from '../components/ui/tooltip'

// Lazy load chart component (378KB recharts bundle) - only loads when needed
const PriceHistoryChart = lazy(() => import('../components/charts/PriceHistoryChart'))
import clsx from 'clsx'
import { cn } from '@/lib/utils'
import { AddToPortfolioModal } from '../components/AddToPortfolioModal'
import { TreatmentBadge } from '../components/TreatmentBadge'
import { ConfidenceIndicator } from '../components/ConfidenceIndicator'
import { SellerBadge } from '../components/SellerBadge'
// CardActionSplitButton removed - actions now in PriceBox
import { ProductSubtypeBadge, getSubtypeColor } from '../components/ProductSubtypeBadge'
import { LoginUpsellButton } from '../components/LoginUpsellOverlay'
import { MetaVote } from '../components/MetaVote'
import { useCurrentUser } from '../context/UserContext'
import { CardDetailLayout, Section, CardHero, PriceBox, PriceAlertModal, TreatmentPricingTable, SimilarCards, StickyPriceHeader, useScrollPast, CardDetailHeader, MobileStickyActions } from '../components/card-detail'
import type { SimilarCard } from '../components/card-detail'
import { CardDetailPageSkeleton, SkeletonChart, SkeletonTableRows } from '../components/ui/skeleton'

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
    grading?: string | null    // PSA 10, BGS 9.5, etc.
    platform?: string          // ebay, opensea, blokpax
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

// Server-side loader for SEO meta tags and data prefetching
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

// Search params type for URL-backed state
type CardSearchParams = {
  treatment?: string
  range?: TimeRange
  sort?: 'price' | 'date' | 'seller'
  dir?: 'asc' | 'desc'
  page?: number
}

export const Route = createFileRoute('/cards/$cardId')({
  component: CardDetail,
  validateSearch: (search: Record<string, unknown>): CardSearchParams => ({
    treatment: (search.treatment as string) || undefined,
    range: (['1m', '3m', '6m', '1y', 'all'].includes(search.range as string) ? search.range : undefined) as TimeRange | undefined,
    sort: (['price', 'date', 'seller'].includes(search.sort as string) ? search.sort : undefined) as CardSearchParams['sort'],
    dir: (['asc', 'desc'].includes(search.dir as string) ? search.dir : undefined) as CardSearchParams['dir'],
    page: typeof search.page === 'number' ? search.page : (typeof search.page === 'string' ? parseInt(search.page, 10) || undefined : undefined),
  }),
  // Loader handles SEO data only - component useQuery handles all data fetching
  // This avoids cache misses from fetch() vs api.get() inconsistencies
  loader: async ({ params }) => {
    const cardId = params.cardId
    const card = await fetchCardForSEO(cardId)
    return { card }
  },
})

// Re-export component for potential lazy loading
export { CardDetail }

type TimeRange = '1m' | '3m' | '6m' | '1y' | 'all'

function CardDetail() {
  const { cardId } = useParams({ from: Route.id })
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // URL-backed state for shareable links
  const searchParams = useSearch({ from: Route.id })
  const treatmentFilter = searchParams.treatment || 'all'
  const timeRange: TimeRange = searchParams.range || '3m'

  // Helper to update URL search params
  const updateSearchParams = (updates: Partial<CardSearchParams>) => {
    navigate({
      to: '/cards/$cardId',
      params: { cardId },
      search: (prev) => {
        const next = { ...prev, ...updates }
        // Remove undefined/null values to keep URL clean
        Object.keys(next).forEach((key) => {
          if (next[key as keyof CardSearchParams] === undefined || next[key as keyof CardSearchParams] === null) {
            delete next[key as keyof CardSearchParams]
          }
        })
        return next
      },
      replace: true, // Don't add to history stack
    })
  }

  // Wrapper functions for URL state updates
  const setTreatmentFilter = (treatment: string) => {
    updateSearchParams({ treatment: treatment === 'all' ? undefined : treatment, page: undefined })
  }

  const setTimeRange = (range: TimeRange) => {
    updateSearchParams({ range: range === '3m' ? undefined : range })
  }

  // Local-only state (not URL-backed)
  const [selectedListing, setSelectedListing] = useState<MarketPrice | null>(null)
  const [showAddModal, setShowAddModal] = useState(false)
  const [showPriceAlertModal, setShowPriceAlertModal] = useState(false)
  const [showReportModal, setShowReportModal] = useState(false)
  const [reportReason, setReportReason] = useState<string>('')
  const [reportNotes, setReportNotes] = useState<string>('')
  const [reportSubmitting, setReportSubmitting] = useState(false)
  const [reportSubmitted, setReportSubmitted] = useState(false)
  const [showSoldListings, setShowSoldListings] = useState(false)
  const [mobileAddedFeedback, setMobileAddedFeedback] = useState(false)

  const { user: currentUser } = useCurrentUser()
  const isLoggedIn = !!currentUser

  // Ref for sticky header scroll detection
  const priceBoxRef = useRef<HTMLDivElement>(null)
  const isScrolledPastPriceBox = useScrollPast(priceBoxRef)

  // Reset local-only state when cardId changes (URL state resets via navigation)
  useEffect(() => {
    setSelectedListing(null)
    setShowReportModal(false)
    setReportReason('')
    setReportNotes('')
    setReportSubmitted(false)
  }, [cardId])

  // Track card listing view (with session-based milestone tracking)
  useEffect(() => {
    if (cardId) {
      analytics.trackCardViewWithSession(cardId)
    }
  }, [cardId])

  // Fetch Card Data - single endpoint, no /market fallback needed
  // The /cards/{id} endpoint already includes all pricing data (floor, vwap, lowest_ask, etc.)
  const { data: card, isLoading: isLoadingCard } = useQuery({
    queryKey: ['card', cardId],
    queryFn: async () => {
      const data = await api.get(`cards/${cardId}`).json<CardDetail>()
      return {
        ...data,
        market_cap: (data.floor_price || data.latest_price || 0) * (data.volume_30d || 0)
      }
    },
    staleTime: 2 * 60 * 1000, // 2 minutes - card data updates infrequently
    enabled: !!cardId,
  })

  // Fetch Sales History (sold + active listings) - single combined endpoint
  // Uses /listings endpoint for better performance (one request instead of two)
  type ListingsResponse = {
    card_id: number
    sold: { items: MarketPrice[], total: number, hasMore: boolean }
    active: { items: MarketPrice[], total: number }
  }
  const { data: historyData, isLoading: isLoadingHistory, error: historyError } = useQuery({
      queryKey: ['card-listings', cardId],
      queryFn: async () => {
          const response = await api.get(`cards/${cardId}/listings?sold_limit=100&active_limit=100`).json<ListingsResponse>()
          // Combine: active listings first, then sold by date
          return {
            items: [...response.active.items, ...response.sold.items],
            total: response.sold.total,
            hasMore: response.sold.hasMore,
            activeCount: response.active.items.length
          }
      },
      staleTime: 2 * 60 * 1000, // 2 minutes
      enabled: !!cardId, // Only fetch when cardId is available
      retry: 2, // Retry twice on failure
  })

  // Backwards compat: extract items array for existing code
  const history = historyData?.items ?? []

  // Debug: Log query state and data
  useEffect(() => {
    if (historyError) {
      console.error('[CardDetail] Listings query error:', historyError)
    }
    console.log('[CardDetail] Query state:', {
      cardId,
      isLoadingHistory,
      historyLength: history.length,
      activeCount: historyData?.activeCount,
      hasError: !!historyError
    })
  }, [cardId, historyError, isLoadingHistory, history.length, historyData?.activeCount])

  // Fetch Snapshot History (for OpenSea/NFT items that don't have individual sales)
  // Runs in parallel with other queries - no longer waits for listings data
  const { data: snapshots } = useQuery({
      queryKey: ['card-snapshots', cardId],
      queryFn: async () => {
          return await api.get(`cards/${cardId}/snapshots?days=365&limit=500`).json<MarketSnapshot[]>()
      },
      staleTime: 5 * 60 * 1000, // 5 minutes - snapshots change slowly
      enabled: !!cardId,
      retry: 1,
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
      // Fetch fresh data for each card (queryKey includes cardId)
  })

  // Fetch Order Book floor data (OSS-compatible alternative to FMP pricing)
  type OrderBookTreatment = {
      treatment: string
      floor_estimate: number | null
      confidence: number
      total_listings: number
      source: string | null
  }
  type OrderBookData = {
      card_id: number
      card_name: string
      overall_floor: number | null
      overall_confidence: number
      by_treatment: OrderBookTreatment[]
  }
  const { data: orderBookData } = useQuery({
      queryKey: ['card-order-book', cardId],
      queryFn: async () => {
          try {
            return await api.get(`cards/${cardId}/order-book/by-treatment`).json<OrderBookData>()
          } catch (e) {
              return null
          }
      },
      staleTime: 5 * 60 * 1000, // 5 minutes
      // Fetch fresh data for each card (queryKey includes cardId)
  })

  // Fetch FMP/Floor price history for chart trend line
  type FMPHistoryPoint = {
      date: string
      floor_price: number | null
      fmp: number | null
      vwap: number | null
      sales_count: number
      treatment: string | null
  }
  const { data: fmpHistory } = useQuery({
      queryKey: ['card-fmp-history', cardId],
      queryFn: async () => {
          try {
            return await api.get(`cards/${cardId}/fmp-history?days=365`).json<FMPHistoryPoint[]>()
          } catch (e) {
              return []
          }
      },
      staleTime: 10 * 60 * 1000, // 10 minutes - historical data changes slowly
      // Fetch fresh data for each card (queryKey includes cardId)
  })

  // Fetch card variants (same card, different treatments)
  type VariantsResponse = {
    card_id: number
    card_name: string
    variants: SimilarCard[]
    count: number
  }
  const { data: variantsData, isLoading: isLoadingVariants } = useQuery({
    queryKey: ['card-variants', cardId],
    queryFn: async () => {
      try {
        return await api.get(`cards/${cardId}/variants?limit=12`).json<VariantsResponse>()
      } catch (e) {
        return null
      }
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  // Fetch similar cards (same rarity from same set)
  type SimilarResponse = {
    card_id: number
    card_name: string
    rarity: string
    set_name: string
    similar_cards: SimilarCard[]
    count: number
  }
  const { data: similarData, isLoading: isLoadingSimilar } = useQuery({
    queryKey: ['card-similar', cardId],
    queryFn: async () => {
      try {
        return await api.get(`cards/${cardId}/similar?limit=12`).json<SimilarResponse>()
      } catch (e) {
        return null
      }
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
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
              const rawTreatment = row.original.treatment
              const hasSubtype = !!row.original.product_subtype

              // If product_subtype exists (e.g., Dragon Box, First Form for NFTs),
              // don't show a card treatment - the subtype column handles categorization
              if (!rawTreatment && hasSubtype) {
                  return <span className="text-muted-foreground text-xs">—</span>
              }

              // If treatment is "NFT" or empty, try to extract from title
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
              // Use grading field if available, otherwise parse from title
              const gradingField = row.original.grading
              const parsedGrading = isPSAGraded(row.original.title)
              const hasGrade = gradingField || parsedGrading.graded
              const gradeDisplay = gradingField || (parsedGrading.graded ? `PSA ${parsedGrading.grade}` : null)
              const isNFT = row.original.platform === 'opensea'

              return (
                  <div className="flex items-center gap-2">
                      {hasGrade && gradeDisplay && (
                          <span className={cn(
                              "px-1.5 py-0.5 rounded text-[9px] uppercase font-bold border shrink-0",
                              isNFT
                                ? "border-cyan-700 bg-cyan-900/30 text-cyan-400"
                                : "border-amber-700 bg-amber-900/30 text-amber-400"
                          )}>
                              {gradeDisplay}
                          </span>
                      )}
                      {isNFT && !hasGrade && (
                          <span className="px-1.5 py-0.5 rounded text-[9px] uppercase font-bold border border-cyan-700 bg-cyan-900/30 text-cyan-400 shrink-0">
                              NFT
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
          accessorKey: 'platform',
          header: 'Source',
          cell: ({ row }) => {
              const platform = row.original.platform || 'ebay'
              const platformConfig: Record<string, { label: string; color: string }> = {
                  ebay: { label: 'eBay', color: 'border-red-800 bg-red-900/20 text-red-400' },
                  opensea: { label: 'OpenSea', color: 'border-cyan-700 bg-cyan-900/30 text-cyan-400' },
                  blokpax: { label: 'Blokpax', color: 'border-purple-700 bg-purple-900/30 text-purple-400' },
              }
              const config = platformConfig[platform] || platformConfig.ebay
              return (
                  <span className={cn("px-1.5 py-0.5 rounded text-[9px] uppercase font-bold border", config.color)}>
                      {config.label}
                  </span>
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
      },
      {
          accessorKey: 'seller_name',
          header: 'Seller',
          cell: ({ row }) => (
            <SellerBadge
              sellerName={row.original.seller_name}
              feedbackScore={row.original.seller_feedback_score}
              feedbackPercent={row.original.seller_feedback_percent}
              size="xs"
            />
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

  // Memoized listings for display
  const activeListings = useMemo(() =>
    filteredData.filter(d => d.listing_type === 'active'),
    [filteredData]
  )
  const soldListings = useMemo(() =>
    filteredData.filter(d => d.listing_type === 'sold'),
    [filteredData]
  )
  const displayListings = useMemo(() =>
    showSoldListings ? filteredData : activeListings,
    [showSoldListings, filteredData, activeListings]
  )

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
          case '1m':
              cutoffDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
              break
          case '3m':
              cutoffDate = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000)
              break
          case '6m':
              cutoffDate = new Date(now.getTime() - 180 * 24 * 60 * 60 * 1000)
              break
          case '1y':
              cutoffDate = new Date(now.getTime() - 365 * 24 * 60 * 60 * 1000)
              break
          case 'all':
          default:
              cutoffDate = null
      }

      // 1. Filter valid sold listings first
      // Use sold_date OR scraped_at as fallback (matches backend COALESCE logic)
      // Filter out prices under $1 to remove junk/error data
      const validSold = history.filter(h => {
          const validPrice = h.price !== undefined && h.price !== null && !isNaN(Number(h.price)) && Number(h.price) >= 1
          const effectiveDate = h.sold_date || h.scraped_at
          const validDate = effectiveDate && !isNaN(new Date(effectiveDate).getTime())
          const isSold = h.listing_type === 'sold' || !h.listing_type
          if (!validPrice || !validDate || !isSold) return false

          // Apply treatment filter (fuzzy matching for variants like "Preslab TAG 9")
          if (treatmentFilter !== 'all') {
              if (treatmentFilter.startsWith('subtype:')) {
                  const subtype = treatmentFilter.replace('subtype:', '')
                  if (h.product_subtype !== subtype) return false
              } else {
                  const t = (h.treatment || 'Classic Paper').toLowerCase()
                  const filter = treatmentFilter.toLowerCase()
                  // Exact match or starts with (e.g., "Preslab TAG" matches "Preslab TAG 9")
                  if (!(t === filter || t.startsWith(filter + ' ') || t.startsWith(filter + '-'))) return false
              }
          }

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

          // For items with product_subtype (NFTs, sealed), use subtype; otherwise use treatment
          const hasSubtype = !!h.product_subtype
          const treatment = hasSubtype ? (h.product_subtype || 'Unknown') : (h.treatment || 'Classic Paper')
          const isCardSealed = card?.rarity_name?.toUpperCase() === 'SEALED'
          // For sealed products, use subtype color; otherwise use treatment color
          const pointColor = isCardSealed || hasSubtype ? getSubtypeColor(h.product_subtype) : getTreatmentColor(h.treatment || 'Classic Paper')
          return {
              id: `${h.id}-${index}`,
              date: saleDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' }),
              timestamp: adjustedTimestamp,
              x: index,
              price: Number(h.price),
              treatment,
              product_subtype: h.product_subtype,
              treatmentColor: pointColor,
              treatmentSimple: hasSubtype ? h.product_subtype : simplifyTreatment(h.treatment || 'Classic Paper'),
              title: h.title,
              listing_type: 'sold',
              isGraded: isPSAGraded(h.title).graded,
              grade: isPSAGraded(h.title).grade,
              isActive: false
          }
      })

      // 4. Add active listings at the right edge (current time)
      // Filter out prices under $1 to remove junk/error data
      const activeListings = history.filter(h => {
          const validPrice = h.price !== undefined && h.price !== null && !isNaN(Number(h.price)) && Number(h.price) >= 1
          if (!(h.listing_type === 'active' && validPrice)) return false

          // Apply treatment filter to active listings too (fuzzy matching)
          if (treatmentFilter !== 'all') {
              if (treatmentFilter.startsWith('subtype:')) {
                  const subtype = treatmentFilter.replace('subtype:', '')
                  if (h.product_subtype !== subtype) return false
              } else {
                  const t = (h.treatment || 'Classic Paper').toLowerCase()
                  const filter = treatmentFilter.toLowerCase()
                  if (!(t === filter || t.startsWith(filter + ' ') || t.startsWith(filter + '-'))) return false
              }
          }
          return true
      })

      // Place active listings at the right side of chart, spaced out by price
      // Sort by price to spread vertically, then space horizontally
      const sortedActive = [...activeListings].sort((a, b) => a.price - b.price)
      const nowTime = now.getTime()
      // Calculate spacing: use 6 hours between each active listing for visual clarity
      const activeData = sortedActive.map((h, index) => {
          // For items with product_subtype (NFTs, sealed), use subtype; otherwise use treatment
          const hasSubtype = !!h.product_subtype
          const treatment = hasSubtype ? (h.product_subtype || 'Unknown') : (h.treatment || 'Classic Paper')
          const isCardSealed = card?.rarity_name?.toUpperCase() === 'SEALED'
          const pointColor = isCardSealed || hasSubtype ? getSubtypeColor(h.product_subtype) : getTreatmentColor(h.treatment || 'Classic Paper')
          return {
              id: `active-${h.id}-${index}`,
              date: 'Active',
              timestamp: nowTime + (index * 6 * 60 * 60 * 1000), // 6 hours offset per listing
              x: soldData.length + index,
              price: Number(h.price),
              treatment,
              product_subtype: h.product_subtype,
              treatmentColor: pointColor,
              treatmentSimple: hasSubtype ? h.product_subtype : simplifyTreatment(h.treatment || 'Classic Paper'),
              title: h.title,
              listing_type: 'active',
              isGraded: isPSAGraded(h.title).graded,
              grade: isPSAGraded(h.title).grade,
              isActive: true
          }
      })

      // 5. Compute daily volumes for volume bars
      const dailyVolumes: Record<string, number> = {}
      soldData.forEach(d => {
          const dayKey = new Date(d.timestamp).toISOString().split('T')[0]
          dailyVolumes[dayKey] = (dailyVolumes[dayKey] || 0) + 1
      })

      // Add volume to each data point
      const soldDataWithVolume = soldData.map(d => {
          const dayKey = new Date(d.timestamp).toISOString().split('T')[0]
          return { ...d, dailyVolume: dailyVolumes[dayKey] || 0 }
      })

      // Active listings don't count toward volume
      const activeDataWithVolume = activeData.map(d => ({ ...d, dailyVolume: 0 }))

      return [...soldDataWithVolume, ...activeDataWithVolume]
  }, [history, timeRange, treatmentFilter, card?.rarity_name])

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
      // Filter out active listings - only use sold data
      const soldData = chartData.filter(d => !d.isActive)
      if (!soldData.length) return null

      const prices = soldData.map(d => d.price)
      const minPrice = Math.min(...prices)
      const maxPrice = Math.max(...prices)
      const avgPrice = prices.reduce((a, b) => a + b, 0) / prices.length
      const firstPrice = prices[0]
      const lastPrice = prices[prices.length - 1]
      let priceChange = firstPrice > 0 ? ((lastPrice - firstPrice) / firstPrice) * 100 : 0

      // Cap trend at ±100% to avoid crazy numbers
      priceChange = Math.max(-100, Math.min(100, priceChange))

      // Only show meaningful trends (at least 2 data points)
      if (soldData.length < 2) {
          priceChange = 0
      }

      // Find dates for low and high prices
      const minItem = soldData.find(d => d.price === minPrice)
      const maxItem = soldData.find(d => d.price === maxPrice)
      const lowDate = minItem?.date || null
      const highDate = maxItem?.date || null

      // Calculate avg daily sold
      // Get the time span of the data
      const timestamps = soldData.map(d => d.timestamp)
      const firstTs = Math.min(...timestamps)
      const lastTs = Math.max(...timestamps)
      const daySpan = Math.max(1, Math.ceil((lastTs - firstTs) / (24 * 60 * 60 * 1000)))
      const avgDailySold = soldData.length / daySpan

      return {
        minPrice,
        maxPrice,
        avgPrice,
        priceChange,
        totalSales: soldData.length,
        lowDate,
        highDate,
        avgDailySold
      }
  }, [chartData])

  // Compute treatment-filtered metrics for PriceBox
  const filteredMetrics = useMemo(() => {
      if (!history) return null

      const now = new Date()
      const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)

      // Filter function for treatment (with fuzzy matching for variants like "Preslab TAG 9")
      const matchesTreatment = (h: MarketPrice) => {
          if (treatmentFilter === 'all') return true
          if (treatmentFilter.startsWith('subtype:')) {
              const subtype = treatmentFilter.replace('subtype:', '')
              return h.product_subtype === subtype
          }
          const t = (h.treatment || 'Classic Paper').toLowerCase()
          const filter = treatmentFilter.toLowerCase()
          // Exact match or starts with (e.g., "Preslab TAG" matches "Preslab TAG 9")
          return t === filter || t.startsWith(filter + ' ') || t.startsWith(filter + '-')
      }

      // Get filtered sold items
      const filteredSold = history.filter(h => {
          const isSold = h.listing_type === 'sold' || !h.listing_type
          const validPrice = h.price !== undefined && h.price !== null && !isNaN(Number(h.price)) && Number(h.price) > 0
          return isSold && validPrice && matchesTreatment(h)
      })

      // Get filtered active listings
      const filteredActive = history.filter(h => {
          const isActive = h.listing_type === 'active'
          const validPrice = h.price !== undefined && h.price !== null && !isNaN(Number(h.price)) && Number(h.price) > 0
          return isActive && validPrice && matchesTreatment(h)
      })

      // 30D Volume: count sales in last 30 days
      const volume30d = filteredSold.filter(h => {
          const effectiveDate = h.sold_date || h.scraped_at
          if (!effectiveDate) return false
          return new Date(effectiveDate) >= thirtyDaysAgo
      }).length

      // Highest Sale: max price from all filtered sold
      const maxPrice = filteredSold.length > 0
          ? Math.max(...filteredSold.map(h => Number(h.price)))
          : null

      // Min price (floor) from recent sales for volatility calculation
      const minPrice = filteredSold.length > 0
          ? Math.min(...filteredSold.map(h => Number(h.price)))
          : null

      // Seller Count: unique sellers from active listings
      const uniqueSellers = new Set(filteredActive.map(h => h.seller_name).filter(Boolean))
      const sellerCount = uniqueSellers.size

      // Listings Count: count of active listings
      const listingsCount = filteredActive.length

      // Lowest Ask (Buy Now price): minimum price from active listings
      const lowestAsk = filteredActive.length > 0
          ? Math.min(...filteredActive.map(h => Number(h.price)))
          : null

      // Highest Ask: maximum price from active listings (fallback for highest sale)
      const highestAsk = filteredActive.length > 0
          ? Math.max(...filteredActive.map(h => Number(h.price)))
          : null

      // Price Range: [min, max] from active listings (fallback for market price)
      const priceRange: [number, number] | null = filteredActive.length >= 2
          ? [lowestAsk!, highestAsk!]
          : null

      // Sales Price Range: [min, max] from sold listings - useful for NFTs with no active listings
      const salesPriceRange: [number, number] | null = filteredSold.length >= 2
          ? [minPrice!, maxPrice!]
          : null

      // Sales Count: total number of sold items
      const salesCount = filteredSold.length

      // Check if this is NFT data (OpenSea/Blokpax platforms)
      const hasNFTData = history.some(h => h.platform === 'opensea' || h.platform === 'blokpax')

      // Volatility: based on price spread
      const volatility = maxPrice && minPrice && minPrice > 0
          ? Math.min((maxPrice / minPrice - 1) / 10, 1) // Normalize to 0-1
          : null

      return {
          volume30d,
          maxPrice,
          minPrice,
          sellerCount,
          listingsCount,
          volatility,
          lowestAsk,
          highestAsk,
          priceRange,
          salesPriceRange,
          salesCount,
          hasNFTData
      }
  }, [history, treatmentFilter])

  // Get the lowest-priced active listing for Buy Now button
  // Only includes listings scraped within the last 24 hours to ensure freshness
  const lowestActiveListing = useMemo(() => {
      if (!history) return null

      const twentyFourHoursAgo = new Date(Date.now() - 24 * 60 * 60 * 1000)

      // Apply treatment filter matching logic
      const matchesTreatment = (h: MarketPrice) => {
          if (treatmentFilter === 'all') return true
          if (treatmentFilter.startsWith('subtype:')) {
              const subtype = treatmentFilter.replace('subtype:', '')
              return h.product_subtype === subtype
          }
          const t = (h.treatment || 'Classic Paper').toLowerCase()
          const filter = treatmentFilter.toLowerCase()
          return t === filter || t.startsWith(filter + ' ') || t.startsWith(filter + '-')
      }

      // Get all active listings with valid prices, URLs, and recent scrape time
      const activeListings = history.filter(h => {
          const isActive = h.listing_type === 'active'
          const validPrice = h.price !== undefined && h.price !== null && !isNaN(Number(h.price)) && Number(h.price) > 0
          const isFresh = h.scraped_at && new Date(h.scraped_at) >= twentyFourHoursAgo
          return isActive && validPrice && h.url && isFresh && matchesTreatment(h)
      })

      if (activeListings.length === 0) return null

      // Find the lowest-priced listing
      return activeListings.reduce((min, h) =>
          Number(h.price) < Number(min.price) ? h : min
      )
  }, [history, treatmentFilter])

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

  // Unified treatment pricing data - combines floor, ask, FMP, and confidence
  const unifiedTreatmentData = useMemo(() => {
      const treatments = new Set<string>()
      // Collect all treatments from all sources
      if (card?.floor_by_variant) Object.keys(card.floor_by_variant).forEach(t => treatments.add(t))
      if (card?.lowest_ask_by_variant) Object.keys(card.lowest_ask_by_variant).forEach(t => treatments.add(t))
      if (pricingData?.by_treatment) pricingData.by_treatment.forEach(p => treatments.add(p.treatment))
      if (orderBookData?.by_treatment) orderBookData.by_treatment.forEach(p => treatments.add(p.treatment))

      return Array.from(treatments).map(treatment => ({
          treatment,
          floor: card?.floor_by_variant?.[treatment] ?? null,
          ask: card?.lowest_ask_by_variant?.[treatment] ?? null,
          fmp: pricingData?.by_treatment?.find(t => t.treatment === treatment)?.fmp ?? null,
          confidence: orderBookData?.by_treatment?.find(t => t.treatment === treatment)?.confidence ?? 0,
          salesCount: pricingData?.by_treatment?.find(t => t.treatment === treatment)?.sales_count ?? 0,
      }))
      // Filter out rows with no meaningful data
      .filter(row => row.floor !== null || row.ask !== null || row.fmp !== null || row.salesCount > 0)
      .sort((a, b) => (a.floor ?? Infinity) - (b.floor ?? Infinity))
  }, [card, pricingData, orderBookData])

  if (isLoadingCard) {
    return <CardDetailPageSkeleton />
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
      <div key={cardId}>
          {/* Mobile Sticky Header */}
          <StickyPriceHeader
            cardName={card.name}
            price={card.floor_price ?? card.lowest_ask}
            priceLabel={card.floor_price ? 'Floor' : 'Ask'}
            isVisible={isScrolledPastPriceBox}
            onViewListings={() => {
              // Scroll to listings section
              document.getElementById('sales-listings-section')?.scrollIntoView({ behavior: 'smooth' })
            }}
          />

          {/* Mobile Sticky Action Footer */}
          <MobileStickyActions
            isVisible={isScrolledPastPriceBox}
            onAddToPortfolio={() => {
              setShowAddModal(true)
              setMobileAddedFeedback(true)
              setTimeout(() => setMobileAddedFeedback(false), 2000)
            }}
            showAddedFeedback={mobileAddedFeedback}
            buyNowUrl={lowestActiveListing?.url ?? undefined}
            lowestBuyNowPrice={lowestActiveListing?.price ?? null}
            listingsCount={card.inventory || 0}
            onViewListings={() => {
              document.getElementById('sales-listings-section')?.scrollIntoView({ behavior: 'smooth' })
            }}
          />

          <CardDetailLayout
            navigation={
              <CardDetailHeader
                cardName={card.name}
                setName={card.set_name}
                isLoggedIn={isLoggedIn}
                onSetPriceAlert={() => setShowPriceAlertModal(true)}
              />
            }
            hero={
              <CardHero
                card={card}
                selectedTreatment={treatmentFilter !== 'all' ? treatmentFilter : undefined}
              />
            }
            priceBox={
              <div ref={priceBoxRef}>
                <PriceBox
                  card={card}
                  treatmentFilter={treatmentFilter}
                  onTreatmentChange={setTreatmentFilter}
                  treatmentOptions={unifiedTreatmentData.map(t => ({
                    value: t.treatment,
                    label: t.treatment,
                    floorPrice: t.floor ?? undefined,
                    listingCount: undefined
                  }))}
                  pricingFMP={pricingData?.fair_market_price ?? undefined}
                  isLoggedIn={isLoggedIn}
                  onAddToPortfolio={() => setShowAddModal(true)}
                  metaVoteSlot={!isSealed ? <MetaVote cardId={card.id} /> : undefined}
                  productDetails={{
                    cardNumber: card.card_number,
                    rarity: card.rarity_name,
                    cardType: card.card_type,
                    orbital: card.orbital,
                    orbitalColor: card.orbital_color,
                    setName: card.set_name
                  }}
                  onSetPriceAlert={() => setShowPriceAlertModal(true)}
                  onViewListings={() => {
                    document.getElementById('sales-listings-section')?.scrollIntoView({ behavior: 'smooth' })
                  }}
                  volatility={filteredMetrics?.volatility ?? undefined}
                  filteredVolume30d={treatmentFilter !== 'all' ? filteredMetrics?.volume30d : undefined}
                  filteredMaxPrice={treatmentFilter !== 'all' ? filteredMetrics?.maxPrice : undefined}
                  filteredSellerCount={treatmentFilter !== 'all' ? filteredMetrics?.sellerCount : undefined}
                  filteredListingsCount={treatmentFilter !== 'all' ? filteredMetrics?.listingsCount : undefined}
                  lowestBuyNowPrice={lowestActiveListing?.price ?? null}
                  buyNowUrl={lowestActiveListing?.url ?? undefined}
                  filteredMarketPrice={
                    treatmentFilter !== 'all'
                      ? (pricingData?.by_treatment?.find(t => t.treatment === treatmentFilter)?.fmp ?? null)
                      : undefined
                  }
                  highestAsk={treatmentFilter !== 'all' ? filteredMetrics?.highestAsk : undefined}
                  priceRange={treatmentFilter !== 'all' ? filteredMetrics?.priceRange : undefined}
                  salesPriceRange={filteredMetrics?.salesPriceRange}
                  salesCount={filteredMetrics?.salesCount}
                />
              </div>
            }
          >
                    {/* Stacked Layout: Chart -> Variant Prices -> FMP -> Sales */}
                    <div className="space-y-4">

                        {/* Chart Section (Full Width) - MOVED TO TOP */}
                        <div>
                            <div className="border border-border rounded bg-card">
                                <div className="w-full bg-muted/10 rounded flex flex-col">
                                    {/* Chart Header with Time Range Buttons */}
                                    <div className="px-3 py-2 border-b border-border/50 flex justify-between items-center gap-2">
                                        <div className="flex items-center gap-3">
                                            <h3 className="text-xs font-bold uppercase tracking-wider">Price History</h3>
                                            <div className="flex items-center gap-2 text-xs">
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

                                        {/* Time Range */}
                                        <div className="flex items-center bg-background rounded border border-border overflow-hidden flex-shrink-0">
                                            {[
                                                { value: '1m', label: '1M' },
                                                { value: '3m', label: '3M' },
                                                { value: '6m', label: '6M' },
                                                { value: '1y', label: '1Y' },
                                                { value: 'all', label: 'ALL' },
                                            ].map(({ value, label }) => (
                                                <button
                                                    key={value}
                                                    onClick={() => setTimeRange(value as TimeRange)}
                                                    className={clsx(
                                                        "px-2.5 py-1.5 text-xs font-bold uppercase transition-colors",
                                                        timeRange === value ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
                                                    )}
                                                >
                                                    {label}
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Chart - lazy loaded */}
                                    <div className="h-[160px] px-3 pt-1 pb-0">
                                        {isLoadingHistory ? (
                                            <SkeletonChart height="h-full" />
                                        ) : chartData.length > 0 ? (
                                            <Suspense fallback={<SkeletonChart height="h-full" />}>
                                                <PriceHistoryChart
                                                    data={chartData}
                                                    floorHistory={fmpHistory}
                                                />
                                            </Suspense>
                                        ) : (
                                            <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
                                                <div className="text-xs uppercase mb-2">
                                                    {timeRange !== 'all' && totalAllTimeSales > 0
                                                        ? `No sales in last ${
                                                            timeRange === '1m' ? '1 month' :
                                                            timeRange === '3m' ? '3 months' :
                                                            timeRange === '6m' ? '6 months' :
                                                            timeRange === '1y' ? 'year' : timeRange
                                                        }`
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

                                    {/* Inline Stats Row */}
                                    {chartStats && chartStats.totalSales > 0 && (
                                        <div className="px-3 py-2 border-t border-border/30 flex items-center justify-between gap-4 text-xs overflow-x-auto">
                                            <div className="flex items-center gap-1.5 shrink-0">
                                                <span className="text-muted-foreground uppercase">Low</span>
                                                <span className="font-mono font-bold text-rose-400">${chartStats.minPrice?.toFixed(2) ?? '---'}</span>
                                                <span className="text-muted-foreground/60">{chartStats.lowDate ? new Date(chartStats.lowDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : ''}</span>
                                            </div>
                                            <div className="flex items-center gap-1.5 shrink-0">
                                                <span className="text-muted-foreground uppercase">High</span>
                                                <span className="font-mono font-bold text-brand-300">${chartStats.maxPrice?.toFixed(2) ?? '---'}</span>
                                                <span className="text-muted-foreground/60">{chartStats.highDate ? new Date(chartStats.highDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : ''}</span>
                                            </div>
                                            <div className="flex items-center gap-1.5 shrink-0">
                                                <span className="text-muted-foreground uppercase">Sold</span>
                                                <span className="font-mono font-bold">{chartStats.totalSales}</span>
                                            </div>
                                            <div className="flex items-center gap-1.5 shrink-0">
                                                <span className="text-muted-foreground uppercase">Avg/Day</span>
                                                <span className="font-mono font-bold">{chartStats.avgDailySold?.toFixed(1) ?? '---'}</span>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Sales Table (Full Width) */}
                        <div id="sales-listings-section" className="border border-border rounded bg-card overflow-hidden scroll-mt-16">
                                        <div className="px-4 py-3 border-b border-border bg-muted/20 flex items-center justify-between gap-4">
                                            <h3 className="text-base sm:text-lg font-bold flex items-center gap-2 flex-wrap">
                                                <span>{activeListings.length} Listings</span>
                                                {treatmentFilter !== 'all' && (
                                                    <span className="text-sm text-muted-foreground font-normal">· {treatmentFilter}</span>
                                                )}
                                            </h3>
                                            {soldListings.length > 0 && (
                                                <label className="flex items-center gap-2 cursor-pointer shrink-0">
                                                    <input
                                                        type="checkbox"
                                                        checked={showSoldListings}
                                                        onChange={(e) => setShowSoldListings(e.target.checked)}
                                                        className="w-4 h-4 rounded border-border bg-background text-primary focus:ring-primary"
                                                    />
                                                    <span className="text-xs text-muted-foreground">
                                                        Show {soldListings.length} sold
                                                    </span>
                                                </label>
                                            )}
                                        </div>

                            {/* TCGPlayer-style listing rows */}
                            <div className="divide-y divide-border">
                                {isLoadingHistory ? (
                                    // Loading skeletons
                                    Array.from({ length: 5 }).map((_, i) => (
                                        <div key={i} className="px-4 py-3 flex items-center gap-4 animate-pulse">
                                            <div className="flex-1 space-y-1.5">
                                                <div className="h-4 bg-muted rounded w-28" />
                                                <div className="h-3 bg-muted rounded w-20" />
                                            </div>
                                            <div className="h-5 bg-muted rounded w-16" />
                                            <div className="h-8 bg-muted rounded w-16" />
                                        </div>
                                    ))
                                ) : displayListings.length ? (
                                    displayListings.map((listing, idx) => {
                                        const isSold = listing.listing_type === 'sold'
                                        const feedbackPercent = listing.seller_feedback_percent
                                        const feedbackScore = listing.seller_feedback_score
                                        const saleDate = listing.sold_date || listing.scraped_at
                                        const treatment = listing.treatment || listing.product_subtype

                                        return (
                                            <div
                                                key={listing.id || idx}
                                                className="px-4 py-3 hover:bg-muted/10 transition-colors"
                                            >
                                                {/* Mobile: stacked layout, Desktop: horizontal */}
                                                <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
                                                    {/* Left: Seller Info */}
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center gap-2 flex-wrap">
                                                            <span className="font-semibold text-sm sm:text-base">
                                                                {listing.seller_name || 'Unknown'}
                                                            </span>
                                                            {feedbackScore != null && feedbackPercent != null && (
                                                                <span className={clsx(
                                                                    "text-xs sm:text-sm",
                                                                    feedbackPercent >= 99 ? 'text-brand-300' : feedbackPercent >= 95 ? 'text-yellow-500' : 'text-muted-foreground'
                                                                )}>
                                                                    {feedbackPercent.toFixed(0)}% ({feedbackScore.toLocaleString()})
                                                                </span>
                                                            )}
                                                            {isSold && (
                                                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-400 uppercase font-bold">
                                                                    Sold
                                                                </span>
                                                            )}
                                                        </div>
                                                        {listing.title && (
                                                            <div className="text-xs sm:text-sm text-muted-foreground mt-1 truncate">
                                                                {listing.title}
                                                            </div>
                                                        )}
                                                        {isSold && saleDate && (
                                                            <div className="text-xs text-muted-foreground/70 mt-0.5">
                                                                {new Date(saleDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' })}
                                                            </div>
                                                        )}
                                                    </div>

                                                    {/* Right side: Treatment + Price + Buttons */}
                                                    <div className="flex items-center gap-2 sm:gap-3 justify-between sm:justify-end shrink-0">
                                                        {/* Treatment Badge - fixed width for alignment */}
                                                        <div className="w-[100px] sm:w-[120px] flex justify-end">
                                                            {treatment && (
                                                                <TreatmentBadge treatment={treatment} size="sm" />
                                                            )}
                                                        </div>

                                                        {/* Price - fixed width for alignment */}
                                                        <div className="w-[90px] sm:w-[100px] text-right">
                                                            <span className="text-lg sm:text-xl font-mono font-bold">
                                                                ${Number(listing.price).toFixed(2)}
                                                            </span>
                                                        </div>

                                                        {/* Action Buttons - fixed width for alignment */}
                                                        <div className="w-[50px] sm:w-[180px] flex justify-end gap-1.5 sm:gap-2">
                                                            <button
                                                                onClick={() => setSelectedListing(listing)}
                                                                className="px-2 sm:px-3 py-1.5 sm:py-2 border border-border text-xs font-bold uppercase rounded hover:bg-muted/50 hover:border-muted-foreground/50 transition-colors"
                                                            >
                                                                View
                                                            </button>
                                                            {listing.url && (
                                                                <a
                                                                    href={listing.url}
                                                                    target="_blank"
                                                                    rel="noopener noreferrer"
                                                                    className="hidden sm:inline-flex px-3 py-2 bg-primary text-primary-foreground text-xs font-bold uppercase rounded hover:bg-primary/90 transition-colors whitespace-nowrap"
                                                                >
                                                                    Go to Listing
                                                                </a>
                                                            )}
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        )
                                    })
                                ) : (
                                    <div className="p-8 text-center text-muted-foreground text-xs uppercase">
                                        No listings available
                                    </div>
                                )}
                            </div>

                            {/* Pagination Controls */}
                            {displayListings.length > 10 && (
                                <div className="flex items-center justify-center px-4 py-3 border-t border-border bg-muted/10">
                                    <p className="text-xs text-muted-foreground">
                                        Showing {displayListings.length} listings
                                    </p>
                                </div>
                            )}
                        </div>

                        {/* Similar Cards - at bottom */}
                        {(similarData?.similar_cards?.length ?? 0) > 0 && (
                            <SimilarCards
                                title="Similar Cards"
                                cards={similarData?.similar_cards ?? []}
                                isLoading={isLoadingSimilar}
                            />
                        )}

                    </div>
          </CardDetailLayout>

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
                        <div className="p-4 border-b border-border">
                            <div className="flex justify-between items-center mb-3">
                                <h2 className="text-sm font-bold uppercase tracking-tight text-muted-foreground">Listing Details</h2>
                                <button onClick={() => setSelectedListing(null)} className="text-muted-foreground hover:text-foreground transition-colors p-1">
                                    <X className="w-5 h-5" />
                                </button>
                            </div>
                            {/* Primary CTA - View on Platform */}
                            <a
                                href={selectedListing.url || `https://www.ebay.com/sch/i.html?_nkw=${encodeURIComponent(selectedListing.title)}&LH_Complete=1`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className={clsx(
                                    "flex items-center justify-center gap-2 w-full py-3 rounded font-bold text-sm uppercase tracking-wide transition-colors",
                                    selectedListing.url?.includes('opensea') ? 'bg-cyan-600 hover:bg-cyan-700 text-white' :
                                    selectedListing.url?.includes('blokpax') ? 'bg-purple-600 hover:bg-purple-700 text-white' :
                                    'bg-blue-600 hover:bg-blue-700 text-white'
                                )}
                                onClick={() => {
                                    const platform = selectedListing.url?.includes('opensea') ? 'opensea' :
                                                    selectedListing.url?.includes('blokpax') ? 'blokpax' :
                                                    selectedListing.url?.includes('ebay') ? 'ebay' : 'external'
                                    analytics.trackExternalLinkClick(platform, cardId, selectedListing.title)
                                }}
                            >
                                View on {selectedListing.url?.includes('opensea') ? 'OpenSea' :
                                         selectedListing.url?.includes('blokpax') ? 'Blokpax' :
                                         selectedListing.url?.includes('ebay') ? 'eBay' : 'Marketplace'}
                                <ExternalLink className="w-4 h-4" />
                            </a>
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
                                    <div className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest mb-1">
                                        {selectedListing.product_subtype ? 'Subtype' : 'Treatment'}
                                    </div>
                                    {selectedListing.product_subtype ? (
                                        <ProductSubtypeBadge subtype={selectedListing.product_subtype} size="xs" />
                                    ) : (
                                        <TreatmentBadge treatment={selectedListing.treatment || 'Classic Paper'} size='xs' />
                                    )}
                                </div>
                            </div>

                            {/* Bid Count - only show for active auctions with bids */}
                            {selectedListing.listing_type === 'active' && selectedListing.bid_count != null && selectedListing.bid_count > 0 && (
                                <div>
                                    <div className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest mb-1">Bids</div>
                                    <div className="text-sm font-mono font-bold text-amber-400">
                                        {selectedListing.bid_count}
                                    </div>
                                </div>
                            )}

                            {/* NFT Traits Section - only for OpenSea items with traits */}
                            {selectedListing.traits && selectedListing.traits.length > 0 && (
                                <div className="pt-4 border-t border-border">
                                    <h3 className="text-xs font-bold uppercase tracking-widest mb-3 flex items-center gap-2">
                                        <div className="w-1 h-4 rounded-full bg-cyan-500"></div>
                                        NFT Traits
                                        <span className="text-[10px] text-muted-foreground font-normal">
                                            ({selectedListing.traits.length})
                                        </span>
                                    </h3>
                                    <div className="space-y-2">
                                        {selectedListing.traits.slice(0, 4).map((trait, idx) => (
                                            <div key={idx} className="flex justify-between items-center text-xs">
                                                <span className="text-muted-foreground uppercase text-[10px]">
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
                                        {selectedListing.traits.length > 4 && (
                                            <div className="text-[10px] text-muted-foreground text-center pt-1">
                                                + {selectedListing.traits.length - 4} more
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

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

                            {/* Description - only if available */}
                            {selectedListing.description && (
                                <div className="pt-4 border-t border-border">
                                    <p className="text-xs text-muted-foreground italic leading-relaxed">
                                        "{selectedListing.description}"
                                    </p>
                                </div>
                            )}

                            {/* Footer - Data timestamp and report link */}
                            <div className="pt-4 mt-auto border-t border-border flex items-center justify-between text-[10px] text-muted-foreground">
                                <span>
                                    Updated {selectedListing.scraped_at
                                        ? new Date(selectedListing.scraped_at).toLocaleDateString()
                                        : 'N/A'}
                                </span>
                                <button
                                    onClick={() => {
                                        setReportReason('')
                                        setReportNotes('')
                                        setReportSubmitted(false)
                                        setShowReportModal(true)
                                    }}
                                    className="flex items-center gap-1 hover:text-amber-500 transition-colors"
                                >
                                    <Flag className="w-3 h-3" /> Report
                                </button>
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

            {/* Price Alert Modal */}
            {card && (
                <PriceAlertModal
                    isOpen={showPriceAlertModal}
                    onClose={() => setShowPriceAlertModal(false)}
                    cardId={card.id}
                    cardName={card.name}
                    currentPrice={card.floor_price || card.latest_price}
                    onCreateAlert={async (alert) => {
                        await api.post('price-alerts', {
                            json: {
                                card_id: alert.cardId,
                                target_price: alert.targetPrice,
                                alert_type: alert.alertType,
                            }
                        }).json()
                    }}
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

          {/* Sticky Mobile Price Bar - visible only on mobile */}
          <div className="md:hidden fixed bottom-0 left-0 right-0 bg-background/95 backdrop-blur-sm border-t border-border px-4 py-3 flex items-center justify-between z-50">
              <div>
                  <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Floor Price</div>
                  <div className="text-xl font-mono font-bold">
                      ${card.floor_price?.toFixed(2) || card.lowest_ask?.toFixed(2) || '---'}
                  </div>
              </div>
              <button
                  onClick={() => setShowAddModal(true)}
                  className="flex items-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded font-bold text-sm uppercase hover:bg-primary/90 transition-colors"
              >
                  <Wallet className="w-4 h-4" />
                  Track
              </button>
          </div>
      </div>
  )
}
