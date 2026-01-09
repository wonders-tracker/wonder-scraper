/**
 * TreatmentPricingTable - Treatment/Variant comparison with sorting
 *
 * Displays pricing data per treatment variant:
 * - Treatment name with color badge
 * - Floor Price (avg of 4 lowest recent sales)
 * - Lowest Ask (active listing)
 * - FMP (Fair Market Price)
 * - Confidence indicator
 * - Sales count
 *
 * Features:
 * - Clickable rows to filter
 * - Sortable columns
 * - Highlight selected treatment
 *
 * @see tasks.json E3-U4
 */

import { useState, useMemo } from 'react'
import { cn } from '@/lib/utils'
import { formatPrice } from '@/lib/formatters'
import { Tooltip } from '../ui/tooltip'
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'

export type TreatmentRow = {
  treatment: string
  floor?: number | null
  ask?: number | null
  fmp?: number | null
  confidence?: number | null
  salesCount?: number | null
}

export type TreatmentPricingTableProps = {
  /** Array of treatment pricing data */
  data: TreatmentRow[]
  /** Currently selected treatment filter */
  selectedTreatment?: string | null
  /** Callback when treatment row is clicked */
  onTreatmentSelect?: (treatment: string | null) => void
  /** Whether this is for a sealed product (use "Variant" instead of "Treatment") */
  isSealed?: boolean
  /** Whether user is logged in (to show/hide FMP) */
  isLoggedIn?: boolean
  /** Additional className */
  className?: string
}

type SortKey = 'treatment' | 'floor' | 'ask' | 'fmp' | 'salesCount'
type SortDir = 'asc' | 'desc'

/**
 * Simple treatment badge (inline version)
 */
function TreatmentBadgeSimple({ treatment }: { treatment: string }) {
  const color = getTreatmentColor(treatment)
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider"
      style={{
        backgroundColor: `${color}20`,
        color: color
      }}
    >
      {treatment}
    </span>
  )
}

/**
 * Get treatment color (simplified version of main getTreatmentColor)
 */
function getTreatmentColor(treatment: string): string {
  const t = (treatment || '').toLowerCase()
  if (t.includes('formless')) return '#d946ef'
  if (t.includes('serial') || t.includes('ocm')) return '#facc15'
  if (t.includes('stone')) return '#a8a29e'
  if (t.includes('star')) return '#a78bfa'
  if (t.includes('full art') && t.includes('foil')) return '#34d399'
  if (t.includes('animated')) return '#22d3ee'
  if (t.includes('foil') || t.includes('holo')) return '#38bdf8'
  if (t.includes('full art') || t.includes('alt art')) return '#818cf8'
  if (t.includes('prerelease')) return '#f472b6'
  if (t.includes('promo')) return '#fb7185'
  return '#9ca3af' // default gray for Classic Paper
}

/**
 * Sort icon component
 */
function SortIcon({ dir }: { dir?: SortDir }) {
  if (!dir) return <ChevronsUpDown className="w-3 h-3 text-muted-foreground" />
  if (dir === 'asc') return <ChevronUp className="w-3 h-3 text-brand-400" />
  return <ChevronDown className="w-3 h-3 text-brand-400" />
}

/**
 * Confidence indicator dots
 */
