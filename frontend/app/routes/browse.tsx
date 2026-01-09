/**
 * Browse Page - Filterable card gallery with URL-backed state
 *
 * Supports filters for:
 * - Product Type (Singles, Boxes, Packs, Bundles)
 * - Rarity (Mythic, Legendary, Epic, Rare, Uncommon, Common)
 * - Treatment (Classic Paper, Classic Foil, Stonefoil, etc.)
 * - Set (Alpha)
 * - Search (free text)
 * - Sort (price, volume, name)
 */

import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { api } from '../utils/auth'
import { useState, useMemo, useEffect } from 'react'
import { Package, X, Search } from 'lucide-react'
import { cn } from '@/lib/utils'
import { SimpleDropdown } from '../components/ui/dropdown'
import { ProductCard, ProductCardSkeleton } from '../components/ui/product-card'
import { Breadcrumbs } from '../components/ui/breadcrumbs'
import { FilterDrawer, FilterTrigger, FilterSection, FilterOption } from '../components/ui/filter-drawer'
import { Button } from '../components/ui/button'

// Search params schema
type BrowseSearchParams = {
  productType?: string
  rarity?: string
  treatment?: string
  set?: string
  search?: string
  sortBy?: 'price' | 'volume' | 'name'
  dir?: 'asc' | 'desc'
}

export const Route = createFileRoute('/browse')({
  component: BrowsePage,
  validateSearch: (search: Record<string, unknown>): BrowseSearchParams => ({
    productType: typeof search.productType === 'string' ? search.productType : undefined,
    rarity: typeof search.rarity === 'string' ? search.rarity : undefined,
    treatment: typeof search.treatment === 'string' ? search.treatment : undefined,
    set: typeof search.set === 'string' ? search.set : undefined,
    search: typeof search.search === 'string' ? search.search : undefined,
    sortBy: ['price', 'volume', 'name'].includes(search.sortBy as string)
      ? (search.sortBy as BrowseSearchParams['sortBy'])
      : undefined,
    dir: ['asc', 'desc'].includes(search.dir as string)
      ? (search.dir as BrowseSearchParams['dir'])
      : undefined,
  }),
})

// Card type (matches API response)
type Card = {
  id: number
  slug?: string
  name: string
  set_name: string
  rarity_name?: string
  product_type?: string
  floor_price?: number
  latest_price?: number
  lowest_ask?: number
  volume?: number
  inventory?: number
  image_url?: string
  last_treatment?: string
}

// Rarity sort order
const RARITY_ORDER = ['Mythic', 'Legendary', 'Epic', 'Rare', 'Uncommon', 'Common']

