/**
 * Market Analytics Page - Redesigned minimal version
 *
 * Features:
 * - Clean data table with sorting
 * - Deals tab for active listings below floor
 * - Collapsible market info (gainers/losers/treatment floors)
 * - Time period filter
 */

import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { api } from '../utils/auth'
import { analytics } from '~/services/analytics'
import { useState, useMemo, useEffect } from 'react'
import { ChevronDown, ChevronUp, ArrowUp, TableIcon, Tag } from 'lucide-react'
import { cn } from '@/lib/utils'
import { SimpleDropdown } from '../components/ui/dropdown'
import { useCurrentUser } from '../context/UserContext'
import { LoginUpsellOverlay } from '../components/LoginUpsellOverlay'
import { slugify } from '@/lib/formatters'
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
  getSortedRowModel,
  SortingState,
  getPaginationRowModel,
} from '@tanstack/react-table'

// Components
import { CompactStats, TopMovers, TreatmentFloors, DealCard } from '../components/market'

// Types
type MarketSearchParams = {
  tab?: 'table' | 'deals'
  time?: string
}

export const Route = createFileRoute('/market')({
  component: MarketPage,
  validateSearch: (search: Record<string, unknown>): MarketSearchParams => ({
    tab: ['table', 'deals'].includes(search.tab as string)
      ? (search.tab as 'table' | 'deals')
      : undefined,
    time: typeof search.time === 'string' ? search.time : undefined,
  }),
})

type MarketCard = {
  id: number
  slug?: string
  name: string
  set_name: string
  latest_price: number
  floor_price?: number
  volume_30d: number
  price_delta_24h: number
  dollar_volume: number
  deal_rating: number
}

type DealListing = {
  id: number
  card_id: number
  card_name: string
  card_slug: string
  card_image_url: string | null
  price: number
  floor_price: number | null
  platform: string
  treatment: string | null
  url: string
  listing_format: 'auction' | 'buy_it_now' | 'best_offer' | null
  bid_count: number | null
  scraped_at: string | null
}

