import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { api } from '../utils/auth'
import { analytics } from '~/services/analytics'
import { ArrowLeft, TrendingUp, ArrowUp, ArrowDown, Activity, Zap, BarChart3, DollarSign, TableIcon, PieChartIcon, LineChart, Tag } from 'lucide-react'
import { Tooltip } from '../components/ui/tooltip'
import { lazy, Suspense } from 'react'
import { useCurrentUser } from '../context/UserContext'

// Lazy load recharts components (368KB) - only loads when user clicks Sentiment tab
const SentimentChart = lazy(() => import('../components/charts/SentimentChart'))
import { ColumnDef, flexRender, getCoreRowModel, useReactTable, getSortedRowModel, SortingState, getPaginationRowModel } from '@tanstack/react-table'
import { useState, useMemo, useEffect } from 'react'
import clsx from 'clsx'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Clock } from 'lucide-react'
import { TreatmentBadge } from '../components/TreatmentBadge'
import { LoginUpsellOverlay } from '../components/LoginUpsellOverlay'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select"

export const Route = createFileRoute('/market')({
  component: MarketAnalysis
})

type MarketCard = {
    id: number
    slug?: string
    name: string
    set_name: string
    rarity_id: number
    latest_price: number
    avg_price: number
    floor_price?: number // Avg of 4 lowest sales - THE standard price
    volume_30d: number // Mapped from volume_period (Total/Window)
    volume_change: number // Delta
    price_delta_24h: number
    dollar_volume: number // Total $ traded in period (sum of sale prices)
    deal_rating: number
    treatment?: string
}

type AnalyticsTab = 'table' | 'volume' | 'sentiment' | 'prices' | 'deals'