function BrowsePage() {
  const searchParams = Route.useSearch()
  const navigate = useNavigate({ from: '/browse' })

  // Local search input state (before debounce)
  const [searchInput, setSearchInput] = useState(searchParams.search || '')

  // Mobile filter drawer state
  const [isFilterDrawerOpen, setIsFilterDrawerOpen] = useState(false)

  // Sync search input with URL params
  useEffect(() => {
    setSearchInput(searchParams.search || '')
  }, [searchParams.search])

  // Debounced search update
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchInput !== (searchParams.search || '')) {
        updateSearch({ search: searchInput || undefined })
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [searchInput])

  // Fetch cards from API
  const { data: cards, isLoading } = useQuery({
    queryKey: ['browse-cards', searchParams.productType],
    queryFn: async () => {
      const params = new URLSearchParams()
      params.set('limit', '500')
      params.set('slim', 'true')
      params.set('time_period', 'all')
      if (searchParams.productType) {
        params.set('product_type', searchParams.productType)
      }
      return api.get(`cards?${params}`).json<Card[]>()
    },
    staleTime: 2 * 60 * 1000,
  })

  // URL update helper
  const updateSearch = (updates: Partial<BrowseSearchParams>) => {
    navigate({
      search: (prev) => {
        const next = { ...prev, ...updates }
        // Remove empty/default values to keep URL clean
        Object.keys(next).forEach((key) => {
          const value = next[key as keyof BrowseSearchParams]
          if (value === undefined || value === '' || value === 'all') {
            delete next[key as keyof BrowseSearchParams]
          }
        })
        return next
      },
      replace: true,
    })
  }

  // Clear all filters
  const clearAllFilters = () => {
    navigate({ search: {}, replace: true })
    setSearchInput('')
  }

  // Extract unique filter options from data with counts
  const filterOptions = useMemo(() => {
    if (!cards) return { rarities: [], treatments: [], sets: [], productTypes: [] }

    // Count occurrences for each filter value
    const rarityCounts = new Map<string, number>()
    const treatmentCounts = new Map<string, number>()
    const setCounts = new Map<string, number>()
    const productTypeCounts = new Map<string, number>()

    cards.forEach((c) => {
      if (c.rarity_name) rarityCounts.set(c.rarity_name, (rarityCounts.get(c.rarity_name) || 0) + 1)
      if (c.last_treatment) treatmentCounts.set(c.last_treatment, (treatmentCounts.get(c.last_treatment) || 0) + 1)
      if (c.set_name) setCounts.set(c.set_name, (setCounts.get(c.set_name) || 0) + 1)
      if (c.product_type) productTypeCounts.set(c.product_type, (productTypeCounts.get(c.product_type) || 0) + 1)
    })

    const rarities = [...rarityCounts.entries()]
      .sort((a, b) => RARITY_ORDER.indexOf(a[0]) - RARITY_ORDER.indexOf(b[0]))
      .map(([value, count]) => ({ value, count }))

    const treatments = [...treatmentCounts.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([value, count]) => ({ value, count }))

    const sets = [...setCounts.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([value, count]) => ({ value, count }))

    const productTypes = [...productTypeCounts.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([value, count]) => ({ value, count }))

    return { rarities, treatments, sets, productTypes }
  }, [cards])

  // Client-side filtering
  const filteredCards = useMemo(() => {
    if (!cards) return []
    return cards.filter((card) => {
      if (searchParams.rarity && card.rarity_name !== searchParams.rarity) return false
      if (searchParams.treatment && card.last_treatment !== searchParams.treatment) return false
      if (searchParams.set && card.set_name !== searchParams.set) return false
      if (searchParams.search) {
        const query = searchParams.search.toLowerCase()
        if (!card.name.toLowerCase().includes(query)) return false
      }
      return true
    })
  }, [cards, searchParams.rarity, searchParams.treatment, searchParams.set, searchParams.search])

  // Client-side sorting
  const sortedCards = useMemo(() => {
    const sorted = [...filteredCards]
    const direction = searchParams.dir === 'asc' ? 1 : -1

    switch (searchParams.sortBy || 'volume') {
      case 'price':
        return sorted.sort(
          (a, b) => direction * ((a.floor_price || a.latest_price || 0) - (b.floor_price || b.latest_price || 0))
        )
      case 'name':
        return sorted.sort((a, b) => direction * a.name.localeCompare(b.name))
      case 'volume':
      default:
        return sorted.sort((a, b) => -direction * ((a.volume ?? 0) - (b.volume ?? 0))) // Desc by default
    }
  }, [filteredCards, searchParams.sortBy, searchParams.dir])

  // Check if any filters are active
  const hasActiveFilters =
    searchParams.productType ||
    searchParams.rarity ||
    searchParams.treatment ||
    searchParams.set ||
    searchParams.search

  // Active filters for chips
  const activeFilters = [
    searchParams.productType && { key: 'productType', label: searchParams.productType },
    searchParams.rarity && { key: 'rarity', label: searchParams.rarity },
    searchParams.treatment && { key: 'treatment', label: searchParams.treatment },
    searchParams.set && { key: 'set', label: searchParams.set },
  ].filter(Boolean) as { key: string; label: string }[]

  // Count for mobile filter trigger badge
  const activeFilterCount = activeFilters.length

  // Build breadcrumbs based on active filters
  const breadcrumbItems = useMemo(() => {
    const items: Array<{ label: string; href?: string; current?: boolean }> = [
      { label: 'Home', href: '/' },
      { label: 'Browse', href: '/browse' },
    ]

    // Add current filter context to breadcrumb
    if (searchParams.productType) {
      items.push({ label: searchParams.productType, current: true })
    } else if (searchParams.rarity) {
      items.push({ label: `${searchParams.rarity} Cards`, current: true })
    } else {
      items[items.length - 1] = { ...items[items.length - 1], current: true }
    }

    return items
  }, [searchParams.productType, searchParams.rarity])

  return (
    <div className="min-h-screen bg-background text-foreground font-mono">
      <div className="max-w-[1800px] mx-auto p-4">
        {/* Breadcrumbs */}
        <Breadcrumbs items={breadcrumbItems} className="mb-2" />

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">Browse Cards</h1>
            <p className="text-sm text-muted-foreground">
              {isLoading ? 'Loading...' : `${sortedCards.length} results`}
            </p>
          </div>

          {/* Mobile filter trigger */}
          <div className="sm:hidden">
            <FilterTrigger
              onClick={() => setIsFilterDrawerOpen(true)}
              activeCount={activeFilterCount}
            />
          </div>
        </div>

        {/* Desktop Filter Bar - hidden on mobile */}
        <div className="hidden sm:flex flex-wrap items-center gap-3 mb-4">
          {/* Product Type */}
          <SimpleDropdown
            value={searchParams.productType || 'all'}
            onChange={(v) => updateSearch({ productType: v === 'all' ? undefined : v })}
            options={[
              { value: 'all', label: 'All Types' },
              ...filterOptions.productTypes.map((t) => ({ value: t.value, label: t.value, count: t.count })),
            ]}
            size="sm"
            className="w-auto"
            triggerClassName="rounded-full px-4"
            aria-label="Filter by product type"
          />

          {/* Rarity */}
          <SimpleDropdown
            value={searchParams.rarity || 'all'}
            onChange={(v) => updateSearch({ rarity: v === 'all' ? undefined : v })}
            options={[
              { value: 'all', label: 'All Rarities' },
              ...filterOptions.rarities.map((r) => ({ value: r.value, label: r.value, count: r.count })),
            ]}
            size="sm"
            className="w-auto"
            triggerClassName="rounded-full px-4"
            aria-label="Filter by rarity"
          />

          {/* Treatment */}
          <SimpleDropdown
            value={searchParams.treatment || 'all'}
            onChange={(v) => updateSearch({ treatment: v === 'all' ? undefined : v })}
            options={[
              { value: 'all', label: 'All Treatments' },
              ...filterOptions.treatments.map((t) => ({ value: t.value, label: t.value, count: t.count })),
            ]}
            size="sm"
            className="w-auto"
            triggerClassName="rounded-full px-4"
            aria-label="Filter by treatment"
          />

          {/* Set */}
          {filterOptions.sets.length > 1 && (
            <SimpleDropdown
              value={searchParams.set || 'all'}
              onChange={(v) => updateSearch({ set: v === 'all' ? undefined : v })}
              options={[
                { value: 'all', label: 'All Sets' },
                ...filterOptions.sets.map((s) => ({ value: s.value, label: s.value, count: s.count })),
              ]}
              size="sm"
              className="w-auto"
              triggerClassName="rounded-full px-4"
              aria-label="Filter by set"
            />
          )}

          {/* Sort */}
          <SimpleDropdown
            value={`${searchParams.sortBy || 'volume'}-${searchParams.dir || 'desc'}`}
            onChange={(v) => {
              const [sortBy, dir] = v.split('-') as [BrowseSearchParams['sortBy'], BrowseSearchParams['dir']]
              updateSearch({ sortBy, dir })
            }}
            options={[
              { value: 'volume-desc', label: 'Most Sales' },
              { value: 'volume-asc', label: 'Least Sales' },
              { value: 'price-asc', label: 'Price: Low to High' },
              { value: 'price-desc', label: 'Price: High to Low' },
              { value: 'name-asc', label: 'Name: A-Z' },
              { value: 'name-desc', label: 'Name: Z-A' },
            ]}
            size="sm"
            className="w-auto"
            triggerClassName="rounded-full px-4"
            aria-label="Sort results"
          />
        </div>

        {/* Mobile Filter Drawer */}
        <FilterDrawer
          isOpen={isFilterDrawerOpen}
          onClose={() => setIsFilterDrawerOpen(false)}
          title="Filters"
          footer={
            <div className="flex gap-3">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => {
                  clearAllFilters()
                  setIsFilterDrawerOpen(false)
                }}
              >
                Clear All
              </Button>
              <Button
                variant="primary"
                className="flex-1"
                onClick={() => setIsFilterDrawerOpen(false)}
              >
                Show {sortedCards.length} Results
              </Button>
            </div>
          }
        >
          {/* Product Type */}
          <FilterSection label="Product Type">
            <div className="flex flex-wrap gap-2">
              <FilterOption
                label="All"
                isSelected={!searchParams.productType}
                onClick={() => updateSearch({ productType: undefined })}
              />
              {filterOptions.productTypes.map((t) => (
                <FilterOption
                  key={t.value}
                  label={t.value}
                  count={t.count}
                  isSelected={searchParams.productType === t.value}
                  onClick={() => updateSearch({ productType: t.value })}
                />
              ))}
            </div>
          </FilterSection>

          {/* Rarity */}
          <FilterSection label="Rarity">
            <div className="flex flex-wrap gap-2">
              <FilterOption
                label="All"
                isSelected={!searchParams.rarity}
                onClick={() => updateSearch({ rarity: undefined })}
              />
              {filterOptions.rarities.map((r) => (
                <FilterOption
                  key={r.value}
                  label={r.value}
                  count={r.count}
                  isSelected={searchParams.rarity === r.value}
                  onClick={() => updateSearch({ rarity: r.value })}
                />
              ))}
            </div>
          </FilterSection>

          {/* Treatment */}
          <FilterSection label="Treatment">
            <div className="flex flex-wrap gap-2">
              <FilterOption
                label="All"
                isSelected={!searchParams.treatment}
                onClick={() => updateSearch({ treatment: undefined })}
              />
              {filterOptions.treatments.map((t) => (
                <FilterOption
                  key={t.value}
                  label={t.value}
                  count={t.count}
                  isSelected={searchParams.treatment === t.value}
                  onClick={() => updateSearch({ treatment: t.value })}
                />
              ))}
            </div>
          </FilterSection>

          {/* Set */}
          {filterOptions.sets.length > 1 && (
            <FilterSection label="Set">
              <div className="flex flex-wrap gap-2">
                <FilterOption
                  label="All"
                  isSelected={!searchParams.set}
                  onClick={() => updateSearch({ set: undefined })}
                />
                {filterOptions.sets.map((s) => (
                  <FilterOption
                    key={s.value}
                    label={s.value}
                    count={s.count}
                    isSelected={searchParams.set === s.value}
                    onClick={() => updateSearch({ set: s.value })}
                  />
                ))}
              </div>
            </FilterSection>
          )}

          {/* Sort */}
          <FilterSection label="Sort By">
            <div className="flex flex-wrap gap-2">
              {[
                { value: 'volume-desc', label: 'Most Sales' },
                { value: 'volume-asc', label: 'Least Sales' },
                { value: 'price-asc', label: 'Price: Low' },
                { value: 'price-desc', label: 'Price: High' },
                { value: 'name-asc', label: 'A-Z' },
                { value: 'name-desc', label: 'Z-A' },
              ].map((option) => (
                <FilterOption
                  key={option.value}
                  label={option.label}
                  isSelected={`${searchParams.sortBy || 'volume'}-${searchParams.dir || 'desc'}` === option.value}
                  onClick={() => {
                    const [sortBy, dir] = option.value.split('-') as [BrowseSearchParams['sortBy'], BrowseSearchParams['dir']]
                    updateSearch({ sortBy, dir })
                  }}
                />
              ))}
            </div>
          </FilterSection>
        </FilterDrawer>

        {/* Search Input */}
        <div className="relative mb-4">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" aria-hidden="true" />
          <input
            type="search"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search cards..."
            aria-label="Search cards"
            className={cn(
              'w-full pl-10 pr-10 py-3 rounded-full',
              'bg-card border border-border',
              'text-sm placeholder:text-muted-foreground',
              'focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent'
            )}
          />
          {searchInput && (
            <button
              onClick={() => {
                setSearchInput('')
                updateSearch({ search: undefined })
              }}
              className="absolute right-3 top-1/2 -translate-y-1/2 p-2 rounded-full hover:bg-muted"
              aria-label="Clear search"
            >
              <X className="w-4 h-4 text-muted-foreground" />
            </button>
          )}
        </div>

        {/* Active Filter Chips */}
        {hasActiveFilters && (
          <div className="flex flex-wrap items-center gap-2 mb-6">
            {activeFilters.map((filter) => (
              <button
                key={filter.key}
                onClick={() => updateSearch({ [filter.key]: undefined })}
                className={cn(
                  // Min 44px touch target for mobile
                  'flex items-center gap-1.5 px-4 py-2.5 min-h-[44px] rounded-full',
                  'bg-brand-500/10 border border-brand-500/30 text-brand-300',
                  'text-sm font-medium',
                  'hover:bg-brand-500/20 transition-colors',
                  'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500'
                )}
                aria-label={`Remove ${filter.label} filter`}
              >
                {filter.label}
                <X className="w-4 h-4" aria-hidden="true" />
              </button>
            ))}
            <button
              onClick={clearAllFilters}
              className={cn(
                'px-3 py-2 min-h-[44px] rounded-full',
                'text-sm text-muted-foreground hover:text-foreground transition-colors',
                'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500'
              )}
            >
              Clear all
            </button>
          </div>
        )}

        {/* Results Grid */}
        {isLoading ? (
          <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
            {Array.from({ length: 18 }).map((_, i) => (
              <ProductCardSkeleton key={i} />
            ))}
          </div>
        ) : sortedCards.length > 0 ? (
          <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
            {sortedCards.map((card) => (
              <ProductCard
                key={card.id}
                id={card.id}
                slug={card.slug}
                name={card.name}
                setName={card.set_name}
                price={card.floor_price || card.latest_price || undefined}
                listingsCount={card.inventory}
                imageUrl={card.image_url}
                rarity={card.rarity_name}
                productType={card.product_type}
              />
            ))}
          </div>
        ) : (
          /* Empty State */
          <div className="py-16 text-center">
            <Package className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">No cards found</h3>
            <p className="text-muted-foreground text-sm mb-4">
              Try adjusting your filters or search query
            </p>
            <button
              onClick={clearAllFilters}
              className="text-sm text-brand-400 hover:text-brand-300 transition-colors"
            >
              Clear all filters
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
