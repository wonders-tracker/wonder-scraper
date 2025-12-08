import { createRoute, Link, redirect } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, auth } from '../utils/auth'
import { analytics } from '~/services/analytics'
import { Route as rootRoute } from './__root'
import { ArrowLeft, TrendingUp, Trash2, Search, Edit, X, TrendingDown, BarChart3, Plus, Filter, Package } from 'lucide-react'
import { ColumnDef, flexRender, getCoreRowModel, useReactTable, getSortedRowModel, SortingState, getFilteredRowModel } from '@tanstack/react-table'
import { useMemo, useState, useEffect } from 'react'
import clsx from 'clsx'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell } from 'recharts'
import { TreatmentBadge } from '../components/TreatmentBadge'

// New individual card tracking type
type PortfolioCard = {
    id: number
    user_id: number
    card_id: number
    treatment: string
    source: string
    purchase_price: number
    purchase_date: string | null
    grading: string | null
    notes: string | null
    created_at: string
    updated_at: string
    // Card details
    card_name: string | null
    card_set: string | null
    card_slug: string | null
    rarity_name: string | null
    product_type: string | null
    // Market data
    market_price: number | null
    profit_loss: number | null
    profit_loss_percent: number | null
}

type PortfolioSummary = {
    total_cards: number
    total_cost_basis: number
    total_market_value: number
    total_profit_loss: number
    total_profit_loss_percent: number
    by_treatment: Record<string, { count: number; cost: number; value: number }> | null
    by_source: Record<string, { count: number; cost: number; value: number }> | null
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

// Actual WOTF card treatments
const TREATMENTS = [
  'Classic Paper', 'Classic Foil',
  'Full Art', 'Full Art Foil',
  'Formless', 'Formless Foil',
  'Serialized',
  '1st Edition', '1st Edition Foil',
  'Promo', 'Prerelease'
]
const SOURCES = ['eBay', 'Blokpax', 'TCGPlayer', 'LGS', 'Trade', 'Pack Pull', 'Other']
const PIE_COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4']

function Portfolio() {
  const queryClient = useQueryClient()
  const [editingCard, setEditingCard] = useState<PortfolioCard | null>(null)
  const [editForm, setEditForm] = useState({
    treatment: 'Classic Paper',
    source: 'Other',
    purchase_price: 0,
    purchase_date: '',
    grading: '',
    notes: ''
  })
  const [sorting, setSorting] = useState<SortingState>([])
  const [filterTreatment, setFilterTreatment] = useState<string>('')
  const [filterSource, setFilterSource] = useState<string>('')
  const [filterGraded, setFilterGraded] = useState<string>('')
  const [showFilters, setShowFilters] = useState(false)

  // Track portfolio access
  useEffect(() => {
    analytics.trackPortfolioAccess()
  }, [])

  // Fetch Portfolio Cards (new individual tracking)
  const { data: portfolio, isLoading } = useQuery({
    queryKey: ['portfolio-cards', filterTreatment, filterSource, filterGraded],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (filterTreatment) params.set('treatment', filterTreatment)
      if (filterSource) params.set('source', filterSource)
      if (filterGraded === 'graded') params.set('graded', 'true')
      if (filterGraded === 'raw') params.set('graded', 'false')
      const queryString = params.toString()
      return await api.get(`portfolio/cards${queryString ? '?' + queryString : ''}`).json<PortfolioCard[]>()
    }
  })

  // Fetch Portfolio Summary
  const { data: summary } = useQuery({
    queryKey: ['portfolio-summary'],
    queryFn: async () => {
      return await api.get('portfolio/cards/summary').json<PortfolioSummary>()
    }
  })

  // Update Mutation (PATCH for individual cards)
  const updateMutation = useMutation({
      mutationFn: async ({ id, data }: { id: number, data: any }) => {
          return await api.patch(`portfolio/cards/${id}`, { json: data }).json<PortfolioCard>()
      },
      onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ['portfolio-cards'] })
          queryClient.invalidateQueries({ queryKey: ['portfolio-summary'] })
          setEditingCard(null)
      }
  })

  // Delete Mutation (soft delete)
  const deleteMutation = useMutation({
      mutationFn: async (cardId: number) => {
          await api.delete(`portfolio/cards/${cardId}`)
      },
      onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ['portfolio-cards'] })
          queryClient.invalidateQueries({ queryKey: ['portfolio-summary'] })
      }
  })

  // Open edit drawer
  const handleEditClick = (card: PortfolioCard) => {
      setEditingCard(card)
      setEditForm({
          treatment: card.treatment,
          source: card.source,
          purchase_price: card.purchase_price,
          purchase_date: card.purchase_date ? new Date(card.purchase_date).toISOString().split('T')[0] : '',
          grading: card.grading || '',
          notes: card.notes || ''
      })
  }

  // Submit edit
  const handleEditSubmit = (e: React.FormEvent) => {
      e.preventDefault()
      if (!editingCard) return

      updateMutation.mutate({
          id: editingCard.id,
          data: {
              treatment: editForm.treatment,
              source: editForm.source,
              purchase_price: editForm.purchase_price,
              purchase_date: editForm.purchase_date || null,
              grading: editForm.grading || null,
              notes: editForm.notes || null
          }
      })
  }

  // Clear filters
  const clearFilters = () => {
      setFilterTreatment('')
      setFilterSource('')
      setFilterGraded('')
  }

  const hasActiveFilters = filterTreatment || filterSource || filterGraded

  // Aggregate Stats from summary
  const stats = useMemo(() => {
      if (!summary) return { totalValue: 0, totalCost: 0, totalGain: 0, totalGainPercent: 0, count: 0 }

      return {
          totalValue: summary.total_market_value,
          totalCost: summary.total_cost_basis,
          totalGain: summary.total_profit_loss,
          totalGainPercent: summary.total_profit_loss_percent,
          count: summary.total_cards
      }
  }, [summary])

  // Prepare pie chart data
  const treatmentPieData = useMemo(() => {
      if (!summary?.by_treatment) return []
      return Object.entries(summary.by_treatment).map(([name, data]) => ({
          name,
          value: data.count
      }))
  }, [summary])

  const sourcePieData = useMemo(() => {
      if (!summary?.by_source) return []
      return Object.entries(summary.by_source).map(([name, data]) => ({
          name,
          value: data.count
      }))
  }, [summary])

  const columns = useMemo<ColumnDef<PortfolioCard>[]>(() => [
      {
          accessorKey: 'card_name',
          header: 'Card',
          cell: ({ row }) => (
              <div>
                  <Link to={`/cards/${row.original.card_slug || row.original.card_id}` as any} className="font-bold hover:underline hover:text-primary">
                      {row.original.card_name || 'Unknown'}
                  </Link>
                  <div className="text-[10px] text-muted-foreground uppercase">{row.original.card_set}</div>
              </div>
          )
      },
      {
          accessorKey: 'treatment',
          header: 'Treatment',
          cell: ({ row }) => (
              <TreatmentBadge treatment={row.original.treatment} size="xs" />
          )
      },
      {
          accessorKey: 'source',
          header: 'Source',
          cell: ({ row }) => (
              <span className="text-xs text-muted-foreground">
                  {row.original.source}
              </span>
          )
      },
      {
          accessorKey: 'grading',
          header: 'Grade',
          cell: ({ row }) => (
              row.original.grading ? (
                  <span className="text-xs px-2 py-0.5 rounded bg-yellow-700/50 font-bold">
                      {row.original.grading}
                  </span>
              ) : (
                  <span className="text-xs text-muted-foreground">Raw</span>
              )
          )
      },
      {
          accessorKey: 'purchase_price',
          header: () => <div className="text-right">Cost</div>,
          cell: ({ row }) => <div className="text-right text-muted-foreground font-mono">${row.original.purchase_price.toFixed(2)}</div>
      },
      {
          accessorKey: 'market_price',
          header: () => <div className="text-right">Market</div>,
          cell: ({ row }) => <div className="text-right font-mono font-bold">${(row.original.market_price || 0).toFixed(2)}</div>
      },
      {
          accessorKey: 'profit_loss',
          header: () => <div className="text-right">P/L</div>,
          cell: ({ row }) => {
              const val = row.original.profit_loss || 0
              const pct = row.original.profit_loss_percent || 0
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
                        if (confirm('Remove this card from your portfolio?')) {
                            deleteMutation.mutate(row.original.id)
                        }
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
      getSortedRowModel: getSortedRowModel(),
      getFilteredRowModel: getFilteredRowModel(),
      state: { sorting },
      onSortingChange: setSorting,
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
                    <Plus className="w-3 h-3" /> Add Cards
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

            {/* Breakdown Charts */}
            {(treatmentPieData.length > 0 || sourcePieData.length > 0) && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                    {/* By Treatment */}
                    {treatmentPieData.length > 0 && (
                        <div className="border border-border rounded-lg bg-card p-6">
                            <div className="flex items-center gap-2 mb-4">
                                <Package className="w-4 h-4 text-primary" />
                                <h3 className="text-sm font-bold uppercase tracking-widest">By Treatment</h3>
                            </div>
                            <div className="flex items-center">
                                <div className="h-32 w-32 min-w-[128px] min-h-[128px]">
                                    <ResponsiveContainer width="100%" height="100%" minWidth={128} minHeight={128}>
                                        <PieChart>
                                            <Pie
                                                data={treatmentPieData}
                                                cx="50%"
                                                cy="50%"
                                                innerRadius={25}
                                                outerRadius={50}
                                                dataKey="value"
                                            >
                                                {treatmentPieData.map((_, index) => (
                                                    <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                                                ))}
                                            </Pie>
                                        </PieChart>
                                    </ResponsiveContainer>
                                </div>
                                <div className="flex-1 ml-4 space-y-1">
                                    {treatmentPieData.map((item, idx) => (
                                        <div key={item.name} className="flex items-center justify-between text-xs">
                                            <div className="flex items-center gap-2">
                                                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: PIE_COLORS[idx % PIE_COLORS.length] }} />
                                                <span className="text-muted-foreground">{item.name}</span>
                                            </div>
                                            <span className="font-mono">{item.value}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}

                    {/* By Source */}
                    {sourcePieData.length > 0 && (
                        <div className="border border-border rounded-lg bg-card p-6">
                            <div className="flex items-center gap-2 mb-4">
                                <BarChart3 className="w-4 h-4 text-primary" />
                                <h3 className="text-sm font-bold uppercase tracking-widest">By Source</h3>
                            </div>
                            <div className="flex items-center">
                                <div className="h-32 w-32 min-w-[128px] min-h-[128px]">
                                    <ResponsiveContainer width="100%" height="100%" minWidth={128} minHeight={128}>
                                        <PieChart>
                                            <Pie
                                                data={sourcePieData}
                                                cx="50%"
                                                cy="50%"
                                                innerRadius={25}
                                                outerRadius={50}
                                                dataKey="value"
                                            >
                                                {sourcePieData.map((_, index) => (
                                                    <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                                                ))}
                                            </Pie>
                                        </PieChart>
                                    </ResponsiveContainer>
                                </div>
                                <div className="flex-1 ml-4 space-y-1">
                                    {sourcePieData.map((item, idx) => (
                                        <div key={item.name} className="flex items-center justify-between text-xs">
                                            <div className="flex items-center gap-2">
                                                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: PIE_COLORS[idx % PIE_COLORS.length] }} />
                                                <span className="text-muted-foreground">{item.name}</span>
                                            </div>
                                            <span className="font-mono">{item.value}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Filters */}
            <div className="border border-border rounded-lg bg-card mb-6">
                <div className="px-6 py-4 border-b border-border bg-muted/20 flex items-center justify-between">
                    <h3 className="text-sm font-bold uppercase tracking-widest">Holdings</h3>
                    <button
                        onClick={() => setShowFilters(!showFilters)}
                        className={clsx(
                            "flex items-center gap-2 text-xs uppercase font-bold px-3 py-1.5 rounded transition-colors",
                            hasActiveFilters ? "bg-primary text-primary-foreground" : "bg-muted hover:bg-muted/80"
                        )}
                    >
                        <Filter className="w-3 h-3" />
                        Filters {hasActiveFilters && `(${[filterTreatment, filterSource, filterGraded].filter(Boolean).length})`}
                    </button>
                </div>

                {/* Filter Panel */}
                {showFilters && (
                    <div className="px-6 py-4 border-b border-border bg-muted/10 flex flex-wrap gap-4 items-center">
                        <div className="flex items-center gap-2">
                            <label className="text-xs uppercase text-muted-foreground">Treatment:</label>
                            <select
                                value={filterTreatment}
                                onChange={(e) => setFilterTreatment(e.target.value)}
                                className="text-sm bg-background border border-border rounded px-2 py-1"
                            >
                                <option value="">All</option>
                                {TREATMENTS.map(t => (
                                    <option key={t} value={t}>{t}</option>
                                ))}
                            </select>
                        </div>
                        <div className="flex items-center gap-2">
                            <label className="text-xs uppercase text-muted-foreground">Source:</label>
                            <select
                                value={filterSource}
                                onChange={(e) => setFilterSource(e.target.value)}
                                className="text-sm bg-background border border-border rounded px-2 py-1"
                            >
                                <option value="">All</option>
                                {SOURCES.map(s => (
                                    <option key={s} value={s}>{s}</option>
                                ))}
                            </select>
                        </div>
                        <div className="flex items-center gap-2">
                            <label className="text-xs uppercase text-muted-foreground">Grading:</label>
                            <select
                                value={filterGraded}
                                onChange={(e) => setFilterGraded(e.target.value)}
                                className="text-sm bg-background border border-border rounded px-2 py-1"
                            >
                                <option value="">All</option>
                                <option value="graded">Graded Only</option>
                                <option value="raw">Raw Only</option>
                            </select>
                        </div>
                        {hasActiveFilters && (
                            <button
                                onClick={clearFilters}
                                className="text-xs text-muted-foreground hover:text-foreground underline"
                            >
                                Clear All
                            </button>
                        )}
                    </div>
                )}

                {/* Holdings Table */}
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
                                    <td colSpan={8} className="p-12 text-center text-muted-foreground">
                                        <div className="mb-4">
                                            {hasActiveFilters ? 'No cards match your filters.' : 'Your portfolio is empty.'}
                                        </div>
                                        {hasActiveFilters ? (
                                            <button onClick={clearFilters} className="text-primary hover:underline uppercase text-xs font-bold">
                                                Clear Filters
                                            </button>
                                        ) : (
                                            <Link to="/" className="text-primary hover:underline uppercase text-xs font-bold">
                                                Browse Market to Add Cards
                                            </Link>
                                        )}
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Edit Drawer */}
            {editingCard && (
                <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-end" onClick={() => setEditingCard(null)}>
                    <div
                        className="bg-card border-l border-border h-full w-full max-w-md p-6 overflow-y-auto shadow-2xl"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between mb-6">
                            <div>
                                <h2 className="text-xl font-bold uppercase tracking-tight">Edit Card</h2>
                                <p className="text-sm text-muted-foreground mt-1">{editingCard.card_name}</p>
                                <p className="text-xs text-muted-foreground">{editingCard.card_set}</p>
                            </div>
                            <button
                                onClick={() => setEditingCard(null)}
                                className="text-muted-foreground hover:text-foreground transition-colors"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        {/* Edit Form */}
                        <form onSubmit={handleEditSubmit} className="space-y-6">
                            <div>
                                <label className="block text-xs uppercase font-bold text-muted-foreground mb-2">
                                    Treatment
                                </label>
                                <select
                                    value={editForm.treatment}
                                    onChange={(e) => setEditForm({ ...editForm, treatment: e.target.value })}
                                    className="w-full px-4 py-2 bg-background border border-border rounded font-mono focus:outline-none focus:ring-2 focus:ring-primary"
                                >
                                    {TREATMENTS.map(t => (
                                        <option key={t} value={t}>{t}</option>
                                    ))}
                                </select>
                            </div>

                            <div>
                                <label className="block text-xs uppercase font-bold text-muted-foreground mb-2">
                                    Source
                                </label>
                                <select
                                    value={editForm.source}
                                    onChange={(e) => setEditForm({ ...editForm, source: e.target.value })}
                                    className="w-full px-4 py-2 bg-background border border-border rounded font-mono focus:outline-none focus:ring-2 focus:ring-primary"
                                >
                                    {SOURCES.map(s => (
                                        <option key={s} value={s}>{s}</option>
                                    ))}
                                </select>
                            </div>

                            <div>
                                <label className="block text-xs uppercase font-bold text-muted-foreground mb-2">
                                    Purchase Price
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
                                    Purchase Date <span className="text-xs normal-case">(optional)</span>
                                </label>
                                <input
                                    type="date"
                                    value={editForm.purchase_date}
                                    onChange={(e) => setEditForm({ ...editForm, purchase_date: e.target.value })}
                                    className="w-full px-4 py-2 bg-background border border-border rounded font-mono focus:outline-none focus:ring-2 focus:ring-primary"
                                />
                            </div>

                            <div>
                                <label className="block text-xs uppercase font-bold text-muted-foreground mb-2">
                                    Grading <span className="text-xs normal-case">(e.g., PSA 10, BGS 9.5)</span>
                                </label>
                                <input
                                    type="text"
                                    placeholder="Leave blank for raw cards"
                                    value={editForm.grading}
                                    onChange={(e) => setEditForm({ ...editForm, grading: e.target.value })}
                                    className="w-full px-4 py-2 bg-background border border-border rounded font-mono focus:outline-none focus:ring-2 focus:ring-primary"
                                />
                            </div>

                            <div>
                                <label className="block text-xs uppercase font-bold text-muted-foreground mb-2">
                                    Notes <span className="text-xs normal-case">(optional)</span>
                                </label>
                                <textarea
                                    rows={3}
                                    placeholder="Any notes about this card..."
                                    value={editForm.notes}
                                    onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
                                    className="w-full px-4 py-2 bg-background border border-border rounded font-mono focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                                />
                            </div>

                            {/* Current Stats */}
                            <div className="pt-4 border-t border-border space-y-3">
                                <div className="flex justify-between text-sm">
                                    <span className="text-muted-foreground">Current Market Price:</span>
                                    <span className="font-mono font-bold">${(editingCard.market_price || 0).toFixed(2)}</span>
                                </div>
                                <div className="flex justify-between text-sm">
                                    <span className="text-muted-foreground">Cost Basis:</span>
                                    <span className="font-mono">${editForm.purchase_price.toFixed(2)}</span>
                                </div>
                                <div className="flex justify-between text-sm">
                                    <span className="text-muted-foreground">Profit/Loss:</span>
                                    <span className={clsx(
                                        "font-mono font-bold",
                                        (editingCard.profit_loss || 0) >= 0 ? "text-emerald-500" : "text-red-500"
                                    )}>
                                        {(editingCard.profit_loss || 0) >= 0 ? '+' : ''}${(editingCard.profit_loss || 0).toFixed(2)}
                                    </span>
                                </div>
                            </div>

                            {/* Actions */}
                            <div className="flex gap-3 pt-4">
                                <button
                                    type="button"
                                    onClick={() => setEditingCard(null)}
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