function MarketAnalysis() {
  const navigate = useNavigate()
  const [sorting, setSorting] = useState<SortingState>([{ id: 'volume_30d', desc: true }])
  const [timeFrame, setTimeFrame] = useState('30d')
  const [hideLowSignal, setHideLowSignal] = useState(true)
  const [activeTab, setActiveTab] = useState<AnalyticsTab>('table')

  // Check if user is logged in
  const { user } = useCurrentUser()
  const isLoggedIn = !!user

  // Track market page view
  useEffect(() => {
    analytics.trackMarketPageView()
  }, [])

  // Fetch actual deal listings (active listings below floor price)
  // Only show listings scraped in the last 24 hours to avoid showing ended listings
  const { data: dealListings, isLoading: dealsLoading } = useQuery({
    queryKey: ['market-deals', timeFrame],
    queryFn: async () => {
      // Get active listings sorted by price ascending, only from last 24h to ensure freshness
      const data = await api.get(`market/listings?listing_type=active&time_period=24h&sort_by=price&sort_order=asc&limit=200`).json<{
        items: Array<{
          id: number
          card_id: number
          card_name: string
          card_slug: string
          card_image_url: string | null
          title: string
          price: number
          floor_price: number | null
          vwap: number | null
          platform: string
          treatment: string | null
          url: string
          seller_name: string | null
          scraped_at: string | null
          bid_count: number | null
          listed_at: string | null
          listing_format: 'auction' | 'buy_it_now' | 'best_offer' | null
        }>
      }>()

      // Filter to only listings below floor price and calculate deal %
      const now = Date.now()
      return data.items
        .filter(l => l.floor_price && l.price < l.floor_price)
        .map(l => {
          // Calculate hours since last seen (scraped_at)
          let hoursSinceSeen = 0
          if (l.scraped_at) {
            const scrapedTime = new Date(l.scraped_at).getTime()
            hoursSinceSeen = (now - scrapedTime) / (1000 * 60 * 60)
          }

          // Use listing_format from API (properly detected by scraper)
          // Fallback: if bid_count > 0, it's definitely an auction
          const listingFormat = l.listing_format ?? ((l.bid_count ?? 0) > 0 ? 'auction' : null)

          return {
            ...l,
            dealPct: l.floor_price ? ((l.floor_price - l.price) / l.floor_price) * 100 : 0,
            listingFormat,
            bidCount: l.bid_count ?? 0,
            hoursSinceSeen,
            // Listing is "fresh" if seen in last 6 hours (or if no scraped_at data)
            isFresh: !l.scraped_at || hoursSinceSeen < 6
          }
        })
        // Prioritize fresh listings, then sort by deal %
        .sort((a, b) => {
          // Fresh listings first
          if (a.isFresh !== b.isFresh) return a.isFresh ? -1 : 1
          // Then by deal percentage
          return b.dealPct - a.dealPct
        })
        .slice(0, 30)
    },
    staleTime: 2 * 60 * 1000, // 2 minutes
    enabled: activeTab === 'deals', // Only fetch when deals tab is active
  })

  // Fetch treatment price floors
  const { data: treatments } = useQuery({
    queryKey: ['treatments'],
    queryFn: async () => {
        return await api.get('market/treatments').json<{ name: string; min_price: number; count: number }[]>()
    },
    staleTime: 10 * 60 * 1000, // 10 minutes - treatment floors change slowly
  })

  // Fetch optimized overview data from new endpoint
  // Longer time periods get longer cache times since they change less
  const cacheTimeByPeriod: Record<string, number> = {
    '1h': 1 * 60 * 1000,   // 1 minute for hourly
    '24h': 2 * 60 * 1000,  // 2 minutes for daily
    '7d': 5 * 60 * 1000,   // 5 minutes for weekly
    '30d': 10 * 60 * 1000, // 10 minutes for monthly
    '90d': 15 * 60 * 1000, // 15 minutes for quarterly
    'all': 20 * 60 * 1000, // 20 minutes for all time
  }

  const { data: rawCards, isLoading, isFetching } = useQuery({
    queryKey: ['market-overview', timeFrame],
    queryFn: async () => {
        const data = await api.get(`market/overview?time_period=${timeFrame}`).json<any[]>()
        return data.map(c => {
            // Cap trend percentage at ±100% to avoid crazy numbers
            let priceDelta = c.price_delta_period ?? 0
            priceDelta = Math.max(-100, Math.min(100, priceDelta))

            // Only show trend if there's enough volume (at least 2 sales)
            const volumePeriod = c.volume_period ?? 0
            if (volumePeriod < 2) {
                priceDelta = 0
            }

            return {
                ...c,
                latest_price: c.latest_price ?? 0,
                floor_price: c.floor_price ?? null,
                volume_30d: volumePeriod,
                volume_change: c.volume_change ?? 0,
                price_delta_24h: priceDelta,
                deal_rating: c.deal_rating ?? 0,
                dollar_volume: c.dollar_volume ?? 0
            }
        }) as MarketCard[]
    },
    staleTime: cacheTimeByPeriod[timeFrame] || 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000, // 30 minutes cache
    placeholderData: (previousData) => previousData, // Keep showing old data while loading new
  })

  // Reset sorting to volume descending when timeframe changes
  useEffect(() => {
    setSorting([{ id: 'volume_30d', desc: true }])
  }, [timeFrame])

  // Filter out low signal cards (no confirmed sales)
  const cards = useMemo(() => {
    if (!rawCards) return []
    if (!hideLowSignal) return rawCards
    return rawCards.filter(c => (c.volume_30d ?? 0) > 0)
  }, [rawCards, hideLowSignal])

  // Compute Stats
  const metrics = useMemo(() => {
      const totalVolume = cards.reduce((acc, c) => acc + c.volume_30d, 0)
      const totalDollarVolume = cards.reduce((acc, c) => acc + c.dollar_volume, 0)
      const avgVol = cards.length > 0 ? totalVolume / cards.length : 0
      const gainers = cards.filter(c => c.price_delta_24h > 0).length
      const losers = cards.filter(c => c.price_delta_24h < 0).length
      const unchanged = cards.filter(c => c.price_delta_24h === 0).length
      const totalAssets = cards.length

      // Top mover (biggest absolute change)
      const sortedByChange = [...cards].sort((a, b) => Math.abs(b.price_delta_24h) - Math.abs(a.price_delta_24h))
      const topMover = sortedByChange[0] || null

      // Most active (highest volume)
      const sortedByVolume = [...cards].sort((a, b) => b.volume_30d - a.volume_30d)
      const mostActive = sortedByVolume[0] || null

      // Highest value card
      const sortedByPrice = [...cards].sort((a, b) => b.latest_price - a.latest_price)
      const highestValue = sortedByPrice[0] || null

      // Breadth ratio
      const breadthRatio = totalAssets > 0 ? ((gainers - losers) / totalAssets * 100) : 0

      return { totalVolume, totalDollarVolume, avgVol, gainers, losers, unchanged, totalAssets, topMover, mostActive, highestValue, breadthRatio }
  }, [cards])

  // Top Lists
  const topGainers = useMemo(() => [...cards].sort((a, b) => b.price_delta_24h - a.price_delta_24h).slice(0, 5), [cards])
  const topLosers = useMemo(() => [...cards].sort((a, b) => a.price_delta_24h - b.price_delta_24h).slice(0, 5), [cards])

  // Chart Data - Volume Profile (top 20 with price context)
  const volumeChartData = useMemo(() => {
    const sorted = [...cards]
      .filter(c => c.volume_30d > 0)
      .sort((a, b) => b.volume_30d - a.volume_30d)
      .slice(0, 20)

    const maxVol = Math.max(...sorted.map(c => c.volume_30d))
    return sorted.map(c => ({
      name: c.name.length > 15 ? c.name.slice(0, 15) + '...' : c.name,
      fullName: c.name,
      slug: c.slug || c.id,
      volume: c.volume_30d,
      floor: c.floor_price || c.latest_price,
      dollarVolume: c.dollar_volume,
      trend: c.price_delta_24h,
      pctOfMax: (c.volume_30d / maxVol) * 100
    }))
  }, [cards])

  // Volume summary stats
  const volumeStats = useMemo(() => {
    const withVolume = cards.filter(c => c.volume_30d > 0)
    const total = withVolume.reduce((acc, c) => acc + c.volume_30d, 0)
    const avg = withVolume.length > 0 ? total / withVolume.length : 0
    const top5Share = volumeChartData.slice(0, 5).reduce((acc, c) => acc + c.volume, 0)
    return {
      total,
      avg: avg.toFixed(1),
      activeAssets: withVolume.length,
      top5Pct: total > 0 ? ((top5Share / total) * 100).toFixed(0) : '0'
    }
  }, [cards, volumeChartData])

  // Chart Data - Dollar Volume (total $ traded per card)
  const dollarVolumeChartData = useMemo(() => {
    const sorted = [...cards]
      .filter(c => c.dollar_volume > 0)
      .sort((a, b) => b.dollar_volume - a.dollar_volume)
      .slice(0, 20)

    const totalDollarVol = sorted.reduce((acc, c) => acc + c.dollar_volume, 0)
    return sorted.map(c => ({
      name: c.name.length > 12 ? c.name.slice(0, 12) + '...' : c.name,
      fullName: c.name,
      slug: c.slug || c.id,
      dollarVolume: c.dollar_volume,
      volume: c.volume_30d,
      floor: c.floor_price || c.latest_price,
      share: totalDollarVol > 0 ? ((c.dollar_volume / totalDollarVol) * 100).toFixed(1) : '0'
    }))
  }, [cards])

  // Dollar volume summary stats
  const dollarVolumeStats = useMemo(() => {
    const withVolume = cards.filter(c => c.dollar_volume > 0)
    const total = withVolume.reduce((acc, c) => acc + c.dollar_volume, 0)
    const top5 = dollarVolumeChartData.slice(0, 5).reduce((acc, c) => acc + c.dollarVolume, 0)
    const avgFloor = withVolume.length > 0
      ? withVolume.reduce((acc, c) => acc + (c.floor_price || c.latest_price), 0) / withVolume.length
      : 0
    return {
      total,
      top5Pct: total > 0 ? ((top5 / total) * 100).toFixed(0) : '0',
      avgFloor: avgFloor.toFixed(2)
    }
  }, [cards, dollarVolumeChartData])

  // Chart Data - Price Scatter (price vs volume with trend coloring)
  const priceScatterData = useMemo(() => {
    return cards
      .filter(c => (c.floor_price || c.latest_price) > 0 && c.volume_30d > 0)
      .map(c => ({
        name: c.name,
        slug: c.slug || c.id,
        price: c.floor_price || c.latest_price,
        volume: c.volume_30d,
        dollarVolume: c.dollar_volume,
        trend: c.price_delta_24h,
        isUp: c.price_delta_24h > 0,
        isDown: c.price_delta_24h < 0,
      }))
  }, [cards])

  // Price scatter summary stats
  const priceScatterStats = useMemo(() => {
    const withPrices = cards.filter(c => (c.floor_price || c.latest_price) > 0)
    const totalAssets = withPrices.length
    const avgPrice = totalAssets > 0
      ? withPrices.reduce((acc, c) => acc + (c.floor_price || c.latest_price), 0) / totalAssets
      : 0
    const highPrice = Math.max(...withPrices.map(c => c.floor_price || c.latest_price))
    const lowPrice = Math.min(...withPrices.filter(c => (c.floor_price || c.latest_price) > 0).map(c => c.floor_price || c.latest_price))
    const under25 = withPrices.filter(c => (c.floor_price || c.latest_price) < 25).length
    const premium = withPrices.filter(c => (c.floor_price || c.latest_price) >= 100).length
    return { totalAssets, avgPrice, highPrice, lowPrice, under25, premium }
  }, [cards])

  // Chart Data - Deal Rating Scatter (volume vs deal rating)
  const dealScatterData = useMemo(() => {
    return cards
      .filter(c => c.volume_30d > 0 && c.deal_rating !== 0)
      .map(c => ({
        name: c.name,
        slug: c.slug || c.id,
        volume: c.volume_30d,
        // Clamp deal rating to ±100% for clean chart display
        dealRating: Math.max(-100, Math.min(100, c.deal_rating)),
        floor: c.floor_price || c.latest_price,
        dollarVolume: c.dollar_volume,
        isGoodDeal: c.deal_rating < 0
      }))
  }, [cards])

  // Deal distribution buckets for the bar portion
  const dealDistributionData = useMemo(() => {
    const withDeals = cards.filter(c => c.volume_30d > 0 && c.deal_rating !== 0)
    const buckets = [
      { range: '50%+ Under', min: -100, max: -50, count: 0, color: '#059669', cards: [] as MarketCard[] },
      { range: '25-50% Under', min: -50, max: -25, count: 0, color: '#7dd3a8', cards: [] as MarketCard[] },
      { range: '10-25% Under', min: -25, max: -10, count: 0, color: '#34d399', cards: [] as MarketCard[] },
      { range: '±10% Fair', min: -10, max: 10, count: 0, color: '#64748b', cards: [] as MarketCard[] },
      { range: '10-25% Over', min: 10, max: 25, count: 0, color: '#fbbf24', cards: [] as MarketCard[] },
      { range: '25%+ Over', min: 25, max: 100, count: 0, color: '#f59e0b', cards: [] as MarketCard[] },
    ]

    withDeals.forEach(c => {
      const bucket = buckets.find(b => c.deal_rating >= b.min && c.deal_rating < b.max)
      if (bucket) {
        bucket.count++
        bucket.cards.push(c)
      }
    })

    return buckets.filter(b => b.count > 0)
  }, [cards])

  // Deal summary stats
  const dealStats = useMemo(() => {
    const withDeals = cards.filter(c => c.volume_30d > 0 && c.deal_rating !== 0)
    const goodDeals = withDeals.filter(c => c.deal_rating < -10).length
    const fairPriced = withDeals.filter(c => c.deal_rating >= -10 && c.deal_rating <= 10).length
    const overpriced = withDeals.filter(c => c.deal_rating > 10).length
    const avgDeal = withDeals.length > 0
      ? withDeals.reduce((acc, c) => acc + c.deal_rating, 0) / withDeals.length
      : 0
    return { goodDeals, fairPriced, overpriced, avgDeal: avgDeal.toFixed(1), total: withDeals.length }
  }, [cards])

  // Sentiment detailed breakdown with examples
  const sentimentChartData = useMemo(() => {
    const categories = [
      { name: '20%+ Up', min: 20, max: Infinity, fill: '#059669', cards: [] as MarketCard[] },
      { name: '5-20% Up', min: 5, max: 20, fill: '#7dd3a8', cards: [] as MarketCard[] },
      { name: '0-5% Up', min: 0.01, max: 5, fill: '#6ee7b7', cards: [] as MarketCard[] },
      { name: 'Flat', min: -0.01, max: 0.01, fill: '#64748b', cards: [] as MarketCard[] },
      { name: '0-5% Down', min: -5, max: -0.01, fill: '#fca5a5', cards: [] as MarketCard[] },
      { name: '5-20% Down', min: -20, max: -5, fill: '#ef4444', cards: [] as MarketCard[] },
      { name: '20%+ Down', min: -Infinity, max: -20, fill: '#b91c1c', cards: [] as MarketCard[] },
    ]

    cards.forEach(c => {
      const cat = categories.find(cat => {
        if (cat.name === 'Flat') return c.price_delta_24h === 0
        if (cat.min === -Infinity) return c.price_delta_24h <= cat.max
        if (cat.max === Infinity) return c.price_delta_24h >= cat.min
        return c.price_delta_24h >= cat.min && c.price_delta_24h < cat.max
      })
      if (cat) cat.cards.push(c)
    })

    return categories.filter(c => c.cards.length > 0).map(c => ({
      name: c.name,
      value: c.cards.length,
      fill: c.fill,
      topCard: c.cards.sort((a, b) => Math.abs(b.price_delta_24h) - Math.abs(a.price_delta_24h))[0]
    }))
  }, [cards])

  // Sentiment summary
  const sentimentStats = useMemo(() => {
    const gainers = cards.filter(c => c.price_delta_24h > 0)
    const losers = cards.filter(c => c.price_delta_24h < 0)
    const avgChange = cards.length > 0
      ? cards.reduce((acc, c) => acc + c.price_delta_24h, 0) / cards.length
      : 0
    return {
      gainers: gainers.length,
      losers: losers.length,
      avgChange: avgChange.toFixed(1),
      ratio: losers.length > 0 ? (gainers.length / losers.length).toFixed(2) : 'N/A'
    }
  }, [cards])

  // Table Columns
  const columns = useMemo<ColumnDef<MarketCard>[]>(() => [
      {
          accessorKey: 'name',
          header: ({ column }) => (
              <div className="cursor-pointer flex items-center gap-1 select-none" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>
                  ASSET {column.getIsSorted() && <ArrowUp className={clsx("w-3 h-3 transition-transform", column.getIsSorted() === 'desc' && "rotate-180")} />}
              </div>
          ),
          cell: ({ row }) => (
              <div className="min-w-[120px]">
                  <div className="font-bold text-foreground hover:text-primary cursor-pointer truncate" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: row.original.slug || String(row.original.id) } })}>
                      {row.original.name}
                  </div>
                  <div className="text-[10px] text-muted-foreground uppercase">{row.original.set_name}</div>
              </div>
          )
      },
      {
          accessorKey: 'floor_price',
          header: ({ column }) => (
              <Tooltip content="Floor price (avg of 4 lowest sales)">
                  <div className="flex items-center justify-end gap-1 cursor-pointer select-none" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>
                      FLOOR {column.getIsSorted() && <ArrowUp className={clsx("w-3 h-3 transition-transform", column.getIsSorted() === 'desc' && "rotate-180")} />}
                  </div>
              </Tooltip>
          ),
          cell: ({ row }) => {
              const price = row.original.floor_price || row.original.latest_price
              return <div className="text-right font-mono font-bold">{price ? `$${price.toFixed(2)}` : '---'}</div>
          }
      },
      {
          accessorKey: 'price_delta_24h',
          header: ({ column }) => (
              <Tooltip content="Price change over selected time period">
                  <div className="flex items-center justify-end gap-1 cursor-pointer select-none" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>
                      TREND {column.getIsSorted() && <ArrowUp className={clsx("w-3 h-3 transition-transform", column.getIsSorted() === 'desc' && "rotate-180")} />}
                  </div>
              </Tooltip>
          ),
          cell: ({ row }) => {
              const delta = row.original.price_delta_24h
              if (delta === 0) {
                  return <div className="text-right font-mono text-muted-foreground">-</div>
              }
              return (
                  <div className={clsx("text-right font-mono font-bold", delta > 0 ? "text-brand-300" : "text-red-500")}>
                      {delta > 0 ? '↑' : '↓'}{Math.abs(delta).toFixed(1)}%
                  </div>
              )
          }
      },
      {
          accessorKey: 'volume_30d',
          header: ({ column }) => (
              <Tooltip content="Number of sales in selected period">
                  <div className="flex items-center justify-end gap-1 cursor-pointer select-none" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>
                      VOL {column.getIsSorted() && <ArrowUp className={clsx("w-3 h-3 transition-transform", column.getIsSorted() === 'desc' && "rotate-180")} />}
                  </div>
              </Tooltip>
          ),
          cell: ({ row }) => <div className="text-right font-mono">{row.original.volume_30d}</div>
      },
      {
          accessorKey: 'dollar_volume',
          header: ({ column }) => (
              <Tooltip content="Total $ traded in period (sum of sale prices)">
                  <div className="flex items-center justify-end gap-1 cursor-pointer select-none" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>
                      $ VOL {column.getIsSorted() && <ArrowUp className={clsx("w-3 h-3 transition-transform", column.getIsSorted() === 'desc' && "rotate-180")} />}
                  </div>
              </Tooltip>
          ),
          cell: ({ row }) => {
              const vol = row.original.dollar_volume
              if (vol === 0 || !vol) return <div className="text-right font-mono text-muted-foreground">-</div>
              let formatted: string
              if (vol >= 1000000) {
                  formatted = `$${(vol / 1000000).toFixed(1)}M`
              } else if (vol >= 1000) {
                  formatted = `$${(vol / 1000).toFixed(1)}k`
              } else {
                  formatted = `$${vol.toFixed(0)}`
              }
              return <div className="text-right font-mono text-muted-foreground">{formatted}</div>
          }
      },
      {
          accessorKey: 'deal_rating',
          header: ({ column }) => (
              <Tooltip content="Last sale vs average: UNDER = below avg (good deal), OVER = above avg (premium)">
                  <div className="flex items-center justify-end gap-1 cursor-pointer select-none" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>
                      DEAL {column.getIsSorted() && <ArrowUp className={clsx("w-3 h-3 transition-transform", column.getIsSorted() === 'desc' && "rotate-180")} />}
                  </div>
              </Tooltip>
          ),
          cell: ({ row }) => {
              const rating = row.original.deal_rating
              const volume = row.original.volume_30d
              if (volume < 1 || (rating === 0 && row.original.avg_price === 0)) {
                  return <div className="text-right text-muted-foreground">-</div>
              }
              const isGood = rating < 0
              const displayRating = Math.min(Math.abs(rating), 99.9)
              return (
                  <div className="flex justify-end">
                      <span className={clsx("px-1.5 py-0.5 rounded text-[10px] uppercase font-bold border whitespace-nowrap",
                          isGood ? "border-brand-300/50 bg-brand-300/10 text-brand-300" : "border-amber-500/50 bg-amber-500/10 text-amber-500")}>
                          {displayRating.toFixed(0)}% {isGood ? 'UNDER' : 'OVER'}
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
          sorting: [{ id: 'volume_30d', desc: true }],
          pagination: {
              pageSize: 75,
          },
      },
  })

  if (!rawCards) {
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
    <div className="p-4 md:p-6 min-h-[calc(100vh-4rem)] lg:h-[calc(100vh-4rem)] bg-background text-foreground font-mono flex flex-col overflow-auto lg:overflow-hidden">
        <div className="max-w-[1800px] mx-auto w-full flex flex-col gap-4 h-auto lg:h-full lg:overflow-hidden">
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
                            <SelectTrigger className="w-[110px] h-8 text-xs">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="1h">1 Hour</SelectItem>
                                <SelectItem value="24h">24 Hours</SelectItem>
                                <SelectItem value="7d">7 Days</SelectItem>
                                <SelectItem value="30d">30 Days</SelectItem>
                                <SelectItem value="90d">90 Days</SelectItem>
                                <SelectItem value="all">All Time</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                    {/* Low Signal Filter */}
                    <label className="flex items-center gap-2 cursor-pointer select-none ml-4">
                        <input
                            type="checkbox"
                            checked={hideLowSignal}
                            onChange={e => setHideLowSignal(e.target.checked)}
                            className="w-3.5 h-3.5 rounded border-border bg-background text-primary focus:ring-1 focus:ring-primary cursor-pointer"
                        />
                        <span className="text-xs text-muted-foreground whitespace-nowrap">Hide Low Signal</span>
                    </label>
                </div>
                <div className="flex gap-4 text-xs text-muted-foreground uppercase font-bold">
                    <div className="flex items-center gap-1">
                        <span className="w-2 h-2 bg-brand-300 rounded-full animate-pulse"></span>
                        Live
                    </div>
                    {isFetching && (
                        <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                            <span className="w-1.5 h-1.5 bg-muted-foreground/60 rounded-full animate-ping"></span>
                            Refreshing
                        </div>
                    )}
                    <div>{cards.length} of {rawCards?.length || 0} Assets</div>
                </div>
            </div>

            {/* KPI Dashboard - Auto-fill grid that adapts to screen width */}
            <div
                className="grid gap-4 flex-shrink-0"
                style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}
            >
                {/* Assets Tracked */}
                <div className="bg-card border border-border p-4 rounded hover:border-primary/50 transition-colors">
                    <div className="text-[10px] uppercase text-muted-foreground font-medium mb-2">Assets Tracked</div>
                    <div className="text-3xl font-mono font-bold">{metrics.totalAssets}</div>
                    <div className="text-xs text-muted-foreground mt-1">with market activity</div>
                </div>

                {/* Period Volume */}
                <div className="bg-card border border-border p-4 rounded hover:border-primary/50 transition-colors">
                    <div className="text-[10px] uppercase text-muted-foreground font-medium mb-2">Period Volume</div>
                    <div className="text-3xl font-mono font-bold">{metrics.totalVolume.toLocaleString()}</div>
                    <div className="text-xs text-muted-foreground mt-1">units sold</div>
                </div>

                {/* Dollar Volume */}
                <div className="bg-card border border-border p-4 rounded hover:border-primary/50 transition-colors">
                    <div className="text-[10px] uppercase text-muted-foreground font-medium mb-2">Dollar Volume</div>
                    <div className="text-3xl font-mono font-bold text-brand-300">
                        {metrics.totalDollarVolume >= 1000000
                            ? `$${(metrics.totalDollarVolume / 1000000).toFixed(2)}M`
                            : metrics.totalDollarVolume >= 1000
                            ? `$${(metrics.totalDollarVolume / 1000).toFixed(1)}k`
                            : `$${metrics.totalDollarVolume.toFixed(0)}`}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">total $ traded</div>
                </div>

                {/* Market Sentiment with visual bar */}
                <div className="bg-card border border-border p-4 rounded hover:border-primary/50 transition-colors">
                    <div className="text-[10px] uppercase text-muted-foreground font-medium mb-2">Sentiment</div>
                    <div className="flex items-baseline gap-3">
                        <span className="text-2xl font-mono font-bold text-brand-300">{metrics.gainers}↑</span>
                        <span className="text-2xl font-mono font-bold text-red-500">{metrics.losers}↓</span>
                    </div>
                    {/* Visual sentiment bar */}
                    <div className="mt-2 h-1.5 bg-muted rounded-full overflow-hidden flex">
                        <div
                            className="bg-brand-300 h-full transition-all"
                            style={{ width: `${metrics.totalAssets > 0 ? (metrics.gainers / metrics.totalAssets) * 100 : 0}%` }}
                        />
                        <div
                            className="bg-muted-foreground/30 h-full transition-all"
                            style={{ width: `${metrics.totalAssets > 0 ? (metrics.unchanged / metrics.totalAssets) * 100 : 0}%` }}
                        />
                        <div
                            className="bg-red-500 h-full transition-all"
                            style={{ width: `${metrics.totalAssets > 0 ? (metrics.losers / metrics.totalAssets) * 100 : 0}%` }}
                        />
                    </div>
                    <div className="text-[10px] text-muted-foreground mt-1">{metrics.unchanged} unchanged</div>
                </div>

                {/* Most Active - clickable */}
                <div
                    className="bg-card border border-border p-4 rounded hover:border-primary/50 transition-colors cursor-pointer group"
                    onClick={() => metrics.mostActive && navigate({ to: '/cards/$cardId', params: { cardId: metrics.mostActive.slug || String(metrics.mostActive.id) } })}
                >
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] uppercase text-muted-foreground font-medium">Most Active</span>
                        <span className="text-xs text-primary opacity-0 group-hover:opacity-100 transition-opacity">View →</span>
                    </div>
                    <div className="text-lg font-bold truncate">{metrics.mostActive?.name || '-'}</div>
                    <div className="flex items-center justify-between mt-1">
                        <span className="text-xs text-muted-foreground">{metrics.mostActive?.volume_30d || 0} trades</span>
                        {metrics.mostActive?.floor_price && (
                            <span className="text-xs font-mono text-brand-300">${metrics.mostActive.floor_price.toFixed(2)}</span>
                        )}
                    </div>
                </div>

                {/* Highest Value - clickable */}
                <div
                    className="bg-card border border-border p-4 rounded hover:border-primary/50 transition-colors cursor-pointer group"
                    onClick={() => metrics.highestValue && navigate({ to: '/cards/$cardId', params: { cardId: metrics.highestValue.slug || String(metrics.highestValue.id) } })}
                >
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] uppercase text-muted-foreground font-medium">Highest Value</span>
                        <span className="text-xs text-primary opacity-0 group-hover:opacity-100 transition-opacity">View →</span>
                    </div>
                    <div className="text-lg font-bold truncate">{metrics.highestValue?.name || '-'}</div>
                    <div className="flex items-center justify-between mt-1">
                        <span className="text-xs text-muted-foreground">{metrics.highestValue?.volume_30d || 0} trades</span>
                        <span className="text-lg font-mono font-bold text-brand-300">
                            ${(metrics.highestValue?.floor_price || metrics.highestValue?.latest_price)?.toFixed(2) || '0'}
                        </span>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 flex-1 min-h-0 lg:overflow-hidden">
                {/* Left Column: Movers (Compact) - hidden on mobile, shown as collapsible or below table */}
                <div className="lg:col-span-1 space-y-4 overflow-y-auto order-2 lg:order-1">
                    <div className="bg-card border border-border rounded overflow-hidden">
                        <div className="p-3 border-b border-border bg-muted/20 flex justify-between items-center">
                            <span className="text-xs font-bold uppercase tracking-widest flex items-center gap-2 text-brand-300">
                                <ArrowUp className="w-3 h-3" /> Top Gainers
                            </span>
                    </div>
                    <div className="divide-y divide-border/50">
                            {topGainers.slice(0, 5).map(c => (
                                <div key={c.id} className="p-2 flex justify-between items-center hover:bg-muted/30 cursor-pointer transition-colors" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: c.slug || String(c.id) } })}>
                                    <div className="truncate w-24 text-xs font-bold">{c.name}</div>
                                    <div className="text-right">
                                        <div className="text-brand-300 text-xs font-mono font-bold">↑{Math.abs(c.price_delta_24h).toFixed(1)}%</div>
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
                                <div key={c.id} className="p-2 flex justify-between items-center hover:bg-muted/30 cursor-pointer transition-colors" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: c.slug || String(c.id) } })}>
                                    <div className="truncate w-24 text-xs font-bold">{c.name}</div>
                                    <div className="text-right">
                                        <div className="text-red-500 text-xs font-mono font-bold">↓{Math.abs(c.price_delta_24h).toFixed(1)}%</div>
                                    </div>
                                </div>
                            ))}
                            </div>
                    </div>

                    {/* Price Floors by Treatment */}
                    <div className="bg-card border border-border rounded overflow-hidden">
                        <div className="p-3 border-b border-border bg-muted/20">
                            <span className="text-xs font-bold uppercase tracking-widest flex items-center gap-2">
                                <DollarSign className="w-3 h-3" /> Treatment Floors
                            </span>
                            <div className="text-[9px] text-muted-foreground mt-0.5">Lowest sold price per treatment</div>
                        </div>
                        <div className="divide-y divide-border/50">
                            {treatments && treatments.length > 0 ? (
                                treatments.map(treatment => (
                                    <div key={treatment.name} className="px-3 py-2 flex justify-between items-center hover:bg-muted/20 transition-colors">
                                        <div className="flex items-center gap-2 min-w-0 flex-1">
                                            <TreatmentBadge treatment={treatment.name} size="xs" />
                                        </div>
                                        <div className="flex items-center gap-3 flex-shrink-0">
                                            <span className="text-[10px] text-muted-foreground tabular-nums">{treatment.count} sold</span>
                                            <span className="text-xs font-mono font-bold text-brand-300 w-16 text-right">${treatment.min_price.toFixed(2)}</span>
                                        </div>
                                    </div>
                                ))
                            ) : (
                                <div className="p-4 text-center text-xs text-muted-foreground">Loading...</div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Right Column: Tabbed Analytics */}
                <div className="lg:col-span-3 bg-card border border-border rounded flex flex-col min-h-[400px] lg:min-h-0 relative order-1 lg:order-2">
                    {/* Login gate overlay for non-logged-in users */}
                    {!isLoggedIn && (
                        <LoginUpsellOverlay
                            title="Unlock Market Analytics"
                            description="Sign in to access detailed market depth, sorting, and real-time analytics."
                        />
                    )}

                    {/* Tab Navigation */}
                    <div className="border-b border-border bg-muted/20 flex items-center gap-1 p-1 overflow-x-auto">
                        {[
                            { id: 'table' as AnalyticsTab, label: 'Table', icon: TableIcon },
                            { id: 'volume' as AnalyticsTab, label: 'Volume', icon: BarChart3 },
                            { id: 'sentiment' as AnalyticsTab, label: 'Sentiment', icon: PieChartIcon },
                            { id: 'prices' as AnalyticsTab, label: 'Prices', icon: LineChart },
                            { id: 'deals' as AnalyticsTab, label: 'Deals', icon: Tag },
                        ].map(tab => (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={clsx(
                                    "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap",
                                    activeTab === tab.id
                                        ? "bg-primary text-primary-foreground"
                                        : "text-muted-foreground hover:text-foreground hover:bg-muted"
                                )}
                            >
                                <tab.icon className="w-3.5 h-3.5" />
                                <span className="hidden sm:inline">{tab.label}</span>
                            </button>
                        ))}
                    </div>

                    {/* Tab Content */}
                    <div className="flex-1 overflow-auto">
                        {/* Table Tab */}
                        {activeTab === 'table' && (
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
                        )}

                        {/* Volume Tab - Combined Trading Activity */}
                        {activeTab === 'volume' && (
                            <div className="p-4 flex flex-col h-full overflow-auto">
                                {/* Summary Stats Row */}
                                <div className="grid grid-cols-4 gap-3 mb-4">
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Total Sales</div>
                                        <div className="text-xl font-bold font-mono">{volumeStats.total.toLocaleString()}</div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">$ Traded</div>
                                        <div className="text-xl font-bold font-mono text-brand-300">
                                            ${dollarVolumeStats.total >= 1000000
                                                ? `${(dollarVolumeStats.total / 1000000).toFixed(2)}M`
                                                : dollarVolumeStats.total >= 1000
                                                ? `${(dollarVolumeStats.total / 1000).toFixed(1)}k`
                                                : dollarVolumeStats.total.toFixed(0)}
                                        </div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Active Cards</div>
                                        <div className="text-xl font-bold font-mono">{volumeStats.activeAssets}</div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Avg Sale Price</div>
                                        <div className="text-xl font-bold font-mono">${dollarVolumeStats.avgFloor}</div>
                                    </div>
                                </div>

                                {/* Two-column layout: Most Traded + Highest Value */}
                                <div className="grid grid-cols-2 gap-4 mb-4">
                                    {/* Most Traded (by sales count) */}
                                    <div className="border rounded-lg p-3">
                                        <div className="flex items-center gap-2 mb-3">
                                            <Activity className="w-4 h-4 text-blue-400" />
                                            <span className="text-xs font-bold uppercase text-muted-foreground">Most Traded</span>
                                            <span className="text-[10px] text-muted-foreground ml-auto">by sales count</span>
                                        </div>
                                        <div className="space-y-2">
                                            {volumeChartData.slice(0, 8).map((item, i) => (
                                                <div
                                                    key={item.name}
                                                    className="flex items-center gap-2 hover:bg-muted/50 p-1.5 rounded cursor-pointer transition-colors"
                                                    onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: String(item.slug) } })}
                                                >
                                                    <span className="text-xs text-muted-foreground w-4">{i + 1}</span>
                                                    <div className="flex-1 min-w-0">
                                                        <div className="h-2 bg-muted/30 rounded overflow-hidden">
                                                            <div
                                                                className={clsx("h-full rounded", item.trend > 0 ? "bg-brand-500" : item.trend < 0 ? "bg-red-500" : "bg-muted-foreground")}
                                                                style={{ width: `${item.pctOfMax}%` }}
                                                            />
                                                        </div>
                                                    </div>
                                                    <span className="text-xs font-medium truncate max-w-[80px]">{item.fullName}</span>
                                                    <span className="text-xs font-mono font-bold text-blue-400">{item.volume}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Highest $ Volume */}
                                    <div className="border rounded-lg p-3">
                                        <div className="flex items-center gap-2 mb-3">
                                            <DollarSign className="w-4 h-4 text-brand-400" />
                                            <span className="text-xs font-bold uppercase text-muted-foreground">Highest Value</span>
                                            <span className="text-[10px] text-muted-foreground ml-auto">by $ traded</span>
                                        </div>
                                        <div className="space-y-2">
                                            {dollarVolumeChartData.slice(0, 8).map((item, i) => (
                                                <div
                                                    key={item.name}
                                                    className="flex items-center gap-2 hover:bg-muted/50 p-1.5 rounded cursor-pointer transition-colors"
                                                    onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: String(item.slug) } })}
                                                >
                                                    <span className="text-xs text-muted-foreground w-4">{i + 1}</span>
                                                    <div className="flex-1 min-w-0">
                                                        <div className="h-2 bg-muted/30 rounded overflow-hidden">
                                                            <div className="h-full bg-brand-500 rounded" style={{ width: `${parseFloat(item.share) * 5}%` }} />
                                                        </div>
                                                    </div>
                                                    <span className="text-xs font-medium truncate max-w-[80px]">{item.fullName}</span>
                                                    <span className="text-xs font-mono font-bold text-brand-400">
                                                        ${item.dollarVolume >= 1000 ? `${(item.dollarVolume / 1000).toFixed(1)}k` : item.dollarVolume}
                                                    </span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>

                                {/* Hot Cards - High activity + price movement */}
                                <div className="border rounded-lg p-3">
                                    <div className="flex items-center gap-2 mb-3">
                                        <Zap className="w-4 h-4 text-amber-400" />
                                        <span className="text-xs font-bold uppercase text-muted-foreground">Hot Cards</span>
                                        <span className="text-[10px] text-muted-foreground">High volume + price movement</span>
                                    </div>
                                    <div className="grid grid-cols-5 gap-2">
                                        {cards
                                            .filter(c => c.volume_30d >= 3 && Math.abs(c.price_delta_24h) > 0)
                                            .sort((a, b) => (b.volume_30d * Math.abs(b.price_delta_24h)) - (a.volume_30d * Math.abs(a.price_delta_24h)))
                                            .slice(0, 5)
                                            .map(card => (
                                                <div
                                                    key={card.id}
                                                    className="bg-muted/20 rounded p-2 hover:bg-muted/40 cursor-pointer transition-colors"
                                                    onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: card.slug || String(card.id) } })}
                                                >
                                                    <div className="text-xs font-bold truncate">{card.name}</div>
                                                    <div className="flex items-center justify-between mt-1">
                                                        <span className="text-[10px] font-mono">{card.volume_30d} sales</span>
                                                        <span className={clsx("text-[10px] font-mono font-bold", card.price_delta_24h > 0 ? "text-brand-400" : "text-red-400")}>
                                                            {card.price_delta_24h > 0 ? '+' : ''}{card.price_delta_24h.toFixed(1)}%
                                                        </span>
                                                    </div>
                                                    <div className="text-[10px] text-muted-foreground mt-0.5">${(card.floor_price || card.latest_price)?.toFixed(2)}</div>
                                                </div>
                                            ))}
                                        {cards.filter(c => c.volume_30d >= 3 && Math.abs(c.price_delta_24h) > 0).length === 0 && (
                                            <div className="col-span-5 text-center text-muted-foreground text-sm py-4">No hot cards in this period</div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Sentiment Chart Tab */}
                        {activeTab === 'sentiment' && (
                            <div className="p-4 flex flex-col h-full">
                                {/* Summary Stats Row */}
                                <div className="grid grid-cols-4 gap-3 mb-4">
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Gainers</div>
                                        <div className="text-xl font-bold font-mono text-brand-300">{sentimentStats.gainers}</div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Losers</div>
                                        <div className="text-xl font-bold font-mono text-red-500">{sentimentStats.losers}</div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Avg Change</div>
                                        <div className={clsx("text-xl font-bold font-mono", parseFloat(sentimentStats.avgChange) > 0 ? "text-brand-300" : parseFloat(sentimentStats.avgChange) < 0 ? "text-red-500" : "")}>
                                            {parseFloat(sentimentStats.avgChange) > 0 ? '+' : ''}{sentimentStats.avgChange}%
                                        </div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Bull/Bear Ratio</div>
                                        <div className="text-xl font-bold font-mono">{sentimentStats.ratio}</div>
                                    </div>
                                </div>

                                {/* Sentiment Distribution Chart - Lazy loaded */}
                                <div className="flex-1 min-h-[280px]">
                                    <Suspense fallback={
                                        <div className="flex items-center justify-center h-full">
                                            <div className="text-muted-foreground text-sm">Loading chart...</div>
                                        </div>
                                    }>
                                        <SentimentChart data={sentimentChartData} />
                                    </Suspense>
                                </div>

                                {/* Top Movers in each direction */}
                                <div className="mt-4 border-t border-border pt-3 grid grid-cols-2 gap-4">
                                    <div>
                                        <div className="text-[10px] uppercase text-brand-300 mb-2">Top Gainers</div>
                                        <div className="space-y-1">
                                            {topGainers.slice(0, 3).map((card, i) => (
                                                <div key={i} className="flex items-center justify-between text-xs bg-brand-300/10 rounded px-2 py-1 cursor-pointer hover:bg-brand-300/20" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: card.slug || String(card.id) } })}>
                                                    <span className="truncate flex-1">{card.name}</span>
                                                    <span className="font-mono text-brand-300 ml-2">+{card.price_delta_24h.toFixed(1)}%</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-[10px] uppercase text-red-500 mb-2">Top Losers</div>
                                        <div className="space-y-1">
                                            {topLosers.slice(0, 3).map((card, i) => (
                                                <div key={i} className="flex items-center justify-between text-xs bg-red-500/10 rounded px-2 py-1 cursor-pointer hover:bg-red-500/20" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: card.slug || String(card.id) } })}>
                                                    <span className="truncate flex-1">{card.name}</span>
                                                    <span className="font-mono text-red-500 ml-2">{card.price_delta_24h.toFixed(1)}%</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Prices Tab - Actionable Price Intelligence */}
                        {activeTab === 'prices' && (
                            <div className="p-4 flex flex-col h-full overflow-auto">
                                {/* Top Movers Section */}
                                <div className="grid grid-cols-2 gap-4 mb-4">
                                    {/* Top Gainers */}
                                    <div className="border border-brand-500/30 rounded-lg p-3 bg-brand-500/5">
                                        <div className="flex items-center gap-2 mb-3">
                                            <TrendingUp className="w-4 h-4 text-brand-400" />
                                            <span className="text-xs font-bold uppercase text-brand-400">Top Gainers</span>
                                        </div>
                                        <div className="space-y-2">
                                            {cards
                                                .filter(c => c.price_delta_24h > 0 && c.volume_30d > 0)
                                                .sort((a, b) => b.price_delta_24h - a.price_delta_24h)
                                                .slice(0, 5)
                                                .map((card, i) => (
                                                    <div
                                                        key={card.id}
                                                        className="flex items-center justify-between p-2 rounded bg-brand-500/10 hover:bg-brand-500/20 cursor-pointer transition-colors"
                                                        onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: card.slug || String(card.id) } })}
                                                    >
                                                        <div className="flex items-center gap-2 min-w-0">
                                                            <span className="text-xs text-brand-400 font-bold w-4">{i + 1}</span>
                                                            <span className="text-sm font-medium truncate">{card.name}</span>
                                                        </div>
                                                        <div className="flex items-center gap-3 flex-shrink-0">
                                                            <span className="text-xs text-muted-foreground font-mono">${(card.floor_price || card.latest_price)?.toFixed(2)}</span>
                                                            <span className="text-sm font-bold text-brand-400 font-mono">+{card.price_delta_24h.toFixed(1)}%</span>
                                                        </div>
                                                    </div>
                                                ))}
                                            {cards.filter(c => c.price_delta_24h > 0 && c.volume_30d > 0).length === 0 && (
                                                <div className="text-center text-muted-foreground text-sm py-4">No gainers in period</div>
                                            )}
                                        </div>
                                    </div>

                                    {/* Top Losers */}
                                    <div className="border border-red-500/30 rounded-lg p-3 bg-red-500/5">
                                        <div className="flex items-center gap-2 mb-3">
                                            <ArrowDown className="w-4 h-4 text-red-400" />
                                            <span className="text-xs font-bold uppercase text-red-400">Top Losers</span>
                                        </div>
                                        <div className="space-y-2">
                                            {cards
                                                .filter(c => c.price_delta_24h < 0 && c.volume_30d > 0)
                                                .sort((a, b) => a.price_delta_24h - b.price_delta_24h)
                                                .slice(0, 5)
                                                .map((card, i) => (
                                                    <div
                                                        key={card.id}
                                                        className="flex items-center justify-between p-2 rounded bg-red-500/10 hover:bg-red-500/20 cursor-pointer transition-colors"
                                                        onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: card.slug || String(card.id) } })}
                                                    >
                                                        <div className="flex items-center gap-2 min-w-0">
                                                            <span className="text-xs text-red-400 font-bold w-4">{i + 1}</span>
                                                            <span className="text-sm font-medium truncate">{card.name}</span>
                                                        </div>
                                                        <div className="flex items-center gap-3 flex-shrink-0">
                                                            <span className="text-xs text-muted-foreground font-mono">${(card.floor_price || card.latest_price)?.toFixed(2)}</span>
                                                            <span className="text-sm font-bold text-red-400 font-mono">{card.price_delta_24h.toFixed(1)}%</span>
                                                        </div>
                                                    </div>
                                                ))}
                                            {cards.filter(c => c.price_delta_24h < 0 && c.volume_30d > 0).length === 0 && (
                                                <div className="text-center text-muted-foreground text-sm py-4">No losers in period</div>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                {/* Price Tier Distribution */}
                                <div className="border rounded-lg p-3 mb-4">
                                    <div className="text-xs font-bold uppercase text-muted-foreground mb-3">Price Distribution</div>
                                    <div className="space-y-2">
                                        {[
                                            { label: 'Budget', range: '$0-10', min: 0, max: 10, color: 'bg-blue-500' },
                                            { label: 'Value', range: '$10-25', min: 10, max: 25, color: 'bg-brand-500' },
                                            { label: 'Mid', range: '$25-50', min: 25, max: 50, color: 'bg-yellow-500' },
                                            { label: 'High', range: '$50-100', min: 50, max: 100, color: 'bg-orange-500' },
                                            { label: 'Premium', range: '$100+', min: 100, max: Infinity, color: 'bg-red-500' },
                                        ].map(tier => {
                                            const count = cards.filter(c => {
                                                const price = c.floor_price || c.latest_price
                                                return price >= tier.min && price < tier.max
                                            }).length
                                            const pct = cards.length > 0 ? (count / cards.length) * 100 : 0
                                            return (
                                                <div key={tier.label} className="flex items-center gap-3">
                                                    <div className="w-16 text-xs text-muted-foreground">{tier.range}</div>
                                                    <div className="flex-1 h-6 bg-muted/30 rounded overflow-hidden relative">
                                                        <div
                                                            className={`h-full ${tier.color} transition-all duration-500`}
                                                            style={{ width: `${pct}%` }}
                                                        />
                                                        <div className="absolute inset-0 flex items-center px-2">
                                                            <span className="text-xs font-bold text-white drop-shadow-sm">{count} cards</span>
                                                        </div>
                                                    </div>
                                                    <div className="w-12 text-xs text-muted-foreground text-right">{pct.toFixed(0)}%</div>
                                                </div>
                                            )
                                        })}
                                    </div>
                                </div>

                                {/* Bottom Row: Liquid Budget + Premium */}
                                <div className="grid grid-cols-2 gap-4">
                                    {/* Liquid Budget Cards */}
                                    <div className="border rounded-lg p-3">
                                        <div className="flex items-center gap-2 mb-3">
                                            <DollarSign className="w-4 h-4 text-blue-400" />
                                            <span className="text-xs font-bold uppercase text-muted-foreground">Liquid Budget Cards</span>
                                        </div>
                                        <div className="text-[10px] text-muted-foreground mb-2">Under $25, high volume - easy to trade</div>
                                        <div className="space-y-1.5">
                                            {cards
                                                .filter(c => (c.floor_price || c.latest_price) < 25 && (c.floor_price || c.latest_price) > 0 && c.volume_30d >= 3)
                                                .sort((a, b) => b.volume_30d - a.volume_30d)
                                                .slice(0, 5)
                                                .map(card => (
                                                    <div
                                                        key={card.id}
                                                        className="flex items-center justify-between text-sm hover:bg-muted/50 p-1.5 rounded cursor-pointer"
                                                        onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: card.slug || String(card.id) } })}
                                                    >
                                                        <span className="truncate text-xs">{card.name}</span>
                                                        <div className="flex items-center gap-2 flex-shrink-0">
                                                            <span className="text-xs font-mono text-brand-400">${(card.floor_price || card.latest_price)?.toFixed(2)}</span>
                                                            <span className="text-[10px] text-muted-foreground">{card.volume_30d} sales</span>
                                                        </div>
                                                    </div>
                                                ))}
                                            {cards.filter(c => (c.floor_price || c.latest_price) < 25 && c.volume_30d >= 3).length === 0 && (
                                                <div className="text-center text-muted-foreground text-xs py-2">No liquid budget cards</div>
                                            )}
                                        </div>
                                    </div>

                                    {/* Premium Watchlist */}
                                    <div className="border rounded-lg p-3">
                                        <div className="flex items-center gap-2 mb-3">
                                            <Zap className="w-4 h-4 text-amber-400" />
                                            <span className="text-xs font-bold uppercase text-muted-foreground">Premium Watchlist</span>
                                        </div>
                                        <div className="text-[10px] text-muted-foreground mb-2">$100+ cards worth tracking</div>
                                        <div className="space-y-1.5">
                                            {cards
                                                .filter(c => (c.floor_price || c.latest_price) >= 100)
                                                .sort((a, b) => (b.floor_price || b.latest_price) - (a.floor_price || a.latest_price))
                                                .slice(0, 5)
                                                .map(card => (
                                                    <div
                                                        key={card.id}
                                                        className="flex items-center justify-between text-sm hover:bg-muted/50 p-1.5 rounded cursor-pointer"
                                                        onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: card.slug || String(card.id) } })}
                                                    >
                                                        <span className="truncate text-xs">{card.name}</span>
                                                        <div className="flex items-center gap-2 flex-shrink-0">
                                                            <span className="text-xs font-mono text-amber-400">${(card.floor_price || card.latest_price)?.toFixed(2)}</span>
                                                            {card.price_delta_24h !== 0 && (
                                                                <span className={clsx("text-[10px] font-mono", card.price_delta_24h > 0 ? "text-brand-400" : "text-red-400")}>
                                                                    {card.price_delta_24h > 0 ? '+' : ''}{card.price_delta_24h.toFixed(1)}%
                                                                </span>
                                                            )}
                                                        </div>
                                                    </div>
                                                ))}
                                            {cards.filter(c => (c.floor_price || c.latest_price) >= 100).length === 0 && (
                                                <div className="text-center text-muted-foreground text-xs py-2">No premium cards</div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Deals Tab - Active listings below floor price */}
                        {activeTab === 'deals' && (
                            <div className="p-4 flex flex-col h-full overflow-auto">
                                {/* Summary Stats Row */}
                                <div className="grid grid-cols-4 gap-3 mb-4">
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Deals Found</div>
                                        <div className="text-2xl font-bold font-mono text-brand-300">{dealListings?.length ?? 0}</div>
                                        <div className="text-[10px] text-muted-foreground">below floor price</div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Best Deal</div>
                                        <div className="text-2xl font-bold font-mono text-brand-300">
                                            {dealListings?.[0]?.dealPct ? `${dealListings[0].dealPct.toFixed(0)}%` : '-'}
                                        </div>
                                        <div className="text-[10px] text-muted-foreground">max discount</div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Avg Discount</div>
                                        <div className="text-2xl font-bold font-mono">
                                            {dealListings && dealListings.length > 0
                                                ? `${(dealListings.reduce((acc, l) => acc + l.dealPct, 0) / dealListings.length).toFixed(0)}%`
                                                : '-'}
                                        </div>
                                        <div className="text-[10px] text-muted-foreground">below floor</div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Total Savings</div>
                                        <div className="text-2xl font-bold font-mono text-brand-300">
                                            {dealListings && dealListings.length > 0
                                                ? `$${dealListings.reduce((acc, l) => acc + ((l.floor_price || 0) - l.price), 0).toFixed(0)}`
                                                : '-'}
                                        </div>
                                        <div className="text-[10px] text-muted-foreground">vs floor prices</div>
                                    </div>
                                </div>

                                {/* Deals Grid */}
                                <div className="flex-1">
                                    {dealsLoading ? (
                                        <div className="flex items-center justify-center h-64">
                                            <div className="text-sm text-muted-foreground animate-pulse">Finding deals...</div>
                                        </div>
                                    ) : !dealListings || dealListings.length === 0 ? (
                                        <div className="flex flex-col items-center justify-center h-64 text-center border border-dashed border-border rounded-lg">
                                            <Tag className="w-12 h-12 text-muted-foreground/30 mb-3" />
                                            <div className="text-lg font-bold text-muted-foreground mb-1">No Deals Right Now</div>
                                            <div className="text-sm text-muted-foreground max-w-md">
                                                All active listings are at or above their floor price. Check back later or try a different time period.
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                                            {dealListings.map((listing) => (
                                                <a
                                                    key={listing.id}
                                                    href={listing.url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    onClick={() => analytics.trackExternalLinkClick(listing.platform, listing.card_id, listing.title)}
                                                    className="border border-border rounded-lg p-3 hover:border-brand-300 hover:bg-brand-300/5 transition-all group"
                                                >
                                                    {/* Deal Badge + Listing Type */}
                                                    <div className="flex items-center justify-between mb-2">
                                                        <span className="px-2 py-1 bg-brand-300/20 text-brand-300 text-xs font-bold rounded">
                                                            {listing.dealPct.toFixed(0)}% OFF
                                                        </span>
                                                        <div className="flex items-center gap-1.5">
                                                            {/* Listing Type Badge */}
                                                            {listing.listingFormat === 'auction' ? (
                                                                <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-400 text-[10px] font-bold rounded uppercase">
                                                                    Auction{listing.bidCount > 0 && ` (${listing.bidCount})`}
                                                                </span>
                                                            ) : listing.listingFormat === 'best_offer' ? (
                                                                <span className="px-1.5 py-0.5 bg-blue-500/20 text-blue-400 text-[10px] font-bold rounded uppercase">
                                                                    Best Offer
                                                                </span>
                                                            ) : listing.listingFormat === 'buy_it_now' ? (
                                                                <span className="px-1.5 py-0.5 bg-emerald-500/20 text-emerald-400 text-[10px] font-bold rounded uppercase">
                                                                    Buy Now
                                                                </span>
                                                            ) : (
                                                                <span className="px-1.5 py-0.5 bg-gray-500/20 text-gray-400 text-[10px] font-bold rounded uppercase">
                                                                    Listing
                                                                </span>
                                                            )}
                                                            <span className="text-[10px] text-muted-foreground uppercase font-medium">{listing.platform}</span>
                                                        </div>
                                                    </div>
                                                    {/* Freshness indicator - warn if not seen recently */}
                                                    {!listing.isFresh && listing.hoursSinceSeen != null && (
                                                        <div className="mb-2 px-2 py-1 bg-amber-500/10 border border-amber-500/30 rounded text-[10px] text-amber-400">
                                                            ⚠️ Last seen {Math.round(listing.hoursSinceSeen)}h ago — may have ended
                                                        </div>
                                                    )}

                                                    {/* Card Info */}
                                                    <div className="flex gap-3">
                                                        {listing.card_image_url ? (
                                                            <img
                                                                src={listing.card_image_url}
                                                                alt={listing.card_name}
                                                                loading="lazy"
                                                                className="w-14 h-20 object-cover rounded flex-shrink-0"
                                                            />
                                                        ) : (
                                                            <div className="w-14 h-20 bg-muted rounded flex-shrink-0 flex items-center justify-center">
                                                                <Tag className="w-6 h-6 text-muted-foreground/50" />
                                                            </div>
                                                        )}
                                                        <div className="flex-1 min-w-0">
                                                            <div className="font-bold text-sm truncate group-hover:text-brand-300 transition-colors">
                                                                {listing.card_name}
                                                            </div>
                                                            {listing.treatment && (
                                                                <div className="text-xs text-brand-300/70 mb-1">{listing.treatment}</div>
                                                            )}
                                                            {/* Pricing */}
                                                            <div className="mt-2">
                                                                <div className="text-xl font-bold font-mono text-brand-300">${listing.price.toFixed(2)}</div>
                                                                <div className="flex items-center gap-2 text-xs">
                                                                    <span className="font-mono text-muted-foreground line-through">${listing.floor_price?.toFixed(2)}</span>
                                                                    <span className="font-mono text-brand-300 font-medium">Save ${((listing.floor_price || 0) - listing.price).toFixed(2)}</span>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </a>
                                            ))}
                                        </div>
                                    )}
                                </div>

                                {/* Footer Note */}
                                <div className="mt-4 pt-3 border-t border-border text-center text-[10px] text-muted-foreground">
                                    Floor = avg of 4 lowest recent sales per card + treatment. Click any deal to buy on marketplace.
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Pagination Controls - only show for table tab */}
                    {activeTab === 'table' && (
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
                    )}
                </div>
            </div>
        </div>
    </div>
  )
}
