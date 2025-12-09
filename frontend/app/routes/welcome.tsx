import { createFileRoute, redirect, useRouter } from '@tanstack/react-router'
import { useState, useEffect } from 'react'
import { auth, api } from '../utils/auth'
import { analytics } from '~/services/analytics'
import { CardGridBackground } from '~/components/CardGridBackground'
import { User, MessageCircle, FileText, ArrowRight, Loader2 } from 'lucide-react'

interface UserProfile {
  id: number
  email: string
  username: string | null
  discord_handle: string | null
  bio: string | null
  subscription_tier: string
}

export const Route = createFileRoute('/welcome')({
  component: Welcome,
  beforeLoad: () => {
    if (typeof window !== 'undefined' && !auth.isAuthenticated()) {
      throw redirect({ to: '/login' })
    }
  }
})

function Welcome() {
  const router = useRouter()
  const [username, setUsername] = useState('')
  const [discordHandle, setDiscordHandle] = useState('')
  const [bio, setBio] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null)

  // Fetch current user to pre-fill any existing data
  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const profile = await api.get('users/me').json<UserProfile>()
        setUserProfile(profile)
        setUsername(profile.username || '')
        setDiscordHandle(profile.discord_handle || '')
        setBio(profile.bio || '')
      } catch (e) {
        console.error('Failed to fetch profile:', e)
      } finally {
        setIsLoading(false)
      }
    }
    fetchProfile()
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsSubmitting(true)

    try {
      await api.put('users/me', {
        json: {
          username: username || null,
          discord_handle: discordHandle || null,
          bio: bio || null,
        }
      })
      analytics.trackProfileCompleted(!!username, !!discordHandle)
      // Navigate to upsell page
      router.navigate({ to: '/upgrade' as any })
    } catch (e) {
      console.error('Failed to update profile:', e)
      setError('Failed to save profile. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleSkip = () => {
    analytics.trackProfileSkipped()
    router.navigate({ to: '/upgrade' as any })
  }

  if (isLoading) {
    return (
      <div className="relative flex min-h-[calc(100vh-8rem)] items-center justify-center p-4">
        <CardGridBackground rows={10} cols={12} animationDuration={40} />
        <div className="relative z-10 text-center">
          <Loader2 className="w-8 h-8 animate-spin mx-auto text-primary" />
          <p className="text-muted-foreground mt-2">Loading...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="relative flex min-h-[calc(100vh-8rem)] items-center justify-center p-4">
      {/* Animated card grid background */}
      <CardGridBackground rows={10} cols={12} animationDuration={40} />

      {/* Content */}
      <div className="relative z-10 w-full max-w-lg">
        <div className="border rounded-lg overflow-hidden bg-card/95 backdrop-blur-sm shadow-2xl p-8">
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold tracking-tight">
              Welcome to Wonders Tracker!
            </h1>
            <p className="text-muted-foreground mt-2">
              Let's set up your profile. This helps other collectors find and connect with you.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Username */}
            <div>
              <label htmlFor="username" className="flex items-center gap-2 text-sm font-medium mb-2">
                <User className="w-4 h-4 text-muted-foreground" />
                Display Name
              </label>
              <input
                id="username"
                type="text"
                placeholder="How should we call you?"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full rounded-md border-0 py-2.5 bg-input text-foreground ring-1 ring-inset ring-border placeholder:text-muted-foreground focus:ring-2 focus:ring-inset focus:ring-primary sm:text-sm px-3"
              />
            </div>

            {/* Discord Handle */}
            <div>
              <label htmlFor="discord" className="flex items-center gap-2 text-sm font-medium mb-2">
                <MessageCircle className="w-4 h-4 text-muted-foreground" />
                Discord Handle
                <span className="text-xs text-muted-foreground">(optional)</span>
              </label>
              <input
                id="discord"
                type="text"
                placeholder="username#1234 or @username"
                value={discordHandle}
                onChange={(e) => setDiscordHandle(e.target.value)}
                className="w-full rounded-md border-0 py-2.5 bg-input text-foreground ring-1 ring-inset ring-border placeholder:text-muted-foreground focus:ring-2 focus:ring-inset focus:ring-primary sm:text-sm px-3"
              />
            </div>

            {/* Bio */}
            <div>
              <label htmlFor="bio" className="flex items-center gap-2 text-sm font-medium mb-2">
                <FileText className="w-4 h-4 text-muted-foreground" />
                Short Bio
                <span className="text-xs text-muted-foreground">(optional)</span>
              </label>
              <textarea
                id="bio"
                placeholder="Tell us about your collection or trading interests..."
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                rows={3}
                className="w-full rounded-md border-0 py-2.5 bg-input text-foreground ring-1 ring-inset ring-border placeholder:text-muted-foreground focus:ring-2 focus:ring-inset focus:ring-primary sm:text-sm px-3 resize-none"
              />
            </div>

            {error && (
              <div className="text-red-500 text-sm text-center">{error}</div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full flex items-center justify-center gap-2 rounded-md bg-primary px-3 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  Continue
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Skip Link */}
          <div className="mt-4 text-center">
            <button
              type="button"
              onClick={handleSkip}
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              Skip for now
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
