import { useEffect, useRef } from 'react'
import { useLocation } from '@tanstack/react-router'
import { api } from '../utils/auth'

// Generate or get session ID using cryptographically secure randomness
function getSessionId(): string {
  if (typeof window === 'undefined') return ''

  let sessionId = sessionStorage.getItem('wt_session_id')
  if (!sessionId) {
    // Use crypto.randomUUID for secure random session IDs
    sessionId = crypto.randomUUID()
    sessionStorage.setItem('wt_session_id', sessionId)
  }
  return sessionId
}

export function usePageTracking() {
  const location = useLocation()
  const lastPathRef = useRef<string>('')

  useEffect(() => {
    // Don't track the same path twice in a row
    if (location.pathname === lastPathRef.current) return
    lastPathRef.current = location.pathname

    // Track page view
    const trackPageView = async () => {
      try {
        await api.post('analytics/pageview', {
          json: {
            path: location.pathname,
            referrer: document.referrer || null,
            session_id: getSessionId(),
          },
        })
      } catch (e) {
        // Silently fail - analytics shouldn't break the app
        console.debug('[Analytics] Failed to track page view:', e)
      }
    }

    trackPageView()
  }, [location.pathname])
}
