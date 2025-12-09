import { createFileRoute, useRouter, useSearch } from '@tanstack/react-router'
import { useEffect } from 'react'
import { analytics } from '~/services/analytics'

export const Route = createFileRoute('/auth/callback')({
  component: AuthCallback,
  validateSearch: (search: Record<string, unknown>) => {
    return {
      token: search.token as string | undefined,
    }
  },
})

function AuthCallback() {
  const search = useSearch({ from: Route.id })
  const router = useRouter()

  useEffect(() => {
    if (search.token) {
      localStorage.setItem('token', search.token)
      // Track successful Discord login
      analytics.trackLogin('discord')
      // Redirect to welcome page for profile completion
      window.location.href = '/welcome'
    } else {
      // No token? Redirect to login
      router.navigate({ to: '/login' })
    }
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