function MarketPage() {
  const navigate = useNavigate()
  const searchParams = Route.useSearch()
  const { user } = useCurrentUser()
  const isLoggedIn = !!user

  // State
  const [activeTab, setActiveTab] = useState<'table' | 'deals'>(searchParams.tab || 'table')
  const [timeFrame, setTimeFrame] = useState(searchParams.time || '30d')
  const [sorting, setSorting] = useState<SortingState>([{ id: 'volume_30d', desc: true }])
  const [showMarketInfo, setShowMarketInfo] = useState(false)

  // Sync tab with URL
  useEffect(() => {
    if (searchParams.tab && searchParams.tab !== activeTab) {
      setActiveTab(searchParams.tab)
    }
  }, [searchParams.tab])

  // Track page view
  useEffect(() => {
    analytics.trackMarketPageView()
  }, [])

  // Fetch market overview data
  const { data: rawCards, isLoading } = useQuery({
    queryKey: ['market-overview', timeFrame],
    queryFn: async () => {
      const data = await api.get(`market/overview?time_period=${timeFrame}`).json<any[]>()
      return data.map((c) => ({
        ...c,
        latest_price: c.latest_price ?? 0,
        floor_price: c.floor_price ?? null,
        volume_30d: c.volume_period ?? 0,
        price_delta_24h: Math.max(-100, Math.min(100, c.price_delta_period ?? 0)),
        deal_rating: c.deal_rating ?? 0,
        dollar_volume: c.dollar_volume ?? 0,
      })) as MarketCard[]
    },
    staleTime: 5 * 60 * 1000,
  })

  // Fetch treatment floors
  const { data: treatments } = useQuery({
    queryKey: ['treatments'],
    queryFn: () => api.get('market/treatments').json<{ name: string; min_price: number; count: number }[]>(),
    staleTime: 10 * 60 * 1000,
  })

  // Fetch deals (only when deals tab is active)
  const { data: dealsData, isLoading: dealsLoading } = useQuery({
    queryKey: ['market-deals'],
    queryFn: async () => {
      const data = await api
        .get('market/listings?listing_type=active&time_period=7d&sort_by=price&sort_order=asc&limit=200')
        .json<{ items: DealListing[] }>()

      const now = Date.now()
      return data.items
        .filter((l) => l.floor_price && l.price < l.floor_price)
        .map((l) => {
          const hoursSinceSeen = l.scraped_at
            ? (now - new Date(l.scraped_at).getTime()) / (1000 * 60 * 60)
            : 0
          const isAuction = l.listing_format === 'auction' || (l.bid_count ?? 0) > 0
          return {
            ...l,
            dealPct: l.floor_price ? ((l.floor_price - l.price) / l.floor_price) * 100 : 0,
            isAuction,
            isStale: l.scraped_at ? hoursSinceSeen > 6 : false,
          }
        })
        .sort((a, b) => b.dealPct - a.dealPct)
    },
    staleTime: 2 * 60 * 1000,
    enabled: activeTab === 'deals',
  })

  // Filter to cards with activity
  const cards = useMemo(() => {
    if (!rawCards) return []
    return rawCards.filter((c) => c.volume_30d > 0)
  }, [rawCards])

  // Compute stats
  const stats = useMemo(() => {
    const totalSales = cards.reduce((acc, c) => acc + c.volume_30d, 0)
    const dollarVolume = cards.reduce((acc, c) => acc + c.dollar_volume, 0)
    const dealCount = dealsData?.filter((d) => !d.isAuction).length ?? 0
    return { totalSales, dollarVolume, dealCount }
  }, [cards, dealsData])

  // Top gainers/losers
  const topGainers = useMemo(
    () =>
      [...cards]
        .filter((c) => c.price_delta_24h > 0)
        .sort((a, b) => b.price_delta_24h - a.price_delta_24h)
        .slice(0, 5)
        .map((c) => ({ id: c.id, slug: c.slug, name: c.name, price_delta: c.price_delta_24h })),
    [cards]
  )

  const topLosers = useMemo(
    () =>
      [...cards]
        .filter((c) => c.price_delta_24h < 0)
        .sort((a, b) => a.price_delta_24h - b.price_delta_24h)
        .slice(0, 5)
        .map((c) => ({ id: c.id, slug: c.slug, name: c.name, price_delta: c.price_delta_24h })),
    [cards]
  )

  // Table columns
  const columns = useMemo<ColumnDef<MarketCard>[]>(
    () => [
      {
        accessorKey: 'name',
        header: ({ column }) => (
          <button
            className="flex items-center gap-1"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Name
            {column.getIsSorted() && (
              <ArrowUp className={cn('w-3 h-3', column.getIsSorted() === 'desc' && 'rotate-180')} />
            )}
          </button>
        ),
        cell: ({ row }) => (
          <Link
            to="/cards/$cardId"
            params={{ cardId: row.original.slug || slugify(row.original.name) }}
            className="hover:text-brand-300 transition-colors"
          >
            <div className="font-medium">{row.original.name}</div>
            <div className="text-xs text-muted-foreground">{row.original.set_name}</div>
          </Link>
        ),
      },
      {
        accessorKey: 'floor_price',
        header: ({ column }) => (
          <button
            className="flex items-center gap-1 ml-auto"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Floor
            {column.getIsSorted() && (
              <ArrowUp className={cn('w-3 h-3', column.getIsSorted() === 'desc' && 'rotate-180')} />
            )}
          </button>
        ),
        cell: ({ row }) => {
          const price = row.original.floor_price || row.original.latest_price
          return (
            <div className="text-right font-mono font-medium">
              {price ? `$${price.toFixed(2)}` : '—'}
            </div>
          )
        },
      },
      {
        accessorKey: 'price_delta_24h',
        header: ({ column }) => (
          <button
            className="flex items-center gap-1 ml-auto"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Trend
            {column.getIsSorted() && (
              <ArrowUp className={cn('w-3 h-3', column.getIsSorted() === 'desc' && 'rotate-180')} />
            )}
          </button>
        ),
        cell: ({ row }) => {
          const delta = row.original.price_delta_24h
          if (delta === 0) return <div className="text-right text-muted-foreground">—</div>
          return (
            <div
              className={cn(
                'text-right font-mono font-medium',
                delta > 0 ? 'text-emerald-500' : 'text-red-500'
              )}
            >
              {delta > 0 ? '+' : ''}
              {delta.toFixed(1)}%
            </div>
          )
        },
      },
      {
        accessorKey: 'volume_30d',
        header: ({ column }) => (
          <button
            className="flex items-center gap-1 ml-auto"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Vol
            {column.getIsSorted() && (
              <ArrowUp className={cn('w-3 h-3', column.getIsSorted() === 'desc' && 'rotate-180')} />
            )}
          </button>
        ),
        cell: ({ row }) => <div className="text-right font-mono">{row.original.volume_30d}</div>,
      },
      {
        accessorKey: 'dollar_volume',
        header: ({ column }) => (
          <button
            className="flex items-center gap-1 ml-auto"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            $ Vol
            {column.getIsSorted() && (
              <ArrowUp className={cn('w-3 h-3', column.getIsSorted() === 'desc' && 'rotate-180')} />
            )}
          </button>
        ),
        cell: ({ row }) => {
          const vol = row.original.dollar_volume
          if (!vol) return <div className="text-right text-muted-foreground">—</div>
          const formatted =
            vol >= 1000 ? `$${(vol / 1000).toFixed(1)}k` : `$${vol.toFixed(0)}`
          return <div className="text-right font-mono text-muted-foreground">{formatted}</div>
        },
      },
      {
        accessorKey: 'deal_rating',
        header: ({ column }) => (
          <button
            className="flex items-center gap-1 ml-auto"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Deal
            {column.getIsSorted() && (
              <ArrowUp className={cn('w-3 h-3', column.getIsSorted() === 'desc' && 'rotate-180')} />
            )}
          </button>
        ),
        cell: ({ row }) => {
          const rating = row.original.deal_rating
          if (rating === 0) return <div className="text-right text-muted-foreground">—</div>
          const isGood = rating < 0
          return (
            <div className="flex justify-end">
              <span
                className={cn(
                  'px-1.5 py-0.5 rounded text-[10px] uppercase font-semibold',
                  isGood
                    ? 'bg-emerald-500/20 text-emerald-400'
                    : 'bg-amber-500/20 text-amber-400'
                )}
              >
                {Math.abs(rating).toFixed(0)}% {isGood ? 'under' : 'over'}
              </span>
            </div>
          )
        },
      },
    ],
    []
  )

  const table = useReactTable({
    data: cards,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    onSortingChange: setSorting,
    state: { sorting },
    initialState: {
      pagination: { pageSize: 50 },
    },
  })

  // Split deals into buy now and auctions
  const buyNowDeals = dealsData?.filter((d) => !d.isAuction).slice(0, 24) ?? []
  const auctionDeals = dealsData?.filter((d) => d.isAuction).slice(0, 12) ?? []

  // Loading state
  if (isLoading && !rawCards) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="text-lg font-medium mb-2">Loading market data...</div>
          <div className="text-sm text-muted-foreground">Analyzing trends</div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Market Analytics</h1>
          <p className="text-sm text-muted-foreground">{cards.length} cards with activity</p>
        </div>
        <SimpleDropdown
          value={timeFrame}
          onChange={(v) => setTimeFrame(v)}
          options={[
            { value: '7d', label: '7 Days' },
            { value: '30d', label: '30 Days' },
            { value: '90d', label: '90 Days' },
            { value: 'all', label: 'All Time' },
          ]}
          size="sm"
          triggerClassName="w-[100px]"
        />
      </div>

      {/* Compact Stats */}
      <CompactStats
        totalSales={stats.totalSales}
        dollarVolume={stats.dollarVolume}
        dealCount={stats.dealCount}
        className="mb-4"
      />

      {/* Collapsible Market Info */}
      <div className="mb-4">
        <button
          onClick={() => setShowMarketInfo(!showMarketInfo)}
          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-2"
        >
          {showMarketInfo ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          Market Info
        </button>
        {showMarketInfo && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <TopMovers gainers={topGainers} losers={topLosers} className="md:col-span-2" />
            <TreatmentFloors treatments={treatments ?? []} />
          </div>
        )}
      </div>

      {/* Tab Navigation */}
      <div className="flex items-center gap-1 border-b border-border mb-4">
        <button
          onClick={() => setActiveTab('table')}
          className={cn(
            'flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
            activeTab === 'table'
              ? 'border-brand-500 text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          )}
        >
          <TableIcon className="w-4 h-4" />
          Table
        </button>
        <button
          onClick={() => setActiveTab('deals')}
          className={cn(
            'flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
            activeTab === 'deals'
              ? 'border-brand-500 text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          )}
        >
          <Tag className="w-4 h-4" />
          Deals
          {stats.dealCount > 0 && (
            <span className="text-xs bg-emerald-500/20 text-emerald-400 px-1.5 py-0.5 rounded">
              {stats.dealCount}
            </span>
          )}
        </button>
      </div>

      {/* Tab Content */}
      <div className="relative">
        {/* Auth gate */}
        {!isLoggedIn && (
          <LoginUpsellOverlay
            title="Unlock Market Analytics"
            description="Sign in to access detailed market data, sorting, and live deals."
          />
        )}

        {/* Table Tab */}
        {activeTab === 'table' && (
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/30 border-b border-border">
                  {table.getHeaderGroups().map((headerGroup) => (
                    <tr key={headerGroup.id}>
                      {headerGroup.headers.map((header) => (
                        <th
                          key={header.id}
                          className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider"
                        >
                          {header.isPlaceholder
                            ? null
                            : flexRender(header.column.columnDef.header, header.getContext())}
                        </th>
                      ))}
                    </tr>
                  ))}
                </thead>
                <tbody className="divide-y divide-border/50">
                  {table.getRowModel().rows.map((row) => (
                    <tr key={row.id} className="hover:bg-muted/30 transition-colors">
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="px-4 py-3">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between px-4 py-3 border-t border-border bg-muted/20">
              <div className="text-sm text-muted-foreground">
                Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => table.previousPage()}
                  disabled={!table.getCanPreviousPage()}
                  className="px-3 py-1 text-sm border border-border rounded hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <button
                  onClick={() => table.nextPage()}
                  disabled={!table.getCanNextPage()}
                  className="px-3 py-1 text-sm border border-border rounded hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Deals Tab */}
        {activeTab === 'deals' && (
          <div className="space-y-6">
            {dealsLoading ? (
              <div className="text-center py-12 text-muted-foreground">Loading deals...</div>
            ) : (
              <>
                {/* Buy Now Deals */}
                {buyNowDeals.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold mb-3">
                      Buy Now Deals
                      <span className="ml-2 text-xs text-muted-foreground font-normal">
                        {buyNowDeals.length} available
                      </span>
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4">
                      {buyNowDeals.map((deal) => (
                        <DealCard
                          key={deal.id}
                          cardName={deal.card_name}
                          cardImageUrl={deal.card_image_url}
                          treatment={deal.treatment}
                          price={deal.price}
                          floorPrice={deal.floor_price!}
                          dealPercent={deal.dealPct}
                          platform={deal.platform}
                          listingFormat={deal.listing_format}
                          isStale={deal.isStale}
                          url={deal.url}
                          onLinkClick={() =>
                            analytics.trackExternalLinkClick(deal.platform, deal.card_id, deal.card_name)
                          }
                        />
                      ))}
                    </div>
                  </div>
                )}

                {/* Auctions */}
                {auctionDeals.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold mb-3">
                      Active Auctions
                      <span className="ml-2 text-xs text-muted-foreground font-normal">
                        {auctionDeals.length} available
                      </span>
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4">
                      {auctionDeals.map((deal) => (
                        <DealCard
                          key={deal.id}
                          cardName={deal.card_name}
                          cardImageUrl={deal.card_image_url}
                          treatment={deal.treatment}
                          price={deal.price}
                          floorPrice={deal.floor_price!}
                          dealPercent={deal.dealPct}
                          platform={deal.platform}
                          listingFormat={deal.listing_format}
                          bidCount={deal.bid_count ?? 0}
                          isStale={deal.isStale}
                          url={deal.url}
                          onLinkClick={() =>
                            analytics.trackExternalLinkClick(deal.platform, deal.card_id, deal.card_name)
                          }
                        />
                      ))}
                    </div>
                  </div>
                )}

                {/* Empty state */}
                {buyNowDeals.length === 0 && auctionDeals.length === 0 && (
                  <div className="text-center py-12">
                    <Tag className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                    <h3 className="text-lg font-medium mb-2">No deals found</h3>
                    <p className="text-sm text-muted-foreground">
                      Check back later for listings below floor price
                    </p>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
