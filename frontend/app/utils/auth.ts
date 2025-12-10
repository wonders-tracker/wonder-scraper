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

export const api = ky.create({
  prefixUrl: API_URL,
  credentials: 'include', // Send cookies with requests
  hooks: {
    beforeRequest: [
      request => {
        if (typeof window !== 'undefined') {
          // Also send token from localStorage as fallback (for backwards compatibility)
          const token = localStorage.getItem('token')
          if (token) {
            request.headers.set('Authorization', `Bearer ${token}`)
          }
        }
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
      }).json<{ access_token: string }>()

      if (res.access_token) {
        // Store in localStorage as backup (cookie is set by server)
        localStorage.setItem('token', res.access_token)
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

  logout: async () => {
    try {
      // Call logout endpoint to clear cookie
      await api.post('auth/logout')
    } catch (e) {
      console.error('Logout error:', e)
    }
    // Clear localStorage
    localStorage.removeItem('token')
    // Notify app of auth state change
    notifyAuthChange()
    window.location.href = '/login'
  },

  isAuthenticated: () => {
    if (typeof window === 'undefined') return false
    // Check localStorage (cookie is httpOnly so can't check directly)
    return !!localStorage.getItem('token')
  },

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
      }>()
      return user
    } catch (e) {
      return null
    }
  },
}

