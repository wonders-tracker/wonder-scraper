import { createFileRoute, Link } from '@tanstack/react-router'
import { useState } from 'react'
import { api } from '~/utils/auth'
import { Mail, AlertCircle, CheckCircle, ArrowLeft } from 'lucide-react'

export const Route = createFileRoute('/forgot-password')({
  component: ForgotPassword,
})

function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await api.post('auth/forgot-password', {
        json: { email }
      }).json()
      setSuccess(true)
    } catch (err: any) {
      setError(err.message || 'Failed to send reset email. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4 font-mono">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-emerald-500/20 rounded-full mb-4">
              <CheckCircle className="w-8 h-8 text-emerald-500" />
            </div>
            <h1 className="text-2xl font-bold uppercase tracking-tight mb-2">Check Your Email</h1>
            <p className="text-muted-foreground text-sm">
              If an account exists with <span className="text-foreground font-medium">{email}</span>, you'll receive a password reset link shortly.
            </p>
          </div>

          <div className="bg-card border border-border rounded-lg p-6">
            <div className="space-y-4 text-sm text-muted-foreground">
              <p>The link will expire in 1 hour.</p>
              <p>Didn't receive an email? Check your spam folder or try again.</p>
            </div>

            <div className="mt-6 flex flex-col gap-3">
              <button
                onClick={() => {
                  setSuccess(false)
                  setEmail('')
                }}
                className="w-full bg-muted/50 text-foreground px-4 py-2.5 rounded font-medium text-sm hover:bg-muted transition-colors"
              >
                Try Different Email
              </button>
              <Link
                to="/login"
                className="w-full bg-primary text-primary-foreground px-4 py-2.5 rounded font-bold uppercase text-sm text-center hover:bg-primary/90 transition-colors"
              >
                Back to Login
              </Link>
            </div>
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
          <h1 className="text-3xl font-bold uppercase tracking-tight mb-2">Reset Password</h1>
          <p className="text-muted-foreground text-sm">Enter your email to receive a reset link</p>
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
              <label htmlFor="email" className="block text-xs uppercase tracking-wider mb-2 text-muted-foreground">
                Email Address
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

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary text-primary-foreground px-4 py-3 rounded font-bold uppercase text-sm hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <span>Sending...</span>
              ) : (
                <>
                  <Mail className="w-4 h-4" />
                  Send Reset Link
                </>
              )}
            </button>
          </form>

          <div className="mt-6 text-center">
            <Link to="/login" className="text-sm text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1">
              <ArrowLeft className="w-3 h-3" />
              Back to Login
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
