import { createRoute, useParams } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../utils/auth'
import { Route as rootRoute } from './__root'
import { ArrowLeft, TrendingUp, Wallet, Filter, ChevronLeft, ChevronRight } from 'lucide-react'
import { Link } from '@tanstack/react-router'
import { ColumnDef, flexRender, getCoreRowModel, useReactTable, getPaginationRowModel, getFilteredRowModel } from '@tanstack/react-table'
import { useMemo, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import clsx from 'clsx'

type CardDetail = {
  id: number
  name: string
  set_name: string
  rarity_id: number
  latest_price?: number
  volume_24h?: number
  price_delta_24h?: number
  lowest_ask?: number
  inventory?: number
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
              market_cap: (market.avg_price || 0) * (market.volume || 0) // Rough estimate
          }
      } catch (e) {
          // If market data fails (404 or 401), return basic info
          return basic
      }
    }
  })

  // Fetch Sales History
  const { data: history, isLoading: isLoadingHistory } = useQuery({
      queryKey: ['card-history', cardId],
      queryFn: async () => {
          try {
            // Fetching 100 items to allow for some client-side filtering/pagination
            // In a real app with massive data, this should be server-side filtered/paginated.
            const data = await api.get(`cards/${cardId}/history?limit=100`).json<MarketPrice[]>()
            return data
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

  // Prepare Chart Data (Sort by date ascending for line chart)
  const chartData = useMemo(() => {
      if (!history) return []
      return [...history]
        .filter(h => h.price > 0 && h.sold_date)
        .sort((a, b) => new Date(a.sold_date).getTime() - new Date(b.sold_date).getTime())
        .map(h => ({
            date: new Date(h.sold_date).toLocaleDateString(),
            price: h.price
        }))
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
                                    Rarity: {card.rarity_id}
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
                                    ${card.latest_price?.toFixed(2) || '---'}
                                </div>
                            </div>
                            <div className="hidden md:block border-l border-border pl-8">
                                <div className="text-[10px] text-muted-foreground uppercase mb-1 tracking-wider">24h Vol</div>
                                <div className="text-4xl font-mono font-bold">
                                    {card.volume_24h || 0}
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
                        <div className="text-xl font-mono font-bold">${card.lowest_ask?.toFixed(2) || '---'}</div>
                    </div>
                     <div className="border border-border p-4 rounded bg-card/50 hover:bg-card transition-colors">
                        <div className="text-[10px] text-muted-foreground uppercase mb-2 flex items-center gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-blue-500"></div>
                            Active Listings
                        </div>
                        <div className="text-xl font-mono font-bold">{card.inventory || 0}</div>
                    </div>
                     <div className="border border-border p-4 rounded bg-card/50 hover:bg-card transition-colors">
                        <div className="text-[10px] text-muted-foreground uppercase mb-2 flex items-center gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-amber-500"></div>
                            Vol (USD)
                        </div>
                        <div className="text-xl font-mono font-bold">${((card.volume_24h || 0) * (card.latest_price || 0)).toFixed(0)}</div>
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
                        <div className="border border-border rounded bg-card p-1 h-[300px]">
                            <div className="h-full w-full bg-muted/10 rounded flex flex-col">
                                <div className="p-4 border-b border-border/50">
                                    <h3 className="text-xs font-bold uppercase tracking-widest">Price Action</h3>
                                </div>
                                <div className="flex-1 p-2 relative">
                                    {chartData.length > 1 ? (
                                        <ResponsiveContainer width="100%" height="100%">
                                            <LineChart data={chartData}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                                                <XAxis dataKey="date" hide />
                                                <YAxis 
                                                    domain={['auto', 'auto']} 
                                                    orientation="right" 
                                                    tick={{fill: '#666', fontSize: 10, fontFamily: 'monospace'}}
                                                    axisLine={false}
                                                    tickLine={false}
                                                    tickFormatter={(val) => `$${val}`}
                                                />
                                                <Tooltip 
                                                    contentStyle={{backgroundColor: '#000', borderColor: '#333', fontFamily: 'monospace', fontSize: '12px'}}
                                                    itemStyle={{color: '#fff'}}
                                                    formatter={(value: number) => [`$${value.toFixed(2)}`, 'Price']}
                                                />
                                                <Line 
                                                    type="monotone" 
                                                    dataKey="price" 
                                                    stroke="#10b981" 
                                                    strokeWidth={2} 
                                                    dot={false} 
                                                    activeDot={{r: 4, fill: '#fff'}}
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
                                                <tr key={row.id} className="hover:bg-muted/30 transition-colors">
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

        {/* SEO Footer */}
        <footer className="border-t border-border py-8 mt-auto bg-muted/10">
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
    </div>
  )
}
