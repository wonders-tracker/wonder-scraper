import * as React from "react"

interface UseFocusTrapOptions {
  /** Whether the focus trap is active */
  enabled?: boolean
  /** Element to return focus to when trap is deactivated */
  returnFocusTo?: React.RefObject<HTMLElement>
  /** Callback when Escape is pressed */
  onEscape?: () => void
  /** Initial element to focus (selector or ref) */
  initialFocus?: string | React.RefObject<HTMLElement>
}

/**
 * Hook for creating accessible focus traps in modals and dialogs
 * Implements WAI-ARIA dialog pattern
 */
export function useFocusTrap<T extends HTMLElement = HTMLDivElement>(
  options: UseFocusTrapOptions = {}
): React.RefObject<T> {
  const { enabled = true, returnFocusTo, onEscape, initialFocus } = options
  const containerRef = React.useRef<T>(null)
  const previousActiveElement = React.useRef<Element | null>(null)

  React.useEffect(() => {
    if (!enabled) return

    // Store the previously focused element
    previousActiveElement.current = document.activeElement

    // Focus the initial element or first focusable
    const container = containerRef.current
    if (!container) return

    const focusInitial = () => {
      if (initialFocus) {
        if (typeof initialFocus === "string") {
          const element = container.querySelector<HTMLElement>(initialFocus)
          element?.focus()
        } else {
          initialFocus.current?.focus()
        }
      } else {
        // Focus first focusable element
        const firstFocusable = getFocusableElements(container)[0]
        firstFocusable?.focus()
      }
    }

    // Use requestAnimationFrame to ensure DOM is ready
    requestAnimationFrame(focusInitial)

    return () => {
      // Return focus to previous element
      const returnTo = returnFocusTo?.current || previousActiveElement.current
      if (returnTo && returnTo instanceof HTMLElement) {
        returnTo.focus()
      }
    }
  }, [enabled, initialFocus, returnFocusTo])

  React.useEffect(() => {
    if (!enabled) return

    const container = containerRef.current
    if (!container) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onEscape?.()
        return
      }

      if (e.key !== "Tab") return

      const focusableElements = getFocusableElements(container)
      if (focusableElements.length === 0) return

      const firstElement = focusableElements[0]
      const lastElement = focusableElements[focusableElements.length - 1]

      // Shift+Tab on first element -> go to last
      if (e.shiftKey && document.activeElement === firstElement) {
        e.preventDefault()
        lastElement.focus()
      }
      // Tab on last element -> go to first
      else if (!e.shiftKey && document.activeElement === lastElement) {
        e.preventDefault()
        firstElement.focus()
      }
    }

    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [enabled, onEscape])

  return containerRef
}

/**
 * Get all focusable elements within a container
 */
function getFocusableElements(container: HTMLElement): HTMLElement[] {
  const focusableSelector = [
    'a[href]',
    'button:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
  ].join(", ")

  return Array.from(container.querySelectorAll<HTMLElement>(focusableSelector)).filter(
    (el) => !el.hasAttribute("disabled") && el.offsetParent !== null
  )
}

/**
 * Hook to lock body scroll when modal is open
 */
export function useBodyScrollLock(locked: boolean) {
  React.useEffect(() => {
    if (!locked) return

    const originalStyle = window.getComputedStyle(document.body).overflow
    document.body.style.overflow = "hidden"

    return () => {
      document.body.style.overflow = originalStyle
    }
  }, [locked])
}

/**
 * Combined hook for modal accessibility
 * Includes focus trap, body scroll lock, and escape handling
 */
export function useModalAccessibility(
  isOpen: boolean,
  options: {
    onClose: () => void
    initialFocus?: string | React.RefObject<HTMLElement>
  }
) {
  const { onClose, initialFocus } = options

  useBodyScrollLock(isOpen)

  const containerRef = useFocusTrap({
    enabled: isOpen,
    onEscape: onClose,
    initialFocus,
  })

  const modalProps = React.useMemo(
    () => ({
      role: "dialog" as const,
      "aria-modal": true as const,
      tabIndex: -1,
    }),
    []
  )

  return {
    containerRef,
    modalProps,
  }
}
