import { createFileRoute, Link } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, auth } from '../utils/auth'
import { analytics } from '~/services/analytics'
import { ArrowLeft, TrendingUp, Trash2, Search, Edit, X, TrendingDown, BarChart3, Plus, Filter, Package } from 'lucide-react'
import { ColumnDef, flexRender, getCoreRowModel, useReactTable, getSortedRowModel, SortingState, getFilteredRowModel } from '@tanstack/react-table'
import { useMemo, useState, useEffect } from 'react'
import clsx from 'clsx'
import { LineChart, Line, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell } from 'recharts'
import { TreatmentBadge } from '../components/TreatmentBadge'
import { Tooltip } from '../components/ui/tooltip'
import { SimpleDropdown } from '../components/ui/dropdown'
import { LoginUpsellOverlay } from '../components/LoginUpsellOverlay'

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

export const Route = createFileRoute('/portfolio')({
  component: Portfolio,
})

// Actual WOTF card treatments
const TREATMENTS = [
  'Classic Paper', 'Classic Foil',
  'Full Art', 'Full Art Foil',
  'Formless', 'Formless Foil',
  'Serialized',
  '1st Edition', '1st Edition Foil',
  'Promo', 'Prerelease',
  'Preslab TAG', 'Preslab TAG 8', 'Preslab TAG 9', 'Preslab TAG 10'
]
const SOURCES = ['eBay', 'Blokpax', 'TCGPlayer', 'LGS', 'Trade', 'Pack Pull', 'Other']
const PIE_COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4']

// Treatment colors matching TreatmentBadge
const TREATMENT_COLORS: Record<string, string> = {
  'Classic Paper': '#71717a',     // zinc-500
  'Classic Foil': '#0ea5e9',      // sky-500
  'Full Art': '#6366f1',          // indigo-500
  'Full Art Foil': '#10b981',     // emerald-500
  'Formless': '#a855f7',          // purple-500
  'Formless Foil': '#d946ef',     // fuchsia-500
  'Serialized': '#eab308',        // yellow-500
  '1st Edition': '#f97316',       // orange-500
  '1st Edition Foil': '#ea580c',  // orange-600
  'Promo': '#f43f5e',             // rose-500
  'Prerelease': '#ec4899',        // pink-500
  'Preslab TAG': '#2dd4bf',       // teal-400
  'Preslab TAG 8': '#38bdf8',     // sky-400
  'Preslab TAG 9': '#4ade80',     // green-400
  'Preslab TAG 10': '#fcd34d',    // amber-300
}

const getTreatmentColor = (treatment: string): string => {
  return TREATMENT_COLORS[treatment] || PIE_COLORS[Object.keys(TREATMENT_COLORS).length % PIE_COLORS.length]
}

// Demo data for logged-out users
const DEMO_PORTFOLIO: PortfolioCard[] = [
  { id: 1, user_id: 0, card_id: 1, treatment: 'Classic Foil', source: 'eBay', purchase_price: 45.00, purchase_date: '2024-01-15', grading: null, notes: null, created_at: '', updated_at: '', card_name: 'Progo, the Guiding Light', card_set: 'Awakening', card_slug: 'progo-the-guiding-light', rarity_name: 'Rare', product_type: 'Single', market_price: 52.50, profit_loss: 7.50, profit_loss_percent: 16.7 },
  { id: 2, user_id: 0, card_id: 2, treatment: 'Serialized', source: 'Blokpax', purchase_price: 125.00, purchase_date: '2024-02-20', grading: 'PSA 10', notes: null, created_at: '', updated_at: '', card_name: 'Deep Black Goop', card_set: 'Awakening', card_slug: 'deep-black-goop', rarity_name: 'Legendary', product_type: 'Single', market_price: 189.00, profit_loss: 64.00, profit_loss_percent: 51.2 },
  { id: 3, user_id: 0, card_id: 3, treatment: 'Full Art Foil', source: 'TCGPlayer', purchase_price: 28.50, purchase_date: '2024-03-10', grading: null, notes: null, created_at: '', updated_at: '', card_name: 'Wandering Spirit', card_set: 'Awakening', card_slug: 'wandering-spirit', rarity_name: 'Epic', product_type: 'Single', market_price: 31.25, profit_loss: 2.75, profit_loss_percent: 9.6 },
  { id: 4, user_id: 0, card_id: 4, treatment: 'Classic Paper', source: 'Pack Pull', purchase_price: 0.00, purchase_date: '2024-03-25', grading: null, notes: null, created_at: '', updated_at: '', card_name: 'Forest Guardian', card_set: 'Awakening', card_slug: 'forest-guardian', rarity_name: 'Common', product_type: 'Single', market_price: 1.25, profit_loss: 1.25, profit_loss_percent: 100 },
  { id: 5, user_id: 0, card_id: 5, treatment: 'Formless Foil', source: 'Trade', purchase_price: 85.00, purchase_date: '2024-04-01', grading: null, notes: null, created_at: '', updated_at: '', card_name: 'Stellar Void', card_set: 'Awakening', card_slug: 'stellar-void', rarity_name: 'Legendary', product_type: 'Single', market_price: 72.00, profit_loss: -13.00, profit_loss_percent: -15.3 },
]