function ConfidenceDots({ score }: { score?: number | null }) {
  const level = score != null ? Math.min(5, Math.max(0, Math.round(score))) : 0
  return (
    <div className="flex items-center gap-0.5" title={`Confidence: ${level}/5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <div
          key={i}
          className={cn(
            'w-1.5 h-1.5 rounded-full',
            i <= level ? 'bg-brand-400' : 'bg-muted-foreground/30'
          )}
        />
      ))}
    </div>
  )
}

export function TreatmentPricingTable({
  data,
  selectedTreatment,
  onTreatmentSelect,
  isSealed = false,
  isLoggedIn = false,
  className
}: TreatmentPricingTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('floor')
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  // Sort data
  const sortedData = useMemo(() => {
    return [...data].sort((a, b) => {
      let aVal: number | string = 0
      let bVal: number | string = 0

      switch (sortKey) {
        case 'treatment':
          aVal = a.treatment.toLowerCase()
          bVal = b.treatment.toLowerCase()
          break
        case 'floor':
          aVal = a.floor ?? Infinity
          bVal = b.floor ?? Infinity
          break
        case 'ask':
          aVal = a.ask ?? Infinity
          bVal = b.ask ?? Infinity
          break
        case 'fmp':
          aVal = a.fmp ?? Infinity
          bVal = b.fmp ?? Infinity
          break
        case 'salesCount':
          aVal = a.salesCount ?? 0
          bVal = b.salesCount ?? 0
          break
      }

      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal)
      }

      const numA = aVal as number
      const numB = bVal as number
      return sortDir === 'asc' ? numA - numB : numB - numA
    })
  }, [data, sortKey, sortDir])

  // Handle column header click
  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  // Handle row click
  const handleRowClick = (treatment: string) => {
    if (!onTreatmentSelect) return
    if (selectedTreatment === treatment) {
      onTreatmentSelect(null) // Deselect
    } else {
      onTreatmentSelect(treatment)
    }
  }

  const label = isSealed ? 'Variant' : 'Treatment'

  if (data.length === 0) {
    return null
  }

  return (
    <div className={cn('border border-border rounded bg-card', className)}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-widest">
          {label} Pricing
        </h3>
        {selectedTreatment && (
          <button
            onClick={() => onTreatmentSelect?.(null)}
            className="text-[10px] text-muted-foreground hover:text-foreground transition-colors"
          >
            Clear filter ×
          </button>
        )}
      </div>

      {/* Mobile scroll hint */}
      <div className="sm:hidden text-[10px] text-muted-foreground text-center py-1.5 border-b border-border/50">
        ← Scroll for more →
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted-foreground text-xs border-b border-border">
              <th className="p-3">
                <button
                  onClick={() => handleSort('treatment')}
                  className="flex items-center gap-1 hover:text-foreground transition-colors"
                >
                  {label}
                  <SortIcon dir={sortKey === 'treatment' ? sortDir : undefined} />
                </button>
              </th>
              <th className="p-3 text-right">
                <Tooltip content="Average of 4 lowest recent sales">
                  <button
                    onClick={() => handleSort('floor')}
                    className="flex items-center gap-1 justify-end hover:text-foreground transition-colors cursor-help"
                  >
                    Floor
                    <SortIcon dir={sortKey === 'floor' ? sortDir : undefined} />
                  </button>
                </Tooltip>
              </th>
              <th className="p-3 text-right">
                <Tooltip content="Lowest active listing price">
                  <button
                    onClick={() => handleSort('ask')}
                    className="flex items-center gap-1 justify-end hover:text-foreground transition-colors cursor-help"
                  >
                    Ask
                    <SortIcon dir={sortKey === 'ask' ? sortDir : undefined} />
                  </button>
                </Tooltip>
              </th>
              <th className="p-3 text-right">
                <Tooltip content="Fair Market Price - MAD-trimmed mean">
                  <button
                    onClick={() => handleSort('fmp')}
                    className="flex items-center gap-1 justify-end hover:text-foreground transition-colors cursor-help"
                  >
                    FMP
                    <SortIcon dir={sortKey === 'fmp' ? sortDir : undefined} />
                  </button>
                </Tooltip>
              </th>
              <th className="p-3 text-center">
                <Tooltip content="Data confidence based on sample size">
                  <span className="cursor-help">Conf</span>
                </Tooltip>
              </th>
              <th className="p-3 text-right">
                <button
                  onClick={() => handleSort('salesCount')}
                  className="flex items-center gap-1 justify-end hover:text-foreground transition-colors"
                >
                  Sales
                  <SortIcon dir={sortKey === 'salesCount' ? sortDir : undefined} />
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedData.map(row => {
              const isSelected = selectedTreatment === row.treatment
              return (
                <tr
                  key={row.treatment}
                  onClick={() => handleRowClick(row.treatment)}
                  className={cn(
                    'border-b border-border/50 transition-colors cursor-pointer',
                    isSelected
                      ? 'bg-brand-500/10 hover:bg-brand-500/15'
                      : 'hover:bg-muted/50',
                    onTreatmentSelect && 'cursor-pointer'
                  )}
                >
                  <td className="p-3">
                    <TreatmentBadgeSimple treatment={row.treatment} />
                  </td>
                  <td className="p-3 text-right font-mono text-brand-300">
                    {row.floor != null ? formatPrice(row.floor) : '---'}
                  </td>
                  <td className="p-3 text-right font-mono text-blue-400">
                    {row.ask != null ? formatPrice(row.ask) : '---'}
                  </td>
                  <td className="p-3 text-right font-mono text-amber-400">
                    {isLoggedIn ? (
                      row.fmp != null ? formatPrice(row.fmp) : '---'
                    ) : (
                      <span className="text-muted-foreground">•••</span>
                    )}
                  </td>
                  <td className="p-3">
                    <div className="flex justify-center">
                      <ConfidenceDots score={row.confidence} />
                    </div>
                  </td>
                  <td className="p-3 text-right text-muted-foreground">
                    {row.salesCount ?? '---'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Selected treatment indicator */}
      {selectedTreatment && (
        <div className="px-4 py-2 bg-brand-500/5 border-t border-brand-500/20 text-[10px] text-brand-400">
          Filtering by: {selectedTreatment}
        </div>
      )}
    </div>
  )
}

/**
 * Loading skeleton for TreatmentPricingTable
 */
export function TreatmentPricingTableSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn('border border-border rounded bg-card animate-pulse', className)}
      role="status"
      aria-busy="true"
      aria-label="Loading treatment pricing"
    >
      <div className="px-4 py-3 border-b border-border">
        <div className="h-4 w-32 bg-muted rounded" />
      </div>
      <div className="p-3 space-y-3">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="flex items-center justify-between">
            <div className="h-5 w-20 bg-muted rounded" />
            <div className="flex gap-4">
              <div className="h-4 w-12 bg-muted rounded" />
              <div className="h-4 w-12 bg-muted rounded" />
              <div className="h-4 w-12 bg-muted rounded" />
            </div>
          </div>
        ))}
      </div>
      <span className="sr-only">Loading treatment pricing data...</span>
    </div>
  )
}
