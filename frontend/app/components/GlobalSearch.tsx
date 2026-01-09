/**
 * GlobalSearch - Autocomplete search component for navigation
 *
 * Features:
 * - Debounced search query (300ms)
 * - Dropdown with card results
 * - Keyboard navigation (up/down arrows, enter to select)
 * - Click outside to close
 * - Shows card name, set, and floor price
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { api } from '../utils/auth'
import { SearchIcon } from './ui/search'
import clsx from 'clsx'

type SearchResult = {
  id: number
  slug?: string
  name: string
  set_name: string
  floor_price?: number
  image_url?: string
  rarity_name?: string
}

type GlobalSearchProps = {
  /** Placeholder text */
  placeholder?: string
  /** Additional className for the container */
  className?: string
  /** Callback when search is submitted or result selected */
  onSelect?: () => void
  /** Size variant */
  size?: 'sm' | 'md'
}

export function GlobalSearch({
  placeholder = "Search cards...",
  className,
  onSelect,
  size = 'md'
}: GlobalSearchProps) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Debounce search query
  useEffect(() => {
    if (!query || query.length < 2) {
      setDebouncedQuery('')
      return
    }
    const timer = setTimeout(() => {
      setDebouncedQuery(query)
    }, 300)
    return () => clearTimeout(timer)
  }, [query])

  // Fetch search results
  const { data: results, isLoading } = useQuery({
    queryKey: ['search', debouncedQuery],
    queryFn: async () => {
      const data = await api.get(`cards?search=${encodeURIComponent(debouncedQuery)}&limit=8&slim=true`).json<SearchResult[]>()
      return data
    },
    enabled: debouncedQuery.length >= 2,
    staleTime: 30 * 1000, // 30 seconds
  })

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Handle keyboard navigation
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!isOpen || !results?.length) return

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setSelectedIndex(prev => (prev + 1) % results.length)
        break
      case 'ArrowUp':
        e.preventDefault()
        setSelectedIndex(prev => (prev - 1 + results.length) % results.length)
        break
      case 'Enter':
        e.preventDefault()
        if (results[selectedIndex]) {
          handleSelect(results[selectedIndex])
        }
        break
      case 'Escape':
        setIsOpen(false)
        inputRef.current?.blur()
        break
    }
  }, [isOpen, results, selectedIndex])

  // Handle result selection
  const handleSelect = (card: SearchResult) => {
    navigate({
      to: '/cards/$cardId',
      params: { cardId: card.slug || String(card.id) }
    })
    setQuery('')
    setIsOpen(false)
    onSelect?.()
  }

  // Show dropdown when there's a query and results
  useEffect(() => {
    if (debouncedQuery.length >= 2) {
      setIsOpen(true)
      setSelectedIndex(0)
    } else {
      setIsOpen(false)
    }
  }, [debouncedQuery])

  const showDropdown = isOpen && (results?.length || isLoading)

  return (
    <div ref={containerRef} className={clsx("relative", className)}>
      {/* Search Input */}
      <div className="relative">
        <SearchIcon
          size={size === 'sm' ? 14 : 16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"
        />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => debouncedQuery.length >= 2 && setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className={clsx(
            "w-full bg-muted/50 pl-10 pr-4 rounded-full border border-border text-sm",
            "focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary",
            "placeholder:text-muted-foreground/60",
            size === 'sm' ? 'h-9' : 'h-10'
          )}
        />
      </div>

      {/* Results Dropdown */}
      {showDropdown && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-popover border border-border rounded-lg shadow-lg z-[100] overflow-hidden">
          {isLoading ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              Searching...
            </div>
          ) : results?.length ? (
            <div className="max-h-[320px] overflow-y-auto">
              {results.map((card, index) => (
                <button
                  key={card.id}
                  onClick={() => handleSelect(card)}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={clsx(
                    "w-full flex items-center gap-3 px-3 py-2 text-left transition-colors",
                    index === selectedIndex ? "bg-muted" : "hover:bg-muted/50"
                  )}
                >
                  {/* Card thumbnail */}
                  {card.image_url ? (
                    <img
                      src={card.image_url}
                      alt={card.name}
                      className="w-8 h-11 object-cover rounded border border-border"
                    />
                  ) : (
                    <div className="w-8 h-11 bg-muted rounded border border-border flex items-center justify-center">
                      <span className="text-[8px] text-muted-foreground">IMG</span>
                    </div>
                  )}

                  {/* Card info */}
                  <div className="flex-1 min-w-0">
                    <div className="font-bold text-sm truncate">{card.name}</div>
                    <div className="text-xs text-muted-foreground truncate">
                      {card.set_name}
                      {card.rarity_name && (
                        <span className="ml-1 text-primary">· {card.rarity_name}</span>
                      )}
                    </div>
                  </div>

                  {/* Price */}
                  {card.floor_price != null && (
                    <div className="text-sm font-mono font-bold text-brand-300">
                      ${card.floor_price.toFixed(2)}
                    </div>
                  )}
                </button>
              ))}
            </div>
          ) : debouncedQuery.length >= 2 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              No cards found for "{debouncedQuery}"
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}

export default GlobalSearch
