import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { api, auth } from '../utils/auth'
import { analytics } from '~/services/analytics'
import { ArrowUp, ArrowDown, Activity, BarChart3, DollarSign, TableIcon, PieChartIcon, LineChart, Tag } from 'lucide-react'
import { Bar, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, CartesianGrid, Cell, ScatterChart, Scatter, ZAxis, ComposedChart, Line, ReferenceLine } from 'recharts'
import { Tooltip } from '../components/ui/tooltip'
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
    market_cap: number
    deal_rating: number
    treatment?: string
}

// Raw API response type
type MarketOverviewItem = {
    id: number
    slug?: string
    name: string
    set_name: string
    rarity_id: number
    latest_price?: number
    avg_price?: number
    floor_price?: number
    volume_period?: number
    volume_change?: number
    price_delta_period?: number
    deal_rating?: number
    treatment?: string
}

type AnalyticsTab = 'table' | 'volume' | 'marketcap' | 'sentiment' | 'prices' | 'deals'

function MarketAnalysis() {
  const navigate = useNavigate()
  const [sorting, setSorting] = useState<SortingState>([{ id: 'volume_30d', desc: true }])
  const [timeFrame, setTimeFrame] = useState('30d')
  const [hideLowSignal, setHideLowSignal] = useState(true)
  const [activeTab, setActiveTab] = useState<AnalyticsTab>('table')

  // Check if user is logged in
  const isLoggedIn = auth.isAuthenticated()

  // Track market page view
  useEffect(() => {
    analytics.trackMarketPageView()
  }, [])

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

  const { data: rawCards, isLoading } = useQuery({
    queryKey: ['market-overview', timeFrame],
    queryFn: async () => {
        const data = await api.get(`market/overview?time_period=${timeFrame}`).json<MarketOverviewItem[]>()
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
                market_cap: (c.floor_price ?? c.latest_price ?? 0) * volumePeriod
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
      const sortedByVolume = [...cards].sort((a, b) => b.volume_30d - a.volume_30d)
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
      marketCap: c.market_cap,
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

  // Chart Data - Market Cap Treemap (visual representation of market share)
  const marketCapChartData = useMemo(() => {
    const sorted = [...cards]
      .filter(c => c.market_cap > 0)
      .sort((a, b) => b.market_cap - a.market_cap)
      .slice(0, 20)

    const totalCap = sorted.reduce((acc, c) => acc + c.market_cap, 0)
    return sorted.map(c => ({
      name: c.name.length > 12 ? c.name.slice(0, 12) + '...' : c.name,
      fullName: c.name,
      slug: c.slug || c.id,
      marketCap: c.market_cap,
      volume: c.volume_30d,
      floor: c.floor_price || c.latest_price,
      share: totalCap > 0 ? ((c.market_cap / totalCap) * 100).toFixed(1) : '0'
    }))
  }, [cards])

  // Market cap summary stats
  const marketCapStats = useMemo(() => {
    const withCap = cards.filter(c => c.market_cap > 0)
    const total = withCap.reduce((acc, c) => acc + c.market_cap, 0)
    const top5 = marketCapChartData.slice(0, 5).reduce((acc, c) => acc + c.marketCap, 0)
    const avgFloor = withCap.length > 0
      ? withCap.reduce((acc, c) => acc + (c.floor_price || c.latest_price), 0) / withCap.length
      : 0
    return {
      total,
      top5Pct: total > 0 ? ((top5 / total) * 100).toFixed(0) : '0',
      avgFloor: avgFloor.toFixed(2)
    }
  }, [cards, marketCapChartData])

  // Chart Data - Price Distribution with volume weight
  const priceDistributionData = useMemo(() => {
    const withPrices = cards.filter(c => c.floor_price && c.floor_price > 0)
    if (withPrices.length === 0) return []

    const buckets = [
      { range: '$0-10', min: 0, max: 10, count: 0, volume: 0, totalValue: 0, cards: [] as MarketCard[] },
      { range: '$10-25', min: 10, max: 25, count: 0, volume: 0, totalValue: 0, cards: [] as MarketCard[] },
      { range: '$25-50', min: 25, max: 50, count: 0, volume: 0, totalValue: 0, cards: [] as MarketCard[] },
      { range: '$50-100', min: 50, max: 100, count: 0, volume: 0, totalValue: 0, cards: [] as MarketCard[] },
      { range: '$100-250', min: 100, max: 250, count: 0, volume: 0, totalValue: 0, cards: [] as MarketCard[] },
      { range: '$250+', min: 250, max: Infinity, count: 0, volume: 0, totalValue: 0, cards: [] as MarketCard[] },
    ]

    withPrices.forEach(c => {
      const price = c.floor_price!
      const bucket = buckets.find(b => price >= b.min && price < b.max)
      if (bucket) {
        bucket.count++
        bucket.volume += c.volume_30d
        bucket.totalValue += c.market_cap
        bucket.cards.push(c)
      }
    })

    return buckets.filter(b => b.count > 0).map(b => ({
      ...b,
      avgPrice: b.count > 0 ? (b.cards.reduce((acc, c) => acc + (c.floor_price || 0), 0) / b.count).toFixed(2) : '0'
    }))
  }, [cards])

  // Chart Data - Deal Rating Scatter (volume vs deal rating)
  const dealScatterData = useMemo(() => {
    return cards
      .filter(c => c.volume_30d > 0 && c.deal_rating !== 0)
      .map(c => ({
        name: c.name,
        slug: c.slug || c.id,
        volume: c.volume_30d,
        dealRating: c.deal_rating,
        floor: c.floor_price || c.latest_price,
        marketCap: c.market_cap,
        isGoodDeal: c.deal_rating < 0
      }))
  }, [cards])

  // Deal distribution buckets for the bar portion (reserved for future visualization)
  const _dealDistributionData = useMemo(() => {
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
          accessorKey: 'market_cap',
          header: ({ column }) => (
              <Tooltip content="Market cap = floor price × volume">
                  <div className="flex items-center justify-end gap-1 cursor-pointer select-none" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>
                      MKT CAP {column.getIsSorted() && <ArrowUp className={clsx("w-3 h-3 transition-transform", column.getIsSorted() === 'desc' && "rotate-180")} />}
                  </div>
              </Tooltip>
          ),
          cell: ({ row }) => {
              const cap = row.original.market_cap
              if (cap === 0 || !cap) return <div className="text-right font-mono text-muted-foreground">-</div>
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

                {/* Market Cap */}
                <div className="bg-card border border-border p-4 rounded hover:border-primary/50 transition-colors">
                    <div className="text-[10px] uppercase text-muted-foreground font-medium mb-2">Market Cap</div>
                    <div className="text-3xl font-mono font-bold text-brand-300">
                        {metrics.totalCap >= 1000000
                            ? `$${(metrics.totalCap / 1000000).toFixed(2)}M`
                            : `$${(metrics.totalCap / 1000).toFixed(1)}k`}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">floor × volume</div>
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
                            { id: 'marketcap' as AnalyticsTab, label: 'Market Cap', icon: DollarSign },
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

                        {/* Volume Chart Tab - Volume Profile Style */}
                        {activeTab === 'volume' && (
                            <div className="p-4 flex flex-col h-full">
                                {/* Summary Stats Row */}
                                <div className="grid grid-cols-4 gap-3 mb-4">
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Total Volume</div>
                                        <div className="text-xl font-bold font-mono">{volumeStats.total.toLocaleString()}</div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Avg per Asset</div>
                                        <div className="text-xl font-bold font-mono">{volumeStats.avg}</div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Active Assets</div>
                                        <div className="text-xl font-bold font-mono">{volumeStats.activeAssets}</div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Top 5 Share</div>
                                        <div className="text-xl font-bold font-mono text-primary">{volumeStats.top5Pct}%</div>
                                    </div>
                                </div>

                                {/* Volume Profile Chart - Horizontal bars with price overlay */}
                                <div className="flex-1 min-h-[280px]">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <ComposedChart data={volumeChartData} layout="vertical" margin={{ left: 10, right: 60 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
                                            <XAxis type="number" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
                                            <YAxis dataKey="name" type="category" width={100} tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
                                            <RechartsTooltip
                                                contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '6px', fontSize: '12px' }}
                                                content={({ active, payload }) => {
                                                    if (active && payload && payload.length) {
                                                        const data = payload[0].payload
                                                        return (
                                                            <div className="bg-card border border-border rounded-md p-2 text-xs shadow-lg">
                                                                <div className="font-bold mb-1">{data.fullName}</div>
                                                                <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                                                                    <span className="text-muted-foreground">Volume:</span>
                                                                    <span className="font-mono font-bold">{data.volume}</span>
                                                                    <span className="text-muted-foreground">Floor:</span>
                                                                    <span className="font-mono text-brand-300">${data.floor?.toFixed(2)}</span>
                                                                    <span className="text-muted-foreground">Mkt Cap:</span>
                                                                    <span className="font-mono">${data.marketCap?.toLocaleString()}</span>
                                                                    <span className="text-muted-foreground">Trend:</span>
                                                                    <span className={clsx("font-mono", data.trend > 0 ? "text-brand-300" : data.trend < 0 ? "text-red-500" : "")}>
                                                                        {data.trend > 0 ? '+' : ''}{data.trend?.toFixed(1)}%
                                                                    </span>
                                                                </div>
                                                            </div>
                                                        )
                                                    }
                                                    return null
                                                }}
                                            />
                                            {/* Volume bars with gradient based on trend */}
                                            <Bar dataKey="volume" radius={[0, 4, 4, 0]}>
                                                {volumeChartData.map((entry, index) => (
                                                    <Cell
                                                        key={`cell-${index}`}
                                                        fill={entry.trend > 0 ? '#7dd3a8' : entry.trend < 0 ? '#ef4444' : 'hsl(var(--muted-foreground))'}
                                                        fillOpacity={0.3 + (entry.pctOfMax / 100) * 0.7}
                                                    />
                                                ))}
                                            </Bar>
                                        </ComposedChart>
                                    </ResponsiveContainer>
                                </div>

                                {/* Supporting Table - Top 5 */}
                                <div className="mt-4 border-t border-border pt-3">
                                    <div className="text-[10px] uppercase text-muted-foreground mb-2">Volume Leaders</div>
                                    <div className="grid grid-cols-5 gap-2 text-xs">
                                        {volumeChartData.slice(0, 5).map((item, i) => (
                                            <div key={i} className="bg-muted/20 rounded p-2 hover:bg-muted/40 cursor-pointer transition-colors" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: String(item.slug) } })}>
                                                <div className="font-bold truncate">{item.fullName}</div>
                                                <div className="font-mono text-primary">{item.volume} sales</div>
                                                <div className="text-muted-foreground">${item.floor?.toFixed(2)}</div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Market Cap Chart Tab */}
                        {activeTab === 'marketcap' && (
                            <div className="p-4 flex flex-col h-full">
                                {/* Summary Stats Row */}
                                <div className="grid grid-cols-4 gap-3 mb-4">
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Total Market Cap</div>
                                        <div className="text-xl font-bold font-mono text-brand-300">
                                            ${marketCapStats.total >= 1000000
                                                ? `${(marketCapStats.total / 1000000).toFixed(2)}M`
                                                : `${(marketCapStats.total / 1000).toFixed(1)}k`}
                                        </div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Top 5 Dominance</div>
                                        <div className="text-xl font-bold font-mono">{marketCapStats.top5Pct}%</div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Avg Floor Price</div>
                                        <div className="text-xl font-bold font-mono">${marketCapStats.avgFloor}</div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Assets w/ Cap</div>
                                        <div className="text-xl font-bold font-mono">{marketCapChartData.length}</div>
                                    </div>
                                </div>

                                {/* Market Cap Chart with share percentages */}
                                <div className="flex-1 min-h-[280px]">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <ComposedChart data={marketCapChartData} layout="vertical" margin={{ left: 10, right: 60 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
                                            <XAxis type="number" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
                                            <YAxis dataKey="name" type="category" width={100} tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
                                            <RechartsTooltip
                                                content={({ active, payload }) => {
                                                    if (active && payload && payload.length) {
                                                        const data = payload[0].payload
                                                        return (
                                                            <div className="bg-card border border-border rounded-md p-2 text-xs shadow-lg">
                                                                <div className="font-bold mb-1">{data.fullName}</div>
                                                                <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                                                                    <span className="text-muted-foreground">Market Cap:</span>
                                                                    <span className="font-mono font-bold text-brand-300">${data.marketCap?.toLocaleString()}</span>
                                                                    <span className="text-muted-foreground">Share:</span>
                                                                    <span className="font-mono">{data.share}%</span>
                                                                    <span className="text-muted-foreground">Floor:</span>
                                                                    <span className="font-mono">${data.floor?.toFixed(2)}</span>
                                                                    <span className="text-muted-foreground">Volume:</span>
                                                                    <span className="font-mono">{data.volume}</span>
                                                                </div>
                                                            </div>
                                                        )
                                                    }
                                                    return null
                                                }}
                                            />
                                            <Bar dataKey="marketCap" radius={[0, 4, 4, 0]}>
                                                {marketCapChartData.map((entry, index) => (
                                                    <Cell
                                                        key={`cell-${index}`}
                                                        fill="#7dd3a8"
                                                        fillOpacity={0.3 + ((20 - index) / 20) * 0.7}
                                                    />
                                                ))}
                                            </Bar>
                                        </ComposedChart>
                                    </ResponsiveContainer>
                                </div>

                                {/* Market Cap Leaders */}
                                <div className="mt-4 border-t border-border pt-3">
                                    <div className="text-[10px] uppercase text-muted-foreground mb-2">Market Cap Leaders</div>
                                    <div className="grid grid-cols-5 gap-2 text-xs">
                                        {marketCapChartData.slice(0, 5).map((item, i) => (
                                            <div key={i} className="bg-muted/20 rounded p-2 hover:bg-muted/40 cursor-pointer transition-colors" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: String(item.slug) } })}>
                                                <div className="font-bold truncate">{item.fullName}</div>
                                                <div className="font-mono text-brand-300">${(item.marketCap / 1000).toFixed(1)}k</div>
                                                <div className="text-muted-foreground">{item.share}% share</div>
                                            </div>
                                        ))}
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

                                {/* Sentiment Distribution Chart */}
                                <div className="flex-1 min-h-[280px]">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <ComposedChart data={sentimentChartData} margin={{ left: 10, right: 30, bottom: 20 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                                            <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} interval={0} />
                                            <YAxis tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
                                            <ReferenceLine y={0} stroke="hsl(var(--border))" />
                                            <RechartsTooltip
                                                content={({ active, payload }) => {
                                                    if (active && payload && payload.length) {
                                                        const data = payload[0].payload
                                                        return (
                                                            <div className="bg-card border border-border rounded-md p-2 text-xs shadow-lg">
                                                                <div className="font-bold mb-1">{data.name}</div>
                                                                <div className="text-muted-foreground">{data.value} assets</div>
                                                                {data.topCard && (
                                                                    <div className="mt-1 pt-1 border-t border-border">
                                                                        <span className="text-muted-foreground">Top: </span>
                                                                        <span className="font-bold">{data.topCard.name}</span>
                                                                        <span className={clsx("ml-1 font-mono", data.topCard.price_delta_24h > 0 ? "text-brand-300" : "text-red-500")}>
                                                                            {data.topCard.price_delta_24h > 0 ? '+' : ''}{data.topCard.price_delta_24h?.toFixed(1)}%
                                                                        </span>
                                                                    </div>
                                                                )}
                                                            </div>
                                                        )
                                                    }
                                                    return null
                                                }}
                                            />
                                            <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                                                {sentimentChartData.map((entry, index) => (
                                                    <Cell key={`cell-${index}`} fill={entry.fill} />
                                                ))}
                                            </Bar>
                                        </ComposedChart>
                                    </ResponsiveContainer>
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

                        {/* Prices Distribution Tab */}
                        {activeTab === 'prices' && (
                            <div className="p-4 flex flex-col h-full">
                                {/* Summary Stats Row */}
                                <div className="grid grid-cols-4 gap-3 mb-4">
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Total Assets</div>
                                        <div className="text-xl font-bold font-mono">{priceDistributionData.reduce((acc, b) => acc + b.count, 0)}</div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Under $25</div>
                                        <div className="text-xl font-bold font-mono text-brand-300">
                                            {priceDistributionData.filter(b => b.max <= 25).reduce((acc, b) => acc + b.count, 0)}
                                        </div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">$25 - $100</div>
                                        <div className="text-xl font-bold font-mono">
                                            {priceDistributionData.filter(b => b.min >= 25 && b.max <= 100).reduce((acc, b) => acc + b.count, 0)}
                                        </div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Premium ($100+)</div>
                                        <div className="text-xl font-bold font-mono text-amber-500">
                                            {priceDistributionData.filter(b => b.min >= 100).reduce((acc, b) => acc + b.count, 0)}
                                        </div>
                                    </div>
                                </div>

                                {/* Stacked bar showing volume and count per price tier */}
                                <div className="flex-1 min-h-[280px]">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <ComposedChart data={priceDistributionData} margin={{ left: 10, right: 30, bottom: 10 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                                            <XAxis dataKey="range" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
                                            <YAxis yAxisId="left" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
                                            <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} tickFormatter={(v) => `${v}`} />
                                            <RechartsTooltip
                                                content={({ active, payload }) => {
                                                    if (active && payload && payload.length) {
                                                        const data = payload[0].payload
                                                        return (
                                                            <div className="bg-card border border-border rounded-md p-2 text-xs shadow-lg">
                                                                <div className="font-bold mb-1">{data.range}</div>
                                                                <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                                                                    <span className="text-muted-foreground">Assets:</span>
                                                                    <span className="font-mono font-bold">{data.count}</span>
                                                                    <span className="text-muted-foreground">Volume:</span>
                                                                    <span className="font-mono">{data.volume}</span>
                                                                    <span className="text-muted-foreground">Total Value:</span>
                                                                    <span className="font-mono text-brand-300">${data.totalValue?.toLocaleString()}</span>
                                                                    <span className="text-muted-foreground">Avg Price:</span>
                                                                    <span className="font-mono">${data.avgPrice}</span>
                                                                </div>
                                                            </div>
                                                        )
                                                    }
                                                    return null
                                                }}
                                            />
                                            <Bar yAxisId="left" dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} fillOpacity={0.8} />
                                            <Line yAxisId="right" type="monotone" dataKey="volume" stroke="#7dd3a8" strokeWidth={2} dot={{ fill: '#7dd3a8', r: 4 }} />
                                        </ComposedChart>
                                    </ResponsiveContainer>
                                </div>

                                {/* Price tier breakdown table */}
                                <div className="mt-4 border-t border-border pt-3">
                                    <div className="text-[10px] uppercase text-muted-foreground mb-2">Price Tier Details</div>
                                    <div className="grid grid-cols-6 gap-2 text-xs">
                                        {priceDistributionData.map((bucket, i) => (
                                            <div key={i} className="bg-muted/20 rounded p-2 text-center">
                                                <div className="font-bold">{bucket.range}</div>
                                                <div className="font-mono text-primary">{bucket.count} cards</div>
                                                <div className="text-muted-foreground">{bucket.volume} sold</div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Deals Distribution Tab - Scatter plot with deal opportunities */}
                        {activeTab === 'deals' && (
                            <div className="p-4 flex flex-col h-full">
                                {/* Summary Stats Row */}
                                <div className="grid grid-cols-4 gap-3 mb-4">
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Good Deals</div>
                                        <div className="text-xl font-bold font-mono text-brand-300">{dealStats.goodDeals}</div>
                                        <div className="text-[10px] text-muted-foreground">10%+ under avg</div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Fair Priced</div>
                                        <div className="text-xl font-bold font-mono">{dealStats.fairPriced}</div>
                                        <div className="text-[10px] text-muted-foreground">within ±10%</div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Overpriced</div>
                                        <div className="text-xl font-bold font-mono text-amber-500">{dealStats.overpriced}</div>
                                        <div className="text-[10px] text-muted-foreground">10%+ over avg</div>
                                    </div>
                                    <div className="bg-muted/30 rounded p-3">
                                        <div className="text-[10px] uppercase text-muted-foreground">Avg Deal Rating</div>
                                        <div className={clsx("text-xl font-bold font-mono", parseFloat(dealStats.avgDeal) < 0 ? "text-brand-300" : parseFloat(dealStats.avgDeal) > 0 ? "text-amber-500" : "")}>
                                            {parseFloat(dealStats.avgDeal) > 0 ? '+' : ''}{dealStats.avgDeal}%
                                        </div>
                                    </div>
                                </div>

                                {/* Scatter plot: Volume vs Deal Rating */}
                                <div className="flex-1 min-h-[280px]">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <ScatterChart margin={{ left: 10, right: 30, bottom: 10 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                                            <XAxis type="number" dataKey="dealRating" name="Deal Rating" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} tickFormatter={(v) => `${v}%`} domain={[-50, 50]} />
                                            <YAxis type="number" dataKey="volume" name="Volume" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
                                            <ZAxis type="number" dataKey="floor" range={[50, 400]} />
                                            <ReferenceLine x={0} stroke="hsl(var(--border))" strokeWidth={2} />
                                            <RechartsTooltip
                                                content={({ active, payload }) => {
                                                    if (active && payload && payload.length) {
                                                        const data = payload[0].payload
                                                        return (
                                                            <div className="bg-card border border-border rounded-md p-2 text-xs shadow-lg">
                                                                <div className="font-bold mb-1">{data.name}</div>
                                                                <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                                                                    <span className="text-muted-foreground">Deal Rating:</span>
                                                                    <span className={clsx("font-mono font-bold", data.dealRating < 0 ? "text-brand-300" : "text-amber-500")}>
                                                                        {data.dealRating > 0 ? '+' : ''}{data.dealRating?.toFixed(1)}%
                                                                    </span>
                                                                    <span className="text-muted-foreground">Volume:</span>
                                                                    <span className="font-mono">{data.volume}</span>
                                                                    <span className="text-muted-foreground">Floor:</span>
                                                                    <span className="font-mono">${data.floor?.toFixed(2)}</span>
                                                                </div>
                                                            </div>
                                                        )
                                                    }
                                                    return null
                                                }}
                                            />
                                            <Scatter data={dealScatterData} shape="circle">
                                                {dealScatterData.map((entry, index) => (
                                                    <Cell
                                                        key={`cell-${index}`}
                                                        fill={entry.isGoodDeal ? '#7dd3a8' : '#f59e0b'}
                                                        fillOpacity={0.7}
                                                    />
                                                ))}
                                            </Scatter>
                                        </ScatterChart>
                                    </ResponsiveContainer>
                                </div>

                                {/* Best Deals Table */}
                                <div className="mt-4 border-t border-border pt-3 grid grid-cols-2 gap-4">
                                    <div>
                                        <div className="text-[10px] uppercase text-brand-300 mb-2">Best Deals (Under Avg)</div>
                                        <div className="space-y-1">
                                            {dealScatterData
                                                .filter(d => d.dealRating < 0)
                                                .sort((a, b) => a.dealRating - b.dealRating)
                                                .slice(0, 4)
                                                .map((deal, i) => (
                                                    <div key={i} className="flex items-center justify-between text-xs bg-brand-300/10 rounded px-2 py-1 cursor-pointer hover:bg-brand-300/20" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: String(deal.slug) } })}>
                                                        <span className="truncate flex-1">{deal.name}</span>
                                                        <span className="font-mono text-brand-300 ml-2">{deal.dealRating.toFixed(0)}%</span>
                                                        <span className="font-mono text-muted-foreground ml-2">${deal.floor?.toFixed(2)}</span>
                                                    </div>
                                                ))}
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-[10px] uppercase text-amber-500 mb-2">Premium Priced (Over Avg)</div>
                                        <div className="space-y-1">
                                            {dealScatterData
                                                .filter(d => d.dealRating > 0)
                                                .sort((a, b) => b.dealRating - a.dealRating)
                                                .slice(0, 4)
                                                .map((deal, i) => (
                                                    <div key={i} className="flex items-center justify-between text-xs bg-amber-500/10 rounded px-2 py-1 cursor-pointer hover:bg-amber-500/20" onClick={() => navigate({ to: '/cards/$cardId', params: { cardId: String(deal.slug) } })}>
                                                        <span className="truncate flex-1">{deal.name}</span>
                                                        <span className="font-mono text-amber-500 ml-2">+{deal.dealRating.toFixed(0)}%</span>
                                                        <span className="font-mono text-muted-foreground ml-2">${deal.floor?.toFixed(2)}</span>
                                                    </div>
                                                ))}
                                        </div>
                                    </div>
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
