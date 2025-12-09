import { createFileRoute, Link, useSearch } from '@tanstack/react-router'
import { useState } from 'react'
import { api } from '~/utils/auth'
import { KeyRound, AlertCircle, CheckCircle, Eye, EyeOff } from 'lucide-react'

export const Route = createFileRoute('/reset-password')({
  component: ResetPassword,
  validateSearch: (search: Record<string, unknown>) => ({
    token: (search.token as string) || '',
  }),
})

function ResetPassword() {
  const { token } = useSearch({ from: Route.id })
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
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

    if (!token) {
      setError('Invalid reset link. Please request a new one.')
      return
    }

    setLoading(true)

    try {
      await api.post('auth/reset-password', {
        json: { token, new_password: password }
      }).json()
      setSuccess(true)
    } catch (err: any) {
      const message = err.response?.json?.detail || err.message || 'Failed to reset password. The link may have expired.'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4 font-mono">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-red-500/20 rounded-full mb-4">
              <AlertCircle className="w-8 h-8 text-red-500" />
            </div>
            <h1 className="text-2xl font-bold uppercase tracking-tight mb-2">Invalid Link</h1>
            <p className="text-muted-foreground text-sm">
              This password reset link is invalid or has expired.
            </p>
          </div>

          <div className="bg-card border border-border rounded-lg p-6 text-center">
            <Link
              to="/forgot-password"
              className="inline-block bg-primary text-primary-foreground px-6 py-2.5 rounded font-bold uppercase text-sm hover:bg-primary/90 transition-colors"
            >
              Request New Link
            </Link>
          </div>
        </div>
      </div>
    )
  }

  if (success) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4 font-mono">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-emerald-500/20 rounded-full mb-4">
              <CheckCircle className="w-8 h-8 text-emerald-500" />
            </div>
            <h1 className="text-2xl font-bold uppercase tracking-tight mb-2">Password Reset!</h1>
            <p className="text-muted-foreground text-sm">
              Your password has been successfully updated.
            </p>
          </div>

          <div className="bg-card border border-border rounded-lg p-6 text-center">
            <Link
              to="/login"
              className="inline-block bg-primary text-primary-foreground px-6 py-2.5 rounded font-bold uppercase text-sm hover:bg-primary/90 transition-colors"
            >
              Sign In
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4 font-mono">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-white mb-4">
            <span className="text-4xl font-bold text-black">W</span>
          </div>
          <h1 className="text-3xl font-bold uppercase tracking-tight mb-2">New Password</h1>
          <p className="text-muted-foreground text-sm">Create a new password for your account</p>
        </div>

        {/* Form */}
        <div className="bg-card border border-border rounded-lg p-6">
          {error && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/50 rounded flex items-start gap-2 text-sm text-red-500">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="password" className="block text-xs uppercase tracking-wider mb-2 text-muted-foreground">
                New Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  className="w-full bg-muted/50 px-4 py-2 pr-10 rounded border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  placeholder="Min. 8 characters"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div>
              <label htmlFor="confirmPassword" className="block text-xs uppercase tracking-wider mb-2 text-muted-foreground">
                Confirm Password
              </label>
              <input
                id="confirmPassword"
                type={showPassword ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={8}
                className="w-full bg-muted/50 px-4 py-2 rounded border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="Confirm new password"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary text-primary-foreground px-4 py-3 rounded font-bold uppercase text-sm hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <span>Resetting...</span>
              ) : (
                <>
                  <KeyRound className="w-4 h-4" />
                  Reset Password
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
