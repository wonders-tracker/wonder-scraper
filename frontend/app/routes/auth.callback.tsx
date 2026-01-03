import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useEffect } from 'react'
import { analytics } from '~/services/analytics'
import { api } from '~/utils/auth'

export const Route = createFileRoute('/auth/callback')({
  component: AuthCallback,
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
  const navigate = useNavigate()

  useEffect(() => {
    const handleAuth = async () => {
      // Cookies are already set by the backend redirect
      // Just verify auth worked and redirect appropriately
      try {
        const profile = await api.get('auth/me').json<UserProfile>()
        // Track successful Discord login
        analytics.trackLogin('discord')
        // Notify app of auth state change
        window.dispatchEvent(new Event('auth-change'))

        if (profile.onboarding_completed) {
          // Already onboarded, go to home
          navigate({ to: '/' })
        } else {
          // New user or hasn't completed onboarding
          navigate({ to: '/welcome' })
        }
      } catch (e) {
        // Auth failed - cookies weren't set properly
        console.error('Auth callback failed:', e)
        navigate({ to: '/login' })
      }
    }
    handleAuth()
  }, [navigate])

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        <h2 className="text-2xl font-bold">Authenticating...</h2>
        <p className="text-muted-foreground">Please wait while we log you in.</p>
      </div>
    </div>
  )
}
