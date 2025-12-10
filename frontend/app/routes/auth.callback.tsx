import { createFileRoute, useRouter, useSearch } from '@tanstack/react-router'
import { useEffect } from 'react'
import { analytics } from '~/services/analytics'
import { api } from '~/utils/auth'

export const Route = createFileRoute('/auth/callback')({
  component: AuthCallback,
  validateSearch: (search: Record<string, unknown>) => {
    return {
      token: search.token as string | undefined,
    }
  },
})

interface UserProfile {
  id: number
  email: string
  username?: string
  discord_handle?: string
  is_active: boolean
  onboarding_completed: boolean
}

function AuthCallback() {
  const search = useSearch({ from: Route.id })
  const router = useRouter()

  useEffect(() => {
    const handleAuth = async () => {
      if (search.token) {
        localStorage.setItem('token', search.token)
        // Notify app of auth state change
        window.dispatchEvent(new Event('auth-change'))
        // Track successful Discord login
        analytics.trackLogin('discord')

        // Check if user has completed onboarding
        try {
          const profile = await api.get('auth/me').json<UserProfile>()
          if (profile.onboarding_completed) {
            // Already onboarded, go to home
            window.location.href = '/'
          } else {
            // New user or hasn't completed onboarding
            window.location.href = '/welcome'
          }
        } catch {
          // If we can't check, default to welcome
          window.location.href = '/welcome'
        }
      } else {
        // No token? Redirect to login
        router.navigate({ to: '/login' })
      }
    }
    handleAuth()
  }, [search.token, router])

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        <h2 className="text-2xl font-bold">Authenticating...</h2>
        <p className="text-muted-foreground">Please wait while we log you in.</p>
      </div>
    </div>
  )
}

