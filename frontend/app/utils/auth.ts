import ky from 'ky'

const API_URL = 'http://localhost:8000/api/v1'

export const api = ky.create({
  prefixUrl: API_URL,
  hooks: {
    beforeRequest: [
      request => {
        if (typeof window !== 'undefined') {
            const token = localStorage.getItem('token')
            if (token) {
            request.headers.set('Authorization', `Bearer ${token}`)
            }
        }
      },
    ],
  },
})

export const auth = {
  login: async (email: string, password: string) => {
    try {
        const res = await api.post('auth/login', {
        // OAuth2PasswordRequestForm expects form data, but FastAPI can handle JSON if configured or mapped
        // Actually OAuth2PasswordRequestForm expects form-data strictly by default in FastAPI.
        // Let's send form-data
        body: new URLSearchParams({ username: email, password }),
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        }).json<{ access_token: string }>()
        
        if (res.access_token) {
        localStorage.setItem('token', res.access_token)
        return true
        }
        return false
    } catch (e) {
        console.error(e)
        return false
    }
  },
  logout: () => {
    localStorage.removeItem('token')
    window.location.href = '/login'
  },
  isAuthenticated: () => {
      if (typeof window === 'undefined') return false
      return !!localStorage.getItem('token')
  }
}

