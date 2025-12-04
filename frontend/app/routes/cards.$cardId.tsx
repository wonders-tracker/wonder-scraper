import { createRoute, useParams } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../utils/auth'
import { Route as rootRoute } from './__root'
import { ArrowLeft, TrendingUp, Wallet, Filter, ChevronLeft, ChevronRight, X, ExternalLink } from 'lucide-react'
import { Link } from '@tanstack/react-router'
import { ColumnDef, flexRender, getCoreRowModel, useReactTable, getPaginationRowModel, getFilteredRowModel } from '@tanstack/react-table'
import { useMemo, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts'
import clsx from 'clsx'

type CardDetail = {
  id: number
  name: string
  set_name: string
  rarity_id: number
  rarity_name?: string
  latest_price?: number
  volume_24h?: number
  price_delta_24h?: number
  lowest_ask?: number
  inventory?: number
  max_price?: number // Added max_price type
  // Calculated fields for display
  market_cap?: number
}

type MarketPrice = {
    id: number
    price: number
    title: string
    sold_date: string
    listing_type: string
    treatment?: string
    bid_count?: number
    url?: string
    image_url?: string
    description?: string
}

export const Route = createRoute({
  getParentRoute: () => rootRoute,
  path: '/cards/$cardId',
  component: CardDetail,
})

function CardDetail() {
  const { cardId } = useParams({ from: Route.id })
  const queryClient = useQueryClient()
  const [treatmentFilter, setTreatmentFilter] = useState<string>('all')
  const [selectedListing, setSelectedListing] = useState<MarketPrice | null>(null)
  
  // Fetch Card Data
  const { data: card, isLoading: isLoadingCard } = useQuery({
    queryKey: ['card', cardId],
    queryFn: async () => {
      // First get card basic info
      const basic = await api.get(`cards/${cardId}`).json<CardDetail>()
      // Then get market snapshot
      try {
          const market = await api.get(`cards/${cardId}/market`).json<any>()
          return {
              ...basic,
              latest_price: market.avg_price,
              volume_24h: market.volume,
              lowest_ask: market.lowest_ask,
              inventory: market.inventory,
              max_price: market.max_price, // Added max_price for Highest Confirmed Sale
              market_cap: (market.avg_price || 0) * (market.volume || 0) // Rough estimate
          }
      } catch (e) {
          // If market data fails (404 or 401), return basic info
          return basic
      }
    }
  })

  // Fetch Sales History (sold + active listings) - fetch ALL for complete timeline
  const { data: history, isLoading: isLoadingHistory } = useQuery({
      queryKey: ['card-history', cardId],
      queryFn: async () => {
          try {
            // Fetch ALL sold listings for complete price history chart
            const soldData = await api.get(`cards/${cardId}/history?limit=1000`).json<MarketPrice[]>()
            const activeData = await api.get(`cards/${cardId}/active?limit=100`).json<MarketPrice[]>().catch(() => [])
            // Combine and sort by date (active listings first, then sold by date)
            return [...activeData, ...soldData]
          } catch (e) {
              return []
          }
      }
  })

  // Mutation to Track Card
  const trackMutation = useMutation({
      mutationFn: async () => {
          await api.post('portfolio/', {
              json: {
                  card_id: parseInt(cardId),
                  quantity: 1,
                  purchase_price: card?.latest_price || 0
              }
          })
      },
      onSuccess: () => {
          alert('Card added to your Portfolio!')
          queryClient.invalidateQueries({ queryKey: ['portfolio'] })
      },
      onError: () => {
          alert('Failed to add card. You might already have it or need to log in.')
      }
  })

  const columns = useMemo<ColumnDef<MarketPrice>[]>(() => [
      {
          accessorKey: 'sold_date',
          header: 'Date',
          cell: ({ row }) => row.original.sold_date ? new Date(row.original.sold_date).toLocaleDateString() : 'N/A'
      },
      {
          accessorKey: 'price',
          header: () => <div className="text-right">Price</div>,
          cell: ({ row }) => <div className="text-right font-mono font-bold">${row.original.price.toFixed(2)}</div>
      },
      {
          accessorKey: 'treatment',
          header: 'Treatment',
          cell: ({ row }) => (
              <span className={clsx("px-1.5 py-0.5 rounded text-[10px] uppercase font-bold border", 
                  row.original.treatment?.includes("Foil") ? "border-purple-800 bg-purple-900/20 text-purple-500" : 
                  row.original.treatment?.includes("Serialized") ? "border-amber-800 bg-amber-900/20 text-amber-500" :
                  "border-zinc-800 bg-zinc-900/20 text-zinc-500"
              )}>
                  {row.original.treatment || 'Classic Paper'}
              </span>
          )
      },
      {
          accessorKey: 'title',
          header: 'Listing Title',
          cell: ({ row }) => <div className="truncate max-w-xl text-xs text-muted-foreground" title={row.original.title}>{row.original.title}</div>
      },
      {
          accessorKey: 'listing_type',
          header: () => <div className="text-right text-xs">Type</div>,
          cell: ({ row }) => (
            <div className="text-right">
                <span className={clsx("px-1.5 py-0.5 rounded text-[10px] uppercase font-bold border", 
                    row.original.listing_type === 'sold' ? "border-green-800 bg-green-900/20 text-green-500" : "border-blue-800 bg-blue-900/20 text-blue-500")}>
                    {row.original.listing_type || 'Sold'}
                </span>
            </div>
          )
      }
  ], [])

  const filteredData = useMemo(() => {
      if (!history) return []
      if (treatmentFilter === 'all') return history
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

  // Prepare Chart Data - Individual points per sale for scatter plot
  const chartData = useMemo(() => {
      if (!history) return []
      
      // 1. Filter valid data first
      const validHistory = history.filter(h => {
          const validPrice = h.price !== undefined && h.price !== null && !isNaN(Number(h.price)) && Number(h.price) > 0
          const validDate = h.sold_date && !isNaN(new Date(h.sold_date).getTime())
          return validPrice && validDate
      })

      // 2. Sort by date
      const sorted = validHistory.sort((a, b) => 
          new Date(a.sold_date).getTime() - new Date(b.sold_date).getTime()
      )
      
      // 3. Map to chart format with sequential index
      return sorted.map((h, index) => {
          const saleDate = new Date(h.sold_date)
          return {
              id: `${h.id}-${index}`, // Unique ID for Recharts
              date: saleDate.toLocaleDateString(),
              timestamp: saleDate.getTime(),
              x: index,  // Sequential index for X-axis
              price: Number(h.price), // Ensure numeric price
            treatment: h.treatment || 'Classic Paper',
              title: h.title,
              listing_type: h.listing_type
          }
      })
  }, [history])
  
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
      {/* Dynamic OG Tags */}
      <head>
        <title>{card.name} | WondersTracker</title>
        <meta name="description" content={`Track ${card.name} market prices and sales history. Current price: $${card.latest_price?.toFixed(2) || '---'}. Live data for Wonders of the First TCG.`} />

        {/* Open Graph */}
        <meta property="og:title" content={`${card.name} - $${card.latest_price?.toFixed(2) || '---'}`} />
        <meta property="og:description" content={`Track ${card.name} prices and market trends on WondersTracker`} />
        <meta property="og:image" content={`https://wonderstrader.com/api/og/${card.id}`} />
        <meta property="og:type" content="website" />
        <meta property="og:url" content={`https://wonderstrader.com/cards/${card.id}`} />

        {/* Twitter Card */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content={`${card.name} - $${card.latest_price?.toFixed(2) || '---'}`} />
        <meta name="twitter:description" content={`Track ${card.name} prices and market trends`} />
        <meta name="twitter:image" content={`https://wonderstrader.com/api/og/${card.id}`} />
      </head>

      <div className="min-h-screen bg-background text-foreground font-mono flex flex-col">
        <div className="flex-1 p-6">
            <div className="max-w-7xl mx-auto">
                {/* Navigation */}
                <div className="flex justify-between items-center mb-8">
                    <Link to="/" className="flex items-center gap-2 text-xs uppercase text-muted-foreground hover:text-primary transition-colors border border-transparent hover:border-border rounded px-3 py-1">
                        <ArrowLeft className="w-3 h-3" /> Dashboard
                    </Link>
                    
                    <button 
                        onClick={() => trackMutation.mutate()}
                        disabled={trackMutation.isPending}
                        className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded text-xs uppercase font-bold hover:bg-primary/90 transition-colors disabled:opacity-50"
                    >
                        <Wallet className="w-3 h-3" />
                        {trackMutation.isPending ? 'Tracking...' : 'Track in Portfolio'}
                    </button>
                </div>
                
                {/* Header Section */}
                <div className="mb-10 border-b border-border pb-8">
                    <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                        <div>
                            <div className="flex items-center gap-3 mb-2">
                                <span className="bg-muted text-muted-foreground px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider">
                                    ID: {card.id.toString().padStart(4, '0')}
                                </span>
                                <span className="bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider border border-zinc-700">
                                    Rarity: {card.rarity_name || card.rarity_id}
                                </span>
                            </div>
                            <h1 className="text-4xl md:text-5xl font-black uppercase tracking-tighter mb-2">{card.name}</h1>
                            <div className="text-sm text-muted-foreground uppercase tracking-[0.2em] flex items-center gap-2">
                                <span className="w-2 h-2 bg-primary rounded-full"></span>
                                {card.set_name}
                            </div>
                        </div>
                        
                        <div className="flex gap-8 md:text-right">
                            <div>
                                <div className="text-[10px] text-muted-foreground uppercase mb-1 tracking-wider">Market Price</div>
                                <div className="text-4xl font-mono font-bold text-emerald-500">
                                    ${(card.lowest_ask && card.lowest_ask > 0) ? card.lowest_ask.toFixed(2) : (card.latest_price?.toFixed(2) || '---')}
                                </div>
                            </div>
                            <div className="hidden md:block border-l border-border pl-8">
                                <div className="text-[10px] text-muted-foreground uppercase mb-1 tracking-wider">24h Vol</div>
                                <div className="text-4xl font-mono font-bold">
                                    {(card.volume_24h || 0).toLocaleString()}
                                </div>
                            </div>
                            {/* Highest Confirmed Sale */}
                            <div className="hidden md:block border-l border-border pl-8">
                                <div className="text-[10px] text-muted-foreground uppercase mb-1 tracking-wider">Highest Sale</div>
                                <div className="text-4xl font-mono font-bold text-emerald-600">
                                    ${card.max_price ? card.max_price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '---'}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                     <div className="border border-border p-4 rounded bg-card/50 hover:bg-card transition-colors">
                        <div className="text-[10px] text-muted-foreground uppercase mb-2 flex items-center gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500"></div>
                            Lowest Ask
                        </div>
                        <div className="text-xl font-mono font-bold">{(card.lowest_ask && card.lowest_ask > 0) ? `$${card.lowest_ask.toFixed(2)}` : '---'}</div>
                    </div>
                     <div className="border border-border p-4 rounded bg-card/50 hover:bg-card transition-colors">
                        <div className="text-[10px] text-muted-foreground uppercase mb-2 flex items-center gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-blue-500"></div>
                            Active Listings
                        </div>
                        <div className="text-xl font-mono font-bold">{(card.inventory || 0).toLocaleString()}</div>
                    </div>
                     <div className="border border-border p-4 rounded bg-card/50 hover:bg-card transition-colors">
                        <div className="text-[10px] text-muted-foreground uppercase mb-2 flex items-center gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-amber-500"></div>
                            Vol (USD)
                        </div>
                        <div className="text-xl font-mono font-bold">${((card.volume_24h || 0) * (card.latest_price || 0)).toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})}</div>
                    </div>
                     <div className="border border-border p-4 rounded bg-card/50 hover:bg-card transition-colors">
                        <div className="text-[10px] text-muted-foreground uppercase mb-2 flex items-center gap-2">
                            <TrendingUp className="w-3 h-3" />
                            Trend (24h)
                        </div>
                        <div className={clsx("text-xl font-mono font-bold", (card.price_delta_24h || 0) >= 0 ? "text-emerald-500" : "text-red-500")}>
                            {(card.price_delta_24h || 0) > 0 ? '+' : ''}{(card.price_delta_24h || 0).toFixed(2)}%
                        </div>
                    </div>
                </div>

                {/* Stacked Layout: Chart then Table */}
                <div className="space-y-8">
                    
                    {/* Chart Section (Full Width) */}
                    <div>
                        <div className="border border-border rounded bg-card p-1 h-[400px]">
                            <div className="h-full w-full bg-muted/10 rounded flex flex-col">
                                <div className="p-4 border-b border-border/50">
                                    <h3 className="text-xs font-bold uppercase tracking-widest">Price Action</h3>
                                </div>
                                <div className="flex-1 p-6 relative">
                                    {chartData.length > 1 ? (
                                        <ResponsiveContainer width="100%" height="100%">
                                            <LineChart data={chartData} margin={{ top: 20, right: 60, bottom: 30, left: 20 }}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="#333" strokeOpacity={0.3} vertical={false} horizontal={true} />
                                                <XAxis
                                                    dataKey="timestamp"
                                                    name="Date"
                                                    type="number"
                                                    domain={['dataMin', 'dataMax']}
                                                    scale="time"
                                                    tick={{fill: '#666', fontSize: 10}}
                                                    axisLine={false}
                                                    tickLine={false}
                                                    tickFormatter={(ts) => new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                                                />
                                                <YAxis
                                                    dataKey="price"
                                                    name="Price"
                                                    domain={[(dataMin: number) => Math.floor(dataMin * 0.9), (dataMax: number) => Math.ceil(dataMax * 1.1)]}
                                                    orientation="right"
                                                    tick={{fill: '#888', fontSize: 11, fontFamily: 'monospace'}}
                                                    axisLine={false}
                                                    tickLine={false}
                                                    tickFormatter={(val) => `$${val.toFixed(0)}`}
                                                    width={60}
                                                />
                                                <Tooltip
                                                    content={({ payload }) => {
                                                        if (!payload || !payload[0]) return null
                                                        const data = payload[0].payload
                                                        if (!data) return null

                                                        return (
                                                            <div style={{backgroundColor: '#1a1a1a', border: '1px solid #333', padding: '12px', borderRadius: '8px', boxShadow: '0 4px 12px rgba(0,0,0,0.5)'}}>
                                                                <div style={{color: '#10b981', fontWeight: 'bold', marginBottom: '8px', fontSize: '16px'}}>${typeof data.price === 'number' ? data.price.toFixed(2) : data.price}</div>
                                                                <div style={{color: '#a3a3a3', fontSize: '11px', marginBottom: '4px', textTransform: 'uppercase', fontWeight: '600'}}>{data.treatment}</div>
                                                                <div style={{color: '#666', fontSize: '10px', marginBottom: '6px'}}>{data.date}</div>
                                                                {data.listing_type === 'active' && (
                                                                    <div style={{color: '#3b82f6', fontSize: '9px', textTransform: 'uppercase', fontWeight: 'bold', marginTop: '6px', paddingTop: '6px', borderTop: '1px solid #333'}}>ACTIVE LISTING</div>
                                                                )}
                                                            </div>
                                                        )
                                                    }}
                                                    cursor={{strokeDasharray: '3 3', stroke: '#666'}}
                                                />

                                                {/* Main price line */}
                                                <Line
                                                    type="monotone"
                                                    dataKey="price"
                                                    stroke="#10b981"
                                                    strokeWidth={3}
                                                    dot={{ fill: '#10b981', strokeWidth: 2, r: 4 }}
                                                    activeDot={{ r: 6, fill: '#10b981' }}
                                                />
                                            </LineChart>
                                        </ResponsiveContainer>
                                    ) : (
                                        <div className="h-full flex items-center justify-center text-xs text-muted-foreground uppercase">
                                            Not enough data points for chart
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Sales History Table (Full Width) */}
                    <div>
                        <div className="border border-border rounded bg-card overflow-hidden">
                            <div className="px-6 py-4 border-b border-border flex justify-between items-center bg-muted/20">
                                <div className="flex items-center gap-4">
                                    <h3 className="text-xs font-bold uppercase tracking-widest flex items-center gap-2">
                                        Recent Sales Activity
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
                                            <option value="all">All Treatments</option>
                                            {uniqueTreatments.map(t => (
                                                <option key={t} value={t}>{t}</option>
                                            ))}
                                        </select>
                                    </div>
                                </div>
                            </div>
                            
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm text-left">
                                    <thead className="text-xs uppercase bg-white text-black sticky top-0">
                                        {table.getHeaderGroups().map(headerGroup => (
                                            <tr key={headerGroup.id}>
                                                {headerGroup.headers.map(header => (
                                                    <th key={header.id} className="px-6 py-3 font-medium border-b border-border">
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
                                                        <td key={cell.id} className="px-6 py-3 whitespace-nowrap">
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
                                                Showing <span className="font-medium">{table.getState().pagination.pageIndex * table.getState().pagination.pageSize + 1}</span> to <span className="font-medium">{Math.min((table.getState().pagination.pageIndex + 1) * table.getState().pagination.pageSize, filteredData.length)}</span> of <span className="font-medium">{filteredData.length}</span> results
                                            </p>
                                        </div>
                                        <div>
                                            <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">
                                                <button
                                                    onClick={() => table.previousPage()}
                                                    disabled={!table.getCanPreviousPage()}
                                                    className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-border bg-card text-sm font-medium text-muted-foreground hover:bg-muted/50 disabled:opacity-50"
                                                >
                                                    <span className="sr-only">Previous</span>
                                                    <ChevronLeft className="h-4 w-4" aria-hidden="true" />
                                                </button>
                                                {Array.from({ length: Math.min(5, table.getPageCount()) }, (_, i) => {
                                                    // Logic to show sliding window of pages could be added here, simplistic for now
                                                    const pageIdx = i; 
                                                    return (
                                                        <button
                                                            key={pageIdx}
                                                            onClick={() => table.setPageIndex(pageIdx)}
                                                            aria-current={table.getState().pagination.pageIndex === pageIdx ? 'page' : undefined}
                                                            className={clsx(
                                                                "relative inline-flex items-center px-4 py-2 border text-xs font-medium",
                                                                table.getState().pagination.pageIndex === pageIdx
                                                                    ? "z-10 bg-primary text-primary-foreground border-primary"
                                                                    : "bg-card border-border text-muted-foreground hover:bg-muted/50"
                                                            )}
                                                        >
                                                            {pageIdx + 1}
                                                        </button>
                                                    )
                                                })}
                                                <button
                                                    onClick={() => table.nextPage()}
                                                    disabled={!table.getCanNextPage()}
                                                    className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-border bg-card text-sm font-medium text-muted-foreground hover:bg-muted/50 disabled:opacity-50"
                                                >
                                                    <span className="sr-only">Next</span>
                                                    <ChevronRight className="h-4 w-4" aria-hidden="true" />
                                                </button>
                                            </nav>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
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
                            <span className="text-emerald-500 font-bold">WondersTrader.com</span>
                        </p>
                    </div>
                    <div className="flex gap-3">
                        <Link
                            to="/"
                            className="px-6 py-3 bg-emerald-500 hover:bg-emerald-600 text-black font-bold uppercase text-sm rounded transition-colors"
                        >
                            View Market
                        </Link>
                        <Link
                            to="/portfolio"
                            className="px-6 py-3 border border-emerald-500 text-emerald-500 hover:bg-emerald-500/10 font-bold uppercase text-sm rounded transition-colors"
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
                                    onError={(e) => (e.currentTarget.style.display = 'none')}
                                />
                            </div>
                        )}

                        <div>
                            <div className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest mb-2">Listing Title</div>
                            <div className="text-sm font-medium leading-relaxed border border-border p-3 rounded bg-muted/20">
                                {selectedListing.title}
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <div className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest mb-1">Price</div>
                                <div className="text-2xl font-mono font-bold text-emerald-500">
                                    ${selectedListing.price.toFixed(2)}
                                </div>
                            </div>
                            <div>
                                <div className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest mb-1">Date</div>
                                <div className="text-sm font-mono">
                                    {selectedListing.sold_date ? new Date(selectedListing.sold_date).toLocaleDateString() : 'N/A'}
                                </div>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <div className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest mb-1">Type</div>
                                <span className={clsx("px-2 py-1 rounded text-[10px] uppercase font-bold border inline-block", 
                                    selectedListing.listing_type === 'sold' ? "border-green-800 bg-green-900/20 text-green-500" : "border-blue-800 bg-blue-900/20 text-blue-500")}>
                                    {selectedListing.listing_type || 'Sold'}
                                </span>
                            </div>
                            <div>
                                <div className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest mb-1">Treatment</div>
                                <span className={clsx("px-2 py-1 rounded text-[10px] uppercase font-bold border inline-block", 
                                    selectedListing.treatment?.includes("Foil") ? "border-purple-800 bg-purple-900/20 text-purple-500" : 
                                    selectedListing.treatment?.includes("Serialized") ? "border-amber-800 bg-amber-900/20 text-amber-500" :
                                    "border-zinc-800 bg-zinc-900/20 text-zinc-500"
                                )}>
                                    {selectedListing.treatment || 'Classic Paper'}
                                </span>
                            </div>
                        </div>

                        <div>
                             <div className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest mb-1">Bid Count</div>
                             <div className="text-sm font-mono font-bold">
                                {selectedListing.bid_count !== undefined ? selectedListing.bid_count : '0'}
                             </div>
                        </div>

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
                                    <span className="text-xs font-bold">{card?.set_name}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-xs text-muted-foreground uppercase">Rarity</span>
                                    <span className="text-xs font-bold">{card?.rarity_name || card?.rarity_id}</span>
                                </div>
                            </div>
                        </div>
                        
                        {/* Listing Info */}
                        {/* Only show placeholder specs if we don't have real data, for now we removed the hardcoded box specs to avoid confusion */}
                        <div className="pt-6 border-t border-border">
                            <h3 className="text-xs font-bold uppercase tracking-widest mb-4 flex items-center gap-2">
                                <div className="w-1 h-4 bg-blue-500 rounded-full"></div>
                                Listing Info
                            </h3>
                            <div className="bg-muted/10 rounded p-4 border border-border space-y-3 text-xs">
                                {selectedListing.description ? (
                                    <p className="text-muted-foreground italic">"{selectedListing.description}"</p>
                                ) : (
                                    <p className="text-muted-foreground">No additional details provided for this listing.</p>
                                )}
                                <div className="pt-2 border-t border-border/50 mt-2">
                                    <div className="text-foreground font-bold mb-1">Source</div>
                                    <p className="text-muted-foreground">Verified Market Data aggregated from {selectedListing.url?.includes('ebay') ? 'eBay' : 'External Market'}.</p>
                                </div>
                            </div>
                        </div>

                        {/* External Link */}
                        <div className="pt-4">
                            <a 
                                href={selectedListing.url || `https://www.ebay.com/sch/i.html?_nkw=${encodeURIComponent(selectedListing.title)}&LH_Complete=1`} 
                                target="_blank" 
                                rel="noopener noreferrer" 
                                className="flex items-center justify-center gap-2 w-full border border-border hover:bg-muted/50 text-xs uppercase font-bold py-3 rounded transition-colors"
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
      </div>
    </>
  )
}