const DEMO_SUMMARY: PortfolioSummary = {
  total_cards: 5,
  total_cost_basis: 283.50,
  total_market_value: 346.00,
  total_profit_loss: 62.50,
  total_profit_loss_percent: 22.0,
  by_treatment: { 'Classic Foil': { count: 1, cost: 45, value: 52.5 }, 'Serialized': { count: 1, cost: 125, value: 189 }, 'Full Art Foil': { count: 1, cost: 28.5, value: 31.25 }, 'Classic Paper': { count: 1, cost: 0, value: 1.25 }, 'Formless Foil': { count: 1, cost: 85, value: 72 } },
  by_source: { 'eBay': { count: 1, cost: 45, value: 52.5 }, 'Blokpax': { count: 1, cost: 125, value: 189 }, 'TCGPlayer': { count: 1, cost: 28.5, value: 31.25 }, 'Pack Pull': { count: 1, cost: 0, value: 1.25 }, 'Trade': { count: 1, cost: 85, value: 72 } }
}

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

  // Check if user is logged in
  const isLoggedIn = auth.isAuthenticated()

  // Track portfolio access
  useEffect(() => {
    analytics.trackPortfolioAccess()
  }, [])

  // Fetch Portfolio Cards (new individual tracking) - only when logged in
  const { data: portfolioData, isLoading } = useQuery({
    queryKey: ['portfolio-cards', filterTreatment, filterSource, filterGraded],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (filterTreatment) params.set('treatment', filterTreatment)
      if (filterSource) params.set('source', filterSource)
      if (filterGraded === 'graded') params.set('graded', 'true')
      if (filterGraded === 'raw') params.set('graded', 'false')
      const queryString = params.toString()
      return await api.get(`portfolio/cards${queryString ? '?' + queryString : ''}`).json<PortfolioCard[]>()
    },
    staleTime: 2 * 60 * 1000, // 2 minutes - portfolio data is user-specific
    enabled: isLoggedIn, // Only fetch when logged in
  })

  // Fetch Portfolio Summary - only when logged in
  const { data: summaryData } = useQuery({
    queryKey: ['portfolio-summary'],
    queryFn: async () => {
      return await api.get('portfolio/cards/summary').json<PortfolioSummary>()
    },
    staleTime: 2 * 60 * 1000, // 2 minutes
    enabled: isLoggedIn,
  })

  // Fetch Portfolio Value History - only when logged in
  const { data: valueHistory } = useQuery({
    queryKey: ['portfolio-value-history'],
    queryFn: async () => {
      return await api.get('portfolio/cards/history/value?days=30').json<{
        history: { date: string; value: number }[]
        cost_basis_history: { date: string; value: number }[]
      }>()
    },
    staleTime: 5 * 60 * 1000, // 5 minutes - history changes slowly
    enabled: isLoggedIn,
  })

  // Use demo data for logged-out users
  const portfolio = isLoggedIn ? portfolioData : DEMO_PORTFOLIO
  const summary = isLoggedIn ? summaryData : DEMO_SUMMARY

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

  // Prepare pie chart data - filter to only valid physical card treatments
  const VALID_TREATMENTS = new Set(TREATMENTS)
  const treatmentPieData = useMemo(() => {
      if (!summary?.by_treatment) return []
      return Object.entries(summary.by_treatment)
          .filter(([name]) => VALID_TREATMENTS.has(name))
          .map(([name, data]) => ({
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

  // Prepare value history chart data
  const valueChartData = useMemo(() => {
      if (!valueHistory?.history?.length) return []
      return valueHistory.history.map((h, idx) => ({
          date: new Date(h.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
          value: h.value,
          cost: valueHistory.cost_basis_history[idx]?.value || 0
      }))
  }, [valueHistory])

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
                  <Tooltip content="Edit">
                      <button
                        onClick={(e) => {
                            e.stopPropagation()
                            handleEditClick(row.original)
                        }}
                        className="text-muted-foreground hover:text-primary transition-colors"
                      >
                          <Edit className="w-4 h-4" />
                      </button>
                  </Tooltip>
                  <Tooltip content="Remove from Portfolio">
                      <button
                        onClick={(e) => {
                            e.stopPropagation()
                            if (confirm('Remove this card from your portfolio?')) {
                                deleteMutation.mutate(row.original.id)
                            }
                        }}
                        className="text-muted-foreground hover:text-red-500 transition-colors"
                      >
                          <Trash2 className="w-4 h-4" />
                      </button>
                  </Tooltip>
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
    <div className="p-6 min-h-screen bg-background text-foreground font-mono relative">
        {/* Login Upsell Overlay for logged-out users */}
        {!isLoggedIn && (
            <LoginUpsellOverlay
                title="Track Your Collection"
                description="Sign in to track your portfolio, monitor P/L, and see your collection's value over time."
            />
        )}

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

            {/* Portfolio Summary - Inline Stats with Mini Pie Charts */}
            <div className="flex flex-wrap items-center gap-6 mb-6 text-sm">
                <Tooltip content="Current market value of all cards">
                    <div className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-emerald-500"></div>
                        <span className="text-[10px] text-muted-foreground uppercase">Value</span>
                        <span className="font-mono font-bold text-lg">${stats.totalValue.toFixed(2)}</span>
                    </div>
                </Tooltip>
                <Tooltip content="Total amount paid for all cards (cost basis)">
                    <div className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-gray-500"></div>
                        <span className="text-[10px] text-muted-foreground uppercase">Cost</span>
                        <span className="font-mono text-muted-foreground text-lg">${stats.totalCost.toFixed(2)}</span>
                    </div>
                </Tooltip>
                <Tooltip content="Unrealized profit/loss if sold at current market prices">
                    <div className="flex items-center gap-2">
                        <div className={clsx("w-1.5 h-1.5 rounded-full", stats.totalGain >= 0 ? "bg-emerald-500" : "bg-red-500")}></div>
                        <span className="text-[10px] text-muted-foreground uppercase">Return</span>
                        <span className={clsx("font-mono font-bold text-lg", stats.totalGain >= 0 ? "text-emerald-500" : "text-red-500")}>
                            {stats.totalGain >= 0 ? '+' : ''}${Math.abs(stats.totalGain).toFixed(2)}
                        </span>
                        <span className={clsx("text-xs", stats.totalGain >= 0 ? "text-emerald-500" : "text-red-500")}>
                            ({stats.totalGain >= 0 ? '+' : ''}{stats.totalGainPercent.toFixed(1)}%)
                        </span>
                    </div>
                </Tooltip>
                <Tooltip content="Total cards in your portfolio">
                    <div className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-blue-500"></div>
                        <span className="text-[10px] text-muted-foreground uppercase">Cards</span>
                        <span className="font-mono font-bold text-lg">{stats.count}</span>
                    </div>
                </Tooltip>

                {/* Mini Pie Charts with Tooltip Legends */}
                {treatmentPieData.length > 0 && (
                    <div className="flex items-center gap-1 ml-4 border-l border-border pl-4 group relative">
                        <div className="h-10 w-10">
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie data={treatmentPieData} cx="50%" cy="50%" innerRadius={10} outerRadius={18} dataKey="value" strokeWidth={0}>
                                        {treatmentPieData.map((item) => (
                                            <Cell key={`t-${item.name}`} fill={getTreatmentColor(item.name)} />
                                        ))}
                                    </Pie>
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                        <span className="text-[10px] text-muted-foreground uppercase">Treatment</span>
                        <Tooltip content="Breakdown by card treatment type">
                            <span className="w-4 h-4 rounded-full bg-muted flex items-center justify-center text-[9px] text-muted-foreground cursor-help">i</span>
                        </Tooltip>
                        {/* Tooltip */}
                        <div className="absolute left-0 top-full mt-2 z-50 hidden group-hover:block bg-card border border-border rounded-lg p-3 shadow-xl min-w-[140px]">
                            <div className="text-[10px] uppercase text-muted-foreground mb-2 font-bold">By Treatment</div>
                            {treatmentPieData.map((item) => (
                                <div key={item.name} className="flex items-center justify-between text-xs py-0.5">
                                    <div className="flex items-center gap-2">
                                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: getTreatmentColor(item.name) }} />
                                        <span className="text-muted-foreground">{item.name}</span>
                                    </div>
                                    <span className="font-mono ml-3">{item.value}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
                {sourcePieData.length > 0 && (
                    <div className="flex items-center gap-1 group relative">
                        <div className="h-10 w-10">
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie data={sourcePieData} cx="50%" cy="50%" innerRadius={10} outerRadius={18} dataKey="value" strokeWidth={0}>
                                        {sourcePieData.map((_, index) => (
                                            <Cell key={`s-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                                        ))}
                                    </Pie>
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                        <span className="text-[10px] text-muted-foreground uppercase">Source</span>
                        <Tooltip content="Breakdown by purchase source">
                            <span className="w-4 h-4 rounded-full bg-muted flex items-center justify-center text-[9px] text-muted-foreground cursor-help">i</span>
                        </Tooltip>
                        {/* Tooltip */}
                        <div className="absolute left-0 top-full mt-2 z-50 hidden group-hover:block bg-card border border-border rounded-lg p-3 shadow-xl min-w-[120px]">
                            <div className="text-[10px] uppercase text-muted-foreground mb-2 font-bold">By Source</div>
                            {sourcePieData.map((item, idx) => (
                                <div key={item.name} className="flex items-center justify-between text-xs py-0.5">
                                    <div className="flex items-center gap-2">
                                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: PIE_COLORS[idx % PIE_COLORS.length] }} />
                                        <span className="text-muted-foreground">{item.name}</span>
                                    </div>
                                    <span className="font-mono ml-3">{item.value}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {/* Portfolio Value Chart */}
            {valueChartData.length > 0 && (
                <div className="border border-border rounded-lg bg-card p-6 mb-8">
                    <div className="flex items-center gap-2 mb-4">
                        <TrendingUp className="w-4 h-4 text-primary" />
                        <h3 className="text-sm font-bold uppercase tracking-widest">Portfolio Value (30 Days)</h3>
                    </div>
                    <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={valueChartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                                <XAxis
                                    dataKey="date"
                                    tick={{ fontSize: 10, fill: '#888' }}
                                    tickLine={false}
                                    interval="preserveStartEnd"
                                />
                                <YAxis
                                    tick={{ fontSize: 10, fill: '#888' }}
                                    tickLine={false}
                                    tickFormatter={(v) => `$${v}`}
                                    domain={['auto', 'auto']}
                                />
                                <RechartsTooltip
                                    contentStyle={{
                                        backgroundColor: '#1a1a1a',
                                        border: '1px solid #333',
                                        borderRadius: '8px',
                                        fontSize: '12px'
                                    }}
                                    formatter={(value: number, name: string) => [
                                        `$${value.toFixed(2)}`,
                                        name === 'value' ? 'Market Value' : 'Cost Basis'
                                    ]}
                                />
                                <Line
                                    type="monotone"
                                    dataKey="cost"
                                    stroke="#666"
                                    strokeWidth={1}
                                    strokeDasharray="5 5"
                                    dot={false}
                                    name="cost"
                                />
                                <Line
                                    type="monotone"
                                    dataKey="value"
                                    stroke="#10b981"
                                    strokeWidth={2}
                                    dot={false}
                                    name="value"
                                />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                    <div className="flex items-center justify-center gap-6 mt-4 text-xs">
                        <div className="flex items-center gap-2">
                            <div className="w-4 h-0.5 bg-emerald-500" />
                            <span className="text-muted-foreground">Market Value</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <div className="w-4 h-0.5 bg-gray-500 border-dashed" style={{ borderTop: '2px dashed #666' }} />
                            <span className="text-muted-foreground">Cost Basis</span>
                        </div>
                    </div>
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
                            <SimpleDropdown
                                value={filterTreatment}
                                onChange={setFilterTreatment}
                                options={[
                                    { value: '', label: 'All' },
                                    ...TREATMENTS.map(t => ({ value: t, label: t }))
                                ]}
                                size="sm"
                                className="w-[140px]"
                            />
                        </div>
                        <div className="flex items-center gap-2">
                            <label className="text-xs uppercase text-muted-foreground">Source:</label>
                            <SimpleDropdown
                                value={filterSource}
                                onChange={setFilterSource}
                                options={[
                                    { value: '', label: 'All' },
                                    ...SOURCES.map(s => ({ value: s, label: s }))
                                ]}
                                size="sm"
                                className="w-[120px]"
                            />
                        </div>
                        <div className="flex items-center gap-2">
                            <label className="text-xs uppercase text-muted-foreground">Grading:</label>
                            <SimpleDropdown
                                value={filterGraded}
                                onChange={setFilterGraded}
                                options={[
                                    { value: '', label: 'All' },
                                    { value: 'graded', label: 'Graded Only' },
                                    { value: 'raw', label: 'Raw Only' },
                                ]}
                                size="sm"
                                className="w-[120px]"
                            />
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
                                <SimpleDropdown
                                    value={editForm.treatment}
                                    onChange={(value) => setEditForm({ ...editForm, treatment: value })}
                                    options={TREATMENTS.map(t => ({ value: t, label: t }))}
                                    className="w-full"
                                    triggerClassName="font-mono"
                                />
                            </div>

                            <div>
                                <label className="block text-xs uppercase font-bold text-muted-foreground mb-2">
                                    Source
                                </label>
                                <SimpleDropdown
                                    value={editForm.source}
                                    onChange={(value) => setEditForm({ ...editForm, source: value })}
                                    options={SOURCES.map(s => ({ value: s, label: s }))}
                                    className="w-full"
                                    triggerClassName="font-mono"
                                />
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
