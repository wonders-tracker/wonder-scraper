import ky from 'ky'

// Use relative URL in production (proxied by Vercel), absolute in dev
const getApiUrl = () => {
  // If env var is set, use it
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL
  }
  // In production (wonderstracker.com), use relative URL for Vercel proxy
  if (typeof window !== 'undefined' && window.location.hostname === 'wonderstracker.com') {
    return '/api/v1'
  }
  // Local development fallback
  return 'http://localhost:8000/api/v1'
}

const API_URL = getApiUrl()

// Track if we're currently refreshing to prevent multiple simultaneous refreshes
let isRefreshing = false
let refreshPromise: Promise<boolean> | null = null

/**
 * Attempt to refresh the access token using the refresh token cookie.
 * Returns true if refresh succeeded, false otherwise.
 */
async function refreshAccessToken(): Promise<boolean> {
  // If already refreshing, wait for that to complete
  if (isRefreshing && refreshPromise) {
    return refreshPromise
  }

  isRefreshing = true
  refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_URL}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
      })
      return response.ok
    } catch {
      return false
    } finally {
      isRefreshing = false
      refreshPromise = null
    }
  })()

  return refreshPromise
}

export const api = ky.create({
  prefixUrl: API_URL,
  credentials: 'include', // Send cookies with requests
  hooks: {
    afterResponse: [
      async (request, options, response) => {
        // If we get a 401, try to refresh the token
        if (response.status === 401) {
          const refreshed = await refreshAccessToken()
          if (refreshed) {
            // Retry the original request
            return ky(request, options)
          }
          // Refresh failed - user needs to login
          notifyAuthChange()
        }
        return response
      },
    ],
  },
})

// Helper to notify app of auth state changes
const notifyAuthChange = () => {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event('auth-change'))
  }
}

export const auth = {
  login: async (email: string, password: string) => {
    try {
      const res = await api.post('auth/login', {
        body: new URLSearchParams({ username: email, password }),
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }).json<{ access_token: string; expires_in: number }>()

      if (res.access_token) {
        // Notify app of auth state change
        notifyAuthChange()
        return true
      }
      return false
    } catch (e) {
      console.error(e)
      return false
    }
  },

  logout: async (queryClient?: { clear: () => void }) => {
    try {
      // Call logout endpoint to clear cookies
      await api.post('auth/logout')
    } catch (e) {
      console.error('Logout error:', e)
    }
    // Clear ALL cached queries to prevent data leakage between users
    if (queryClient) {
      queryClient.clear()
    }
    // Notify app of auth state change
    notifyAuthChange()
    window.location.href = '/login'
  },

  /**
   * Check if user might be authenticated.
   * Since cookies are httpOnly, we can't check directly.
   * This is a hint based on whether /me succeeds.
   */
  isAuthenticated: async (): Promise<boolean> => {
    try {
      await api.get('auth/me')
      return true
    } catch {
      return false
    }
  },

  /**
   * Refresh the access token.
   * Called automatically on 401, but can be called manually.
   */
  refreshToken: refreshAccessToken,

  // Get current user from API (verifies token is still valid)
  getCurrentUser: async () => {
    try {
      const user = await api.get('auth/me').json<{
        id: number
        email: string
        username?: string
        discord_handle?: string
        is_active: boolean
        onboarding_completed: boolean
        subscription_tier?: string
        is_pro?: boolean
      }>()
      return user
    } catch (e) {
      return null
    }
  },
}
