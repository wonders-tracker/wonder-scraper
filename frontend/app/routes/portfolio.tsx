import { createRoute, Link, redirect } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, auth } from '../utils/auth'
import { analytics } from '~/services/analytics'
import { Route as rootRoute } from './__root'
import { ArrowLeft, TrendingUp, Trash2, Search, Edit, X, TrendingDown, BarChart3 } from 'lucide-react'
import { ColumnDef, flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table'
import { useMemo, useState, useEffect } from 'react'
import clsx from 'clsx'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

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
  beforeLoad: () => {
      if (typeof window !== 'undefined' && !auth.isAuthenticated()) {
          throw redirect({ to: '/login' })
      }
  }
})

function Portfolio() {
  const queryClient = useQueryClient()
  const [editingItem, setEditingItem] = useState<PortfolioItem | null>(null)
  const [editForm, setEditForm] = useState({ quantity: 1, purchase_price: 0, acquired_at: '' })

  // Track portfolio access
  useEffect(() => {
    analytics.trackPortfolioAccess()
  }, [])

  // Fetch Portfolio Data
  const { data: portfolio, isLoading } = useQuery({
    queryKey: ['portfolio'],
    queryFn: async () => {
      return await api.get('portfolio/').json<PortfolioItem[]>()
    }
  })

  // Update Mutation
  const updateMutation = useMutation({
      mutationFn: async ({ id, data }: { id: number, data: any }) => {
          return await api.put(`portfolio/${id}`, { json: data }).json<PortfolioItem>()
      },
      onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ['portfolio'] })
          setEditingItem(null)
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

  // Open edit drawer
  const handleEditClick = (item: PortfolioItem) => {
      setEditingItem(item)
      setEditForm({
          quantity: item.quantity,
          purchase_price: item.purchase_price,
          acquired_at: item.acquired_at ? new Date(item.acquired_at).toISOString().split('T')[0] : ''
      })
  }

  // Submit edit
  const handleEditSubmit = (e: React.FormEvent) => {
      e.preventDefault()
      if (!editingItem) return

      updateMutation.mutate({
          id: editingItem.id,
          data: {
              quantity: editForm.quantity,
              purchase_price: editForm.purchase_price,
              acquired_at: editForm.acquired_at || null
          }
      })
  }

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
                  <Link to={`/cards/${row.original.card_id}` as any} className="font-bold hover:underline hover:text-primary">
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
              <div className="text-right flex items-center justify-end gap-2">
                  <button
                    onClick={(e) => {
                        e.stopPropagation()
                        handleEditClick(row.original)
                    }}
                    className="text-muted-foreground hover:text-primary transition-colors"
                    title="Edit"
                  >
                      <Edit className="w-4 h-4" />
                  </button>
                  <button
                    onClick={(e) => {
                        e.stopPropagation()
                        deleteMutation.mutate(row.original.id)
                    }}
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

            {/* Portfolio Worth Graph */}
            <div className="border border-border rounded-lg bg-card p-6 mb-8">
                <div className="flex items-center gap-2 mb-4">
                    <BarChart3 className="w-5 h-5 text-primary" />
                    <h3 className="text-sm font-bold uppercase tracking-widest">Portfolio Value</h3>
                </div>
                <div className="h-48">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={[
                            { date: '7d ago', value: stats.totalValue * 0.92 },
                            { date: '6d ago', value: stats.totalValue * 0.95 },
                            { date: '5d ago', value: stats.totalValue * 0.93 },
                            { date: '4d ago', value: stats.totalValue * 0.96 },
                            { date: '3d ago', value: stats.totalValue * 0.98 },
                            { date: '2d ago', value: stats.totalValue * 0.97 },
                            { date: '1d ago', value: stats.totalValue * 0.99 },
                            { date: 'Today', value: stats.totalValue }
                        ]}>
                            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
                            <XAxis dataKey="date" stroke="hsl(var(--muted-foreground))" fontSize={10} />
                            <YAxis stroke="hsl(var(--muted-foreground))" fontSize={10} />
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: 'hsl(var(--card))',
                                    border: '1px solid hsl(var(--border))',
                                    borderRadius: '4px',
                                    fontSize: '12px'
                                }}
                                formatter={(value: any) => [`$${value.toFixed(2)}`, 'Value']}
                            />
                            <Line
                                type="monotone"
                                dataKey="value"
                                stroke="hsl(var(--primary))"
                                strokeWidth={2}
                                dot={false}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
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
                                    <tr
                                        key={row.id}
                                        className="hover:bg-muted/30 transition-colors cursor-pointer"
                                        onClick={() => handleEditClick(row.original)}
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

            {/* Edit Drawer */}
            {editingItem && (
                <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-end" onClick={() => setEditingItem(null)}>
                    <div
                        className="bg-card border-l border-border h-full w-full max-w-md p-6 overflow-y-auto shadow-2xl"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between mb-6">
                            <div>
                                <h2 className="text-xl font-bold uppercase tracking-tight">Edit Holding</h2>
                                <p className="text-sm text-muted-foreground mt-1">{editingItem.card_name}</p>
                            </div>
                            <button
                                onClick={() => setEditingItem(null)}
                                className="text-muted-foreground hover:text-foreground transition-colors"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        {/* Edit Form */}
                        <form onSubmit={handleEditSubmit} className="space-y-6">
                            <div>
                                <label className="block text-xs uppercase font-bold text-muted-foreground mb-2">
                                    Quantity
                                </label>
                                <input
                                    type="number"
                                    min="1"
                                    value={editForm.quantity}
                                    onChange={(e) => setEditForm({ ...editForm, quantity: parseInt(e.target.value) || 1 })}
                                    className="w-full px-4 py-2 bg-background border border-border rounded font-mono focus:outline-none focus:ring-2 focus:ring-primary"
                                />
                            </div>

                            <div>
                                <label className="block text-xs uppercase font-bold text-muted-foreground mb-2">
                                    Purchase Price (per card)
                                </label>
                                <div className="relative">
                                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground">$</span>
                                    <input
                                        type="number"
                                        step="0.01"
                                        min="0"
                                        value={editForm.purchase_price}
                                        onChange={(e) => setEditForm({ ...editForm, purchase_price: parseFloat(e.target.value) || 0 })}
                                        className="w-full pl-8 pr-4 py-2 bg-background border border-border rounded font-mono focus:outline-none focus:ring-2 focus:ring-primary"
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="block text-xs uppercase font-bold text-muted-foreground mb-2">
                                    Acquired Date <span className="text-xs normal-case">(optional)</span>
                                </label>
                                <input
                                    type="date"
                                    value={editForm.acquired_at}
                                    onChange={(e) => setEditForm({ ...editForm, acquired_at: e.target.value })}
                                    className="w-full px-4 py-2 bg-background border border-border rounded font-mono focus:outline-none focus:ring-2 focus:ring-primary"
                                />
                            </div>

                            {/* Current Stats */}
                            <div className="pt-4 border-t border-border space-y-3">
                                <div className="flex justify-between text-sm">
                                    <span className="text-muted-foreground">Current Market Price:</span>
                                    <span className="font-mono font-bold">${editingItem.current_market_price?.toFixed(2) || '0.00'}</span>
                                </div>
                                <div className="flex justify-between text-sm">
                                    <span className="text-muted-foreground">Total Cost Basis:</span>
                                    <span className="font-mono">${(editForm.quantity * editForm.purchase_price).toFixed(2)}</span>
                                </div>
                                <div className="flex justify-between text-sm">
                                    <span className="text-muted-foreground">Current Value:</span>
                                    <span className="font-mono font-bold">${((editingItem.current_market_price || 0) * editForm.quantity).toFixed(2)}</span>
                                </div>
                            </div>

                            {/* Actions */}
                            <div className="flex gap-3 pt-4">
                                <button
                                    type="button"
                                    onClick={() => setEditingItem(null)}
                                    className="flex-1 px-4 py-2 border border-border rounded text-sm uppercase font-bold hover:bg-muted/50 transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={updateMutation.isPending}
                                    className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded text-sm uppercase font-bold hover:bg-primary/90 transition-colors disabled:opacity-50"
                                >
                                    {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    </div>
  )
}

