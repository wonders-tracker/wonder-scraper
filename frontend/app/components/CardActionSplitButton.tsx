import { useState, useEffect } from 'react'
import { api, auth } from '../utils/auth'

interface CardActionSplitButtonProps {
  cardId: number
  cardName: string
  onAddToPortfolio: () => void
  className?: string
}

export function CardActionSplitButton({
  cardId,
  cardName,
  onAddToPortfolio,
  className = ''
}: CardActionSplitButtonProps) {
  const isLoggedIn = auth.isAuthenticated()
  const [isWatching, setIsWatching] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [showTooltip, setShowTooltip] = useState<'portfolio' | 'alert' | null>(null)
  const [alertAnimation, setAlertAnimation] = useState(false)
  const [portfolioAnimation, setPortfolioAnimation] = useState(false)

  // Check if user is watching this card on mount
  useEffect(() => {
    if (isLoggedIn) {
      checkWatchStatus()
    }
  }, [isLoggedIn, cardId])

  const checkWatchStatus = async () => {
    try {
      const data = await api.get(`watchlist/${cardId}`).json<{ id: number } | null>()
      setIsWatching(data !== null)
    } catch (error) {
      // 404 means not watching, which is fine
      setIsWatching(false)
    }
  }

  const handleToggleWatch = async () => {
    if (!isLoggedIn) {
      window.location.href = '/login'
      return
    }

    setIsLoading(true)
    setAlertAnimation(true)

    try {
      const data = await api.post(`watchlist/${cardId}/toggle`).json<{ watching: boolean }>()
      setIsWatching(data.watching)
    } catch (error) {
      console.error('Failed to toggle watch:', error)
    } finally {
      setIsLoading(false)
      setTimeout(() => setAlertAnimation(false), 300)
    }
  }

  const handleAddToPortfolio = () => {
    if (!isLoggedIn) {
      window.location.href = '/login'
      return
    }

    setPortfolioAnimation(true)
    setTimeout(() => setPortfolioAnimation(false), 300)
    onAddToPortfolio()
  }

  return (
    <div className={`inline-flex rounded-md shadow-sm ${className}`}>
      {/* Add to Portfolio Button */}
      <button
        onClick={handleAddToPortfolio}
        onMouseEnter={() => setShowTooltip('portfolio')}
        onMouseLeave={() => setShowTooltip(null)}
        className={`
          relative inline-flex items-center justify-center
          px-3 py-2 rounded-l-md
          bg-zinc-800 hover:bg-zinc-700
          border border-r-0 border-zinc-700
          text-zinc-200 hover:text-white
          transition-all duration-200
          focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:ring-offset-2 focus:ring-offset-zinc-900
          ${portfolioAnimation ? 'scale-95' : 'scale-100'}
        `}
      >
        {/* Portfolio Icon */}
        <svg
          className={`w-5 h-5 transition-transform duration-200 ${portfolioAnimation ? 'scale-110' : ''}`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M12 5v14" />
          <path d="M5 12h14" />
        </svg>

        {/* Tooltip - positioned below */}
        {showTooltip === 'portfolio' && (
          <div className="absolute top-full mt-2 left-1/2 -translate-x-1/2 px-2 py-1 bg-zinc-900 text-xs text-zinc-300 rounded whitespace-nowrap border border-zinc-700 shadow-lg z-50">
            Add to Portfolio
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-b-4 border-transparent border-b-zinc-700" />
          </div>
        )}
      </button>

      {/* Divider */}
      <div className="w-px bg-zinc-600" />

      {/* Alert / Watch Button */}
      <button
        onClick={handleToggleWatch}
        onMouseEnter={() => setShowTooltip('alert')}
        onMouseLeave={() => setShowTooltip(null)}
        disabled={isLoading}
        className={`
          relative inline-flex items-center justify-center
          px-3 py-2 rounded-r-md
          border border-l-0 border-zinc-700
          transition-all duration-200
          focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-zinc-900
          ${isWatching
            ? 'bg-amber-600 hover:bg-amber-500 text-white focus:ring-amber-500'
            : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-200 hover:text-white focus:ring-zinc-500'
          }
          ${alertAnimation ? 'scale-95' : 'scale-100'}
          ${isLoading ? 'opacity-50 cursor-wait' : ''}
        `}
      >
        {/* Bell Icon */}
        <svg
          className={`
            w-5 h-5 transition-all duration-200
            ${alertAnimation ? 'animate-ring' : ''}
            ${isWatching ? 'fill-current' : ''}
          `}
          viewBox="0 0 24 24"
          fill={isWatching ? 'currentColor' : 'none'}
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
          {isWatching && (
            <circle cx="18" cy="4" r="3" fill="#ef4444" stroke="none" />
          )}
        </svg>

        {/* Tooltip - positioned below */}
        {showTooltip === 'alert' && (
          <div className="absolute top-full mt-2 left-1/2 -translate-x-1/2 px-2 py-1 bg-zinc-900 text-xs text-zinc-300 rounded whitespace-nowrap border border-zinc-700 shadow-lg z-50">
            {isWatching ? 'Remove Alert' : 'Set Price Alert'}
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-b-4 border-transparent border-b-zinc-700" />
          </div>
        )}
      </button>

      {/* Custom keyframes for bell animation */}
      <style>{`
        @keyframes ring {
          0% { transform: rotate(0deg); }
          10% { transform: rotate(15deg); }
          20% { transform: rotate(-15deg); }
          30% { transform: rotate(10deg); }
          40% { transform: rotate(-10deg); }
          50% { transform: rotate(5deg); }
          60% { transform: rotate(-5deg); }
          70% { transform: rotate(0deg); }
          100% { transform: rotate(0deg); }
        }
        .animate-ring {
          animation: ring 0.5s ease-in-out;
        }
      `}</style>
    </div>
  )
}

// Compact variant for table rows / smaller spaces
export function CardActionSplitButtonCompact({
  cardId,
  cardName,
  onAddToPortfolio,
  className = ''
}: CardActionSplitButtonProps) {
  const isLoggedIn = auth.isAuthenticated()
  const [isWatching, setIsWatching] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [showRipple, setShowRipple] = useState<'portfolio' | 'alert' | null>(null)

  useEffect(() => {
    if (isLoggedIn) {
      api.get(`watchlist/${cardId}`).json<{ id: number } | null>()
        .then(data => setIsWatching(data !== null))
        .catch(() => setIsWatching(false))
    }
  }, [isLoggedIn, cardId])

  const handleToggleWatch = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!isLoggedIn) {
      window.location.href = '/login'
      return
    }

    setIsLoading(true)
    setShowRipple('alert')

    try {
      const data = await api.post(`watchlist/${cardId}/toggle`).json<{ watching: boolean }>()
      setIsWatching(data.watching)
    } catch (error) {
      console.error('Failed to toggle watch:', error)
    } finally {
      setIsLoading(false)
      setTimeout(() => setShowRipple(null), 200)
    }
  }

  const handleAddToPortfolio = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!isLoggedIn) {
      window.location.href = '/login'
      return
    }
    setShowRipple('portfolio')
    setTimeout(() => setShowRipple(null), 200)
    onAddToPortfolio()
  }

  return (
    <div className={`inline-flex gap-1 ${className}`}>
      {/* Add to Portfolio - Compact */}
      <button
        onClick={handleAddToPortfolio}
        className={`
          p-1.5 rounded
          bg-zinc-800/50 hover:bg-zinc-700
          text-zinc-400 hover:text-white
          transition-all duration-150
          ${showRipple === 'portfolio' ? 'scale-90 bg-zinc-600' : ''}
        `}
        title="Add to Portfolio"
      >
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 5v14M5 12h14" />
        </svg>
      </button>

      {/* Watch / Alert - Compact */}
      <button
        onClick={handleToggleWatch}
        disabled={isLoading}
        className={`
          p-1.5 rounded
          transition-all duration-150
          ${isWatching
            ? 'bg-amber-600/80 hover:bg-amber-500 text-white'
            : 'bg-zinc-800/50 hover:bg-zinc-700 text-zinc-400 hover:text-white'
          }
          ${showRipple === 'alert' ? 'scale-90' : ''}
          ${isLoading ? 'opacity-50' : ''}
        `}
        title={isWatching ? 'Watching - Click to remove' : 'Add to Watchlist'}
      >
        <svg
          className="w-4 h-4"
          viewBox="0 0 24 24"
          fill={isWatching ? 'currentColor' : 'none'}
          stroke="currentColor"
          strokeWidth="2"
        >
          <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
      </button>
    </div>
  )
}
