import { createFileRoute, Link } from '@tanstack/react-router'
import { useMutation } from '@tanstack/react-query'
import { api } from '../utils/auth'
import { useState } from 'react'
import { Mail, CheckCircle, ArrowLeft } from 'lucide-react'
import { useCurrentUser } from '../context/UserContext'

export const Route = createFileRoute('/unsubscribe')({
  component: Unsubscribe,
})

function Unsubscribe() {
  const [unsubscribed, setUnsubscribed] = useState(false)
  const { user } = useCurrentUser()
  const isLoggedIn = !!user

  const unsubscribeMutation = useMutation({
    mutationFn: async () => {
      await api.post('users/me/unsubscribe', { json: { marketing_emails: false } })
    },
    onSuccess: () => {
      setUnsubscribed(true)
    },
  })

  if (unsubscribed) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-foreground font-mono p-4">
        <div className="max-w-md w-full text-center">
          <div className="w-16 h-16 bg-brand-400/20 rounded-full flex items-center justify-center mx-auto mb-6">
            <CheckCircle className="w-8 h-8 text-brand-400" />
          </div>
          <h1 className="text-2xl font-bold uppercase tracking-tight mb-4">Unsubscribed</h1>
          <p className="text-muted-foreground mb-8">
            You've been unsubscribed from marketing emails. You'll still receive important account notifications.
          </p>
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-sm text-brand-400 hover:text-brand-300 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to WondersTracker
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background text-foreground font-mono p-4">
      <div className="max-w-md w-full">
        <div className="border border-border rounded-lg bg-card p-8 text-center">
          <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center mx-auto mb-6">
            <Mail className="w-8 h-8 text-muted-foreground" />
          </div>

          <h1 className="text-2xl font-bold uppercase tracking-tight mb-4">Unsubscribe</h1>

          <p className="text-muted-foreground mb-8">
            No longer want to receive market digest and promotional emails from WondersTracker?
          </p>

          {isLoggedIn ? (
            <button
              onClick={() => unsubscribeMutation.mutate()}
              disabled={unsubscribeMutation.isPending}
              className="w-full bg-primary text-primary-foreground px-6 py-3 rounded text-sm uppercase font-bold hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {unsubscribeMutation.isPending ? 'Processing...' : 'Unsubscribe from emails'}
            </button>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Please log in to manage your email preferences.
              </p>
              <Link
                to="/login"
                className="inline-block w-full bg-primary text-primary-foreground px-6 py-3 rounded text-sm uppercase font-bold hover:bg-primary/90 transition-colors"
              >
                Log in
              </Link>
            </div>
          )}

          <p className="text-xs text-muted-foreground mt-6">
            You'll still receive important account notifications like password resets.
          </p>
        </div>

        <div className="mt-6 text-center">
          <Link
            to="/"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            ← Back to WondersTracker
          </Link>
        </div>
      </div>
    </div>
  )
}
