/**
 * FilterDrawer - Mobile bottom sheet for filters
 *
 * A slide-up drawer for mobile filter UX. Uses a backdrop overlay
 * and supports both swipe-to-close and button close.
 */

import * as React from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/lib/utils'
import { X, SlidersHorizontal } from 'lucide-react'
import { Button } from './button'

interface FilterDrawerProps {
  isOpen: boolean
  onClose: () => void
  title?: string
  children: React.ReactNode
  /** Footer with apply/clear buttons */
  footer?: React.ReactNode
}

/**
 * Mobile filter drawer (bottom sheet)
 */
export function FilterDrawer({
  isOpen,
  onClose,
  title = 'Filters',
  children,
  footer,
}: FilterDrawerProps) {
  const drawerRef = React.useRef<HTMLDivElement>(null)

  // Lock body scroll when open
  React.useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])

  // Close on escape key
  React.useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [isOpen, onClose])

  // Focus trap
  React.useEffect(() => {
    if (isOpen && drawerRef.current) {
      const focusable = drawerRef.current.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      )
      const first = focusable[0] as HTMLElement
      const last = focusable[focusable.length - 1] as HTMLElement

      const handleTab = (e: KeyboardEvent) => {
        if (e.key !== 'Tab') return

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last?.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first?.focus()
        }
      }

      document.addEventListener('keydown', handleTab)
      first?.focus()

      return () => document.removeEventListener('keydown', handleTab)
    }
  }, [isOpen])

  if (typeof window === 'undefined') return null

  return createPortal(
    <>
      {/* Backdrop */}
      <div
        className={cn(
          'fixed inset-0 bg-black/60 z-40 transition-opacity duration-300',
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        )}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <div
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          'fixed inset-x-0 bottom-0 z-50',
          'bg-card border-t border-border rounded-t-2xl',
          'transition-transform duration-300 ease-out',
          'max-h-[85vh] flex flex-col',
          isOpen ? 'translate-y-0' : 'translate-y-full'
        )}
      >
        {/* Drag handle */}
        <div className="flex justify-center pt-3 pb-2">
          <div className="w-10 h-1 bg-muted-foreground/30 rounded-full" />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-4 pb-3 border-b border-border">
          <h2 className="text-lg font-semibold text-foreground">{title}</h2>
          <button
            onClick={onClose}
            className={cn(
              'p-2 -mr-2 rounded-lg',
              'hover:bg-muted transition-colors',
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500'
            )}
            aria-label="Close filters"
          >
            <X className="w-5 h-5 text-muted-foreground" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">{children}</div>

        {/* Footer */}
        {footer && (
          <div className="p-4 border-t border-border bg-card">{footer}</div>
        )}
      </div>
    </>,
    document.body
  )
}

/**
 * Filter section within the drawer
 */
export function FilterSection({
  label,
  children,
  className,
}: {
  label: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn('space-y-2', className)}>
      <label className="text-sm font-medium text-foreground">{label}</label>
      {children}
    </div>
  )
}

/**
 * Filter option button (pill style)
 * Uses minimum 44px touch target for mobile accessibility
 */
export function FilterOption({
  label,
  count,
  isSelected,
  onClick,
}: {
  label: string
  count?: number
  isSelected: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        // Minimum 44px touch target (Apple HIG / WCAG recommendation)
        'min-h-[44px] px-4 py-2.5 rounded-lg text-sm font-medium transition-colors',
        'border focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500',
        isSelected
          ? 'bg-brand-500/20 border-brand-500/50 text-brand-300'
          : 'bg-card border-border text-muted-foreground hover:border-brand-500/30 hover:text-foreground'
      )}
      aria-pressed={isSelected}
    >
      {label}
      {count !== undefined && (
        <span
          className={cn(
            'ml-1.5 text-xs',
            isSelected ? 'text-brand-400' : 'text-muted-foreground/70'
          )}
        >
          ({count})
        </span>
      )}
    </button>
  )
}

/**
 * Mobile filter trigger button
 */
export function FilterTrigger({
  onClick,
  activeCount = 0,
  className,
}: {
  onClick: () => void
  activeCount?: number
  className?: string
}) {
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={onClick}
      className={cn('gap-2', className)}
      aria-label={`Open filters${activeCount > 0 ? `, ${activeCount} active` : ''}`}
    >
      <SlidersHorizontal className="w-4 h-4" />
      Filters
      {activeCount > 0 && (
        <span className="min-w-[20px] h-5 px-1.5 rounded-full bg-brand-500 text-white text-xs font-bold flex items-center justify-center">
          {activeCount}
        </span>
      )}
    </Button>
  )
}
