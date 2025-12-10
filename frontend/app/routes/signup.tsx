import { createFileRoute, Link } from '@tanstack/react-router'
import { useState, useEffect } from 'react'
import { api } from '~/utils/auth'
import { analytics } from '~/services/analytics'
import { LogIn, AlertCircle } from 'lucide-react'

export const Route = createFileRoute('/signup')({
  component: Signup,
})

function Signup() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // Track signup page view
  useEffect(() => {
    analytics.trackSignupPageView()
  }, [])

  const handleDiscordSignup = async () => {
    try {
      analytics.trackDiscordSignupInitiated()
      const res = await api.get('auth/discord/login').json<{ url: string }>()
      window.location.href = res.url
    } catch {
      setError('Failed to initiate Discord signup')
    }
  }

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    // Validation
    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }

    setLoading(true)

    try {
      // Register user
      await api.post('auth/register', {
        json: { email, password }
      }).json()

      // Auto-login after signup
      const loginRes = await api.post('auth/login', {
        body: new URLSearchParams({ username: email, password }),
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }).json<{ access_token: string }>()

      if (loginRes.access_token) {
        localStorage.setItem('token', loginRes.access_token)
        analytics.trackSignup('email')
        // New users go to onboarding
        window.location.href = '/welcome'
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create account. Please try again.'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4 font-mono">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-white mb-4">
            <span className="text-4xl font-bold text-black">W</span>
          </div>
          <h1 className="text-3xl font-bold uppercase tracking-tight mb-2">Create Account</h1>
          <p className="text-muted-foreground text-sm">Join WondersTracker to track your collection</p>
        </div>

        {/* Signup Form */}
        <div className="bg-card border border-border rounded-lg p-6">
          {error && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/50 rounded flex items-start gap-2 text-sm text-red-500">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Discord Button */}
          <button
            onClick={handleDiscordSignup}
            type="button"
            className="w-full flex justify-center items-center gap-2 rounded-md bg-[#5865F2] px-3 py-2.5 text-sm font-semibold text-white hover:bg-[#4752C4] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#5865F2] transition-colors"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037 3.903 3.903 0 0 0-.94 1.933 18.37 18.37 0 0 0-4.814 0 3.902 3.902 0 0 0-.94-1.933.074.074 0 0 0-.079-.037 19.79 19.79 0 0 0-4.885 1.515.074.074 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.118.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.074.074 0 0 0-.032-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.418 2.157-2.418 1.21 0 2.176 1.085 2.157 2.419 0 1.334-.956 2.419-2.157 2.419zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.418 2.157-2.418 1.21 0 2.176 1.085 2.157 2.419 0 1.334-.946 2.419-2.157 2.419z" />
            </svg>
            Continue with Discord
          </button>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-card px-2 text-muted-foreground">Or continue with email</span>
            </div>
          </div>

          <form onSubmit={handleSignup} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-xs uppercase tracking-wider mb-2 text-muted-foreground">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full bg-muted/50 px-4 py-2 rounded border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="your@email.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-xs uppercase tracking-wider mb-2 text-muted-foreground">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                className="w-full bg-muted/50 px-4 py-2 rounded border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="••••••••"
              />
            </div>

            <div>
              <label htmlFor="confirmPassword" className="block text-xs uppercase tracking-wider mb-2 text-muted-foreground">
                Confirm Password
              </label>
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={8}
                className="w-full bg-muted/50 px-4 py-2 rounded border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="••••••••"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary text-primary-foreground px-4 py-3 rounded font-bold uppercase text-sm hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <span>Creating Account...</span>
              ) : (
                <>
                  <LogIn className="w-4 h-4" />
                  Create Account
                </>
              )}
            </button>
          </form>

          <div className="mt-6 text-center text-sm">
            <span className="text-muted-foreground">Already have an account? </span>
            <Link to="/login" className="text-primary hover:underline font-bold">
              Sign In
            </Link>
          </div>
        </div>

        {/* Back to Home */}
        <div className="text-center mt-6">
          <Link to="/" className="text-xs text-muted-foreground hover:text-foreground transition-colors uppercase tracking-wider">
            ← Back to Market
          </Link>
        </div>
      </div>
    </div>
  )
}

