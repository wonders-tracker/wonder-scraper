/**
 * PriceAlertModal - Modal for setting price alerts on cards
 *
 * Allows users to set target prices and get notified when
 * the price drops below or rises above their target.
 *
 * @see tasks.json
 */

import { useState, useCallback, useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'
import { Button } from '../ui/button'
import {
  X,
  Bell,
  TrendingDown,
  TrendingUp,
  Check,
  AlertCircle
} from 'lucide-react'

export type PriceAlertType = 'below' | 'above'

export type PriceAlertModalProps = {
  isOpen: boolean
  onClose: () => void
  cardId: number
  cardName: string
  currentPrice?: number
  onCreateAlert: (alert: {
    cardId: number
    targetPrice: number
    alertType: PriceAlertType
  }) => Promise<void>
  /** Whether the create action is in progress */
  isCreating?: boolean
}

export function PriceAlertModal({
  isOpen,
  onClose,
  cardId,
  cardName,
  currentPrice,
  onCreateAlert,
  isCreating = false
}: PriceAlertModalProps) {
  const [alertType, setAlertType] = useState<PriceAlertType>('below')
  const [targetPrice, setTargetPrice] = useState<string>('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const modalRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Focus input when modal opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus()
      // Pre-fill with suggested price based on alert type
      if (currentPrice) {
        const suggested = alertType === 'below'
          ? (currentPrice * 0.9).toFixed(2) // 10% below current
          : (currentPrice * 1.1).toFixed(2) // 10% above current
        setTargetPrice(suggested)
      }
    }
  }, [isOpen, alertType, currentPrice])

  // Handle escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [isOpen, onClose])

  // Focus trap
  useEffect(() => {
    if (!isOpen) return

    const modal = modalRef.current
    if (!modal) return

    const focusableElements = modal.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
    const firstElement = focusableElements[0]
    const lastElement = focusableElements[focusableElements.length - 1]

    const handleTab = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return

      if (e.shiftKey) {
        if (document.activeElement === firstElement) {
          e.preventDefault()
          lastElement?.focus()
        }
      } else {
        if (document.activeElement === lastElement) {
          e.preventDefault()
          firstElement?.focus()
        }
      }
    }

    document.addEventListener('keydown', handleTab)
    return () => document.removeEventListener('keydown', handleTab)
  }, [isOpen])

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setError(null)
      setSuccess(false)
    }
  }, [isOpen])

  const handleSubmit = useCallback(async () => {
    setError(null)

    const price = parseFloat(targetPrice)
    if (isNaN(price) || price <= 0) {
      setError('Please enter a valid price')
      return
    }

    if (alertType === 'below' && currentPrice && price >= currentPrice) {
      setError(`Target price should be below current price ($${currentPrice.toFixed(2)})`)
      return
    }

    if (alertType === 'above' && currentPrice && price <= currentPrice) {
      setError(`Target price should be above current price ($${currentPrice.toFixed(2)})`)
      return
    }

    try {
      await onCreateAlert({
        cardId,
        targetPrice: price,
        alertType
      })
      setSuccess(true)
      setTimeout(() => {
        onClose()
      }, 1500)
    } catch (err) {
      setError('Failed to create alert. Please try again.')
    }
  }, [targetPrice, alertType, currentPrice, cardId, onCreateAlert, onClose])

  if (!isOpen) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 animate-in fade-in duration-200"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="price-alert-title"
        className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-md bg-card border border-border rounded-lg shadow-xl animate-in zoom-in-95 fade-in duration-200"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Bell className="w-5 h-5 text-brand-300" />
            <h2 id="price-alert-title" className="text-lg font-bold">
              Set Price Alert
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-muted transition-colors"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {/* Card Info */}
          <div className="text-sm">
            <span className="text-muted-foreground">Alert for: </span>
            <span className="font-medium">{cardName}</span>
            {currentPrice && (
              <span className="text-muted-foreground ml-2">
                (Current: ${currentPrice.toFixed(2)})
              </span>
            )}
          </div>

          {/* Alert Type Toggle */}
          <div>
            <label className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium mb-2 block">
              Alert me when price goes
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setAlertType('below')}
                className={cn(
                  "flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded border transition-all",
                  alertType === 'below'
                    ? "bg-green-500/10 border-green-500/50 text-green-400"
                    : "border-border hover:border-muted-foreground/50"
                )}
              >
                <TrendingDown className="w-4 h-4" />
                Below
              </button>
              <button
                type="button"
                onClick={() => setAlertType('above')}
                className={cn(
                  "flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded border transition-all",
                  alertType === 'above'
                    ? "bg-amber-500/10 border-amber-500/50 text-amber-400"
                    : "border-border hover:border-muted-foreground/50"
                )}
              >
                <TrendingUp className="w-4 h-4" />
                Above
              </button>
            </div>
          </div>

          {/* Target Price Input */}
          <div>
            <label
              htmlFor="target-price"
              className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium mb-2 block"
            >
              Target Price
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                $
              </span>
              <input
                ref={inputRef}
                id="target-price"
                type="number"
                step="0.01"
                min="0"
                value={targetPrice}
                onChange={(e) => setTargetPrice(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleSubmit()
                  }
                }}
                className="w-full pl-7 pr-4 py-2.5 bg-muted/30 border border-border rounded font-mono text-lg focus:outline-none focus:ring-2 focus:ring-brand-300/50 focus:border-brand-300"
                placeholder="0.00"
              />
            </div>
            {currentPrice && (
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  onClick={() => setTargetPrice((currentPrice * 0.9).toFixed(2))}
                  className="text-xs text-muted-foreground hover:text-foreground px-2 py-1 rounded bg-muted/30 hover:bg-muted/50 transition-colors"
                >
                  -10%
                </button>
                <button
                  type="button"
                  onClick={() => setTargetPrice((currentPrice * 0.8).toFixed(2))}
                  className="text-xs text-muted-foreground hover:text-foreground px-2 py-1 rounded bg-muted/30 hover:bg-muted/50 transition-colors"
                >
                  -20%
                </button>
                <button
                  type="button"
                  onClick={() => setTargetPrice((currentPrice * 0.75).toFixed(2))}
                  className="text-xs text-muted-foreground hover:text-foreground px-2 py-1 rounded bg-muted/30 hover:bg-muted/50 transition-colors"
                >
                  -25%
                </button>
              </div>
            )}
          </div>

          {/* Error Message */}
          {error && (
            <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded p-3">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}

          {/* Success Message */}
          {success && (
            <div className="flex items-center gap-2 text-sm text-green-400 bg-green-500/10 border border-green-500/20 rounded p-3">
              <Check className="w-4 h-4 flex-shrink-0" />
              Alert created! You'll be notified when the price {alertType === 'below' ? 'drops below' : 'rises above'} ${targetPrice}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-border flex gap-2">
          <Button
            variant="outline"
            className="flex-1"
            onClick={onClose}
            disabled={isCreating}
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            className="flex-1"
            onClick={handleSubmit}
            disabled={isCreating || success || !targetPrice}
            leftIcon={success ? <Check className="w-4 h-4" /> : <Bell className="w-4 h-4" />}
          >
            {isCreating ? 'Creating...' : success ? 'Created!' : 'Create Alert'}
          </Button>
        </div>
      </div>
    </>
  )
}
