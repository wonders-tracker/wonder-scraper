import { useState, useRef, useEffect, ReactNode } from 'react'
import { createPortal } from 'react-dom'

interface TooltipProps {
  content: ReactNode
  children: ReactNode
  position?: 'top' | 'bottom' | 'left' | 'right'
  delay?: number
  className?: string
}

export function Tooltip({
  content,
  children,
  position = 'top',
  delay = 200,
  className = '',
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false)
  const [coords, setCoords] = useState({ x: 0, y: 0 })
  const triggerRef = useRef<HTMLSpanElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)

  const updatePosition = () => {
    if (!triggerRef.current) return

    const rect = triggerRef.current.getBoundingClientRect()
    let x = rect.left + rect.width / 2
    let y = rect.top

    switch (position) {
      case 'bottom':
        y = rect.bottom + 8
        break
      case 'left':
        x = rect.left - 8
        y = rect.top + rect.height / 2
        break
      case 'right':
        x = rect.right + 8
        y = rect.top + rect.height / 2
        break
      case 'top':
      default:
        y = rect.top - 8
        break
    }

    setCoords({ x, y })
  }

  const showTooltip = () => {
    timeoutRef.current = setTimeout(() => {
      updatePosition()
      setIsVisible(true)
    }, delay)
  }

  const hideTooltip = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
    setIsVisible(false)
  }

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [])

  // Hide tooltip on scroll
  useEffect(() => {
    if (!isVisible) return

    const handleScroll = () => {
      hideTooltip()
    }

    window.addEventListener('scroll', handleScroll, true)
    return () => window.removeEventListener('scroll', handleScroll, true)
  }, [isVisible])

  // Adjust position if tooltip would go off screen
  useEffect(() => {
    if (isVisible && tooltipRef.current) {
      const tooltip = tooltipRef.current
      const rect = tooltip.getBoundingClientRect()

      let newX = coords.x
      let newY = coords.y

      // Keep tooltip within viewport
      if (rect.right > window.innerWidth - 10) {
        newX = window.innerWidth - rect.width - 10
      }
      if (rect.left < 10) {
        newX = rect.width / 2 + 10
      }
      if (rect.bottom > window.innerHeight - 10) {
        newY = window.innerHeight - rect.height - 10
      }
      if (rect.top < 10) {
        newY = rect.height + 10
      }

      if (newX !== coords.x || newY !== coords.y) {
        setCoords({ x: newX, y: newY })
      }
    }
  }, [isVisible, coords])

  const getPositionStyles = (): React.CSSProperties => {
    const base: React.CSSProperties = {
      position: 'fixed',
      zIndex: 9999,
      left: coords.x,
      top: coords.y,
    }

    switch (position) {
      case 'bottom':
        return { ...base, transform: 'translateX(-50%)' }
      case 'left':
        return { ...base, transform: 'translate(-100%, -50%)' }
      case 'right':
        return { ...base, transform: 'translateY(-50%)' }
      case 'top':
      default:
        return { ...base, transform: 'translate(-50%, -100%)' }
    }
  }

  const tooltipElement = isVisible && typeof document !== 'undefined' ? createPortal(
    <div
      ref={tooltipRef}
      style={getPositionStyles()}
      className={`px-2 py-1 text-xs font-medium bg-zinc-900 text-zinc-100 rounded border border-zinc-700 shadow-lg whitespace-pre-line pointer-events-none animate-in fade-in-0 zoom-in-95 duration-100 ${className}`}
      role="tooltip"
    >
      {content}
    </div>,
    document.body
  ) : null

  return (
    <>
      <span
        ref={triggerRef}
        onMouseEnter={showTooltip}
        onMouseLeave={hideTooltip}
        onFocus={showTooltip}
        onBlur={hideTooltip}
        className="inline-flex"
      >
        {children}
      </span>
      {tooltipElement}
    </>
  )
}

export default Tooltip
