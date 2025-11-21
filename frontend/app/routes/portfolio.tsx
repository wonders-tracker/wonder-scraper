import { createRoute, Link } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../utils/auth'
import { Route as rootRoute } from './__root'
import { ArrowLeft, TrendingUp, Trash2, Search } from 'lucide-react'
import { ColumnDef, flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table'
import { useMemo } from 'react'
import clsx from 'clsx'

type PortfolioItem = {
    id: number
    card_id: number
    quantity: number
    purchase_price: number
    acquired_at: string
    card_name: string
    card_set: string
    current_market_price: number
    current_value: number
    gain_loss: number
    gain_loss_percent: number
}

export const Route = createRoute({
  getParentRoute: () => rootRoute,
  path: '/portfolio',
  component: Portfolio,
})

function Portfolio() {
  const queryClient = useQueryClient()

  // Fetch Portfolio Data
  const { data: portfolio, isLoading } = useQuery({
    queryKey: ['portfolio'],
    queryFn: async () => {
      return await api.get('portfolio/').json<PortfolioItem[]>()
    }
  })

  // Delete Mutation
  const deleteMutation = useMutation({
      mutationFn: async (itemId: number) => {
          await api.delete(`portfolio/${itemId}`)
      },
      onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ['portfolio'] })
      }
  })

  // Aggregate Stats
  const stats = useMemo(() => {
      if (!portfolio) return { totalValue: 0, totalCost: 0, totalGain: 0, totalGainPercent: 0, count: 0 }
      
      const totalValue = portfolio.reduce((acc, item) => acc + (item.current_value || 0), 0)
      const totalCost = portfolio.reduce((acc, item) => acc + (item.purchase_price * item.quantity), 0)
      const totalGain = totalValue - totalCost
      const totalGainPercent = totalCost > 0 ? (totalGain / totalCost) * 100 : 0
      const count = portfolio.reduce((acc, item) => acc + item.quantity, 0)
      
      return { totalValue, totalCost, totalGain, totalGainPercent, count }
  }, [portfolio])

  const columns = useMemo<ColumnDef<PortfolioItem>[]>(() => [
      {
          accessorKey: 'card_name',
          header: 'Card',
          cell: ({ row }) => (
              <div>
                  <Link to={`/cards/${row.original.card_id}`} className="font-bold hover:underline hover:text-primary">
                      {row.original.card_name}
                  </Link>
                  <div className="text-[10px] text-muted-foreground uppercase">{row.original.card_set}</div>
              </div>
          )
      },
      {
          accessorKey: 'quantity',
          header: () => <div className="text-right">Qty</div>,
          cell: ({ row }) => <div className="text-right">{row.original.quantity}</div>
      },
      {
          accessorKey: 'purchase_price',
          header: () => <div className="text-right">Avg Cost</div>,
          cell: ({ row }) => <div className="text-right text-muted-foreground">${row.original.purchase_price.toFixed(2)}</div>
      },
      {
          accessorKey: 'current_market_price',
          header: () => <div className="text-right">Market Price</div>,
          cell: ({ row }) => <div className="text-right font-mono">${row.original.current_market_price.toFixed(2)}</div>
      },
      {
          accessorKey: 'current_value',
          header: () => <div className="text-right">Value</div>,
          cell: ({ row }) => <div className="text-right font-mono font-bold">${row.original.current_value.toFixed(2)}</div>
      },
      {
          accessorKey: 'gain_loss',
          header: () => <div className="text-right">Gain/Loss</div>,
          cell: ({ row }) => {
              const val = row.original.gain_loss
              const pct = row.original.gain_loss_percent
              return (
                  <div className={clsx("text-right font-mono text-xs", val >= 0 ? "text-emerald-500" : "text-red-500")}>
                      {val >= 0 ? '+' : ''}{val.toFixed(2)} ({pct.toFixed(1)}%)
                  </div>
              )
          }
      },
      {
          id: 'actions',
          cell: ({ row }) => (
              <div className="text-right">
                  <button 
                    onClick={() => deleteMutation.mutate(row.original.id)}
                    className="text-muted-foreground hover:text-red-500 transition-colors"
                    title="Remove from Portfolio"
                  >
                      <Trash2 className="w-4 h-4" />
                  </button>
              </div>
          )
      }
  ], [])

  const table = useReactTable({
      data: portfolio || [],
      columns,
      getCoreRowModel: getCoreRowModel(),
  })

  if (isLoading) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-background text-foreground font-mono">
            <div className="text-center animate-pulse">
                <div className="text-xl uppercase tracking-widest mb-2">Loading Portfolio</div>
                <div className="text-xs text-muted-foreground">Calculating asset values...</div>
            </div>
        </div>
      )
  }

  return (
    <div className="p-6 min-h-screen bg-background text-foreground font-mono">
        <div className="max-w-7xl mx-auto">
            {/* Header */}
            <div className="mb-8 flex justify-between items-center">
                <div className="flex items-center gap-4">
                    <Link to="/" className="flex items-center justify-center w-8 h-8 border border-border rounded hover:bg-muted/50 transition-colors">
                        <ArrowLeft className="w-4 h-4 text-muted-foreground" />
                    </Link>
                    <h1 className="text-3xl font-bold uppercase tracking-tight">My Portfolio</h1>
                </div>
                <Link to="/" className="flex items-center gap-2 text-xs uppercase font-bold bg-primary text-primary-foreground px-4 py-2 rounded hover:bg-primary/90 transition-colors">
                    <Search className="w-3 h-3" /> Find Cards
                </Link>
            </div>

            {/* Portfolio Summary */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <div className="border border-border p-6 rounded-lg bg-card shadow-sm">
                    <div className="text-xs text-muted-foreground uppercase mb-2">Total Value</div>
                    <div className="text-3xl font-mono font-bold">${stats.totalValue.toFixed(2)}</div>
                </div>
                <div className="border border-border p-6 rounded-lg bg-card shadow-sm">
                    <div className="text-xs text-muted-foreground uppercase mb-2">Total Cost</div>
                    <div className="text-3xl font-mono text-muted-foreground">${stats.totalCost.toFixed(2)}</div>
                </div>
                <div className="border border-border p-6 rounded-lg bg-card shadow-sm">
                    <div className="text-xs text-muted-foreground uppercase mb-2">Total Return</div>
                    <div className={clsx("text-3xl font-mono font-bold", stats.totalGain >= 0 ? "text-emerald-500" : "text-red-500")}>
                        {stats.totalGain >= 0 ? '+' : ''}{stats.totalGain.toFixed(2)}
                    </div>
                    <div className={clsx("text-xs font-bold mt-1", stats.totalGain >= 0 ? "text-emerald-500" : "text-red-500")}>
                        {stats.totalGain >= 0 ? '+' : ''}{stats.totalGainPercent.toFixed(2)}% All Time
                    </div>
                </div>
                <div className="border border-border p-6 rounded-lg bg-card shadow-sm">
                    <div className="text-xs text-muted-foreground uppercase mb-2">Total Cards</div>
                    <div className="text-3xl font-mono">{stats.count}</div>
                </div>
            </div>

            {/* Holdings Table */}
            <div className="border border-border rounded-lg bg-card overflow-hidden">
                <div className="px-6 py-4 border-b border-border bg-muted/20">
                    <h3 className="text-sm font-bold uppercase tracking-widest">Holdings</h3>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="text-xs uppercase bg-muted/30 text-muted-foreground">
                            {table.getHeaderGroups().map(headerGroup => (
                                <tr key={headerGroup.id}>
                                    {headerGroup.headers.map(header => (
                                        <th key={header.id} className="px-6 py-3 font-medium">
                                            {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                                        </th>
                                    ))}
                                </tr>
                            ))}
                        </thead>
                        <tbody className="divide-y divide-border/50">
                            {portfolio && portfolio.length > 0 ? (
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
                                    <td colSpan={7} className="p-12 text-center text-muted-foreground">
                                        <div className="mb-4">Your portfolio is empty.</div>
                                        <Link to="/" className="text-primary hover:underline uppercase text-xs font-bold">
                                            Browse Market to Add Cards
                                        </Link>
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
  )
}

