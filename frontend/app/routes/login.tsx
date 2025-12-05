import { createRoute, redirect, useRouter, Link } from '@tanstack/react-router'
import { useState } from 'react'
import { auth, api } from '../utils/auth'
import { Route as rootRoute } from './__root'
import { Wallet, Bell, TrendingUp, BarChart3, Shield, Zap } from 'lucide-react'

export const Route = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  component: Login,
  beforeLoad: () => {
    if (typeof window !== 'undefined' && auth.isAuthenticated()) {
        throw redirect({ to: '/' })
    }
  }
})

function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    const success = await auth.login(email, password)
    if (success) {
      router.navigate({ to: '/' })
    } else {
      setError('Invalid credentials')
    }
  }

  const handleDiscordLogin = async () => {
    try {
      const res = await api.get('auth/discord/login').json<{ url: string }>()
      window.location.href = res.url
    } catch (e) {
      setError('Failed to initiate Discord login')
    }
  }

  const features = [
    {
      icon: Wallet,
      title: 'Portfolio Tracking',
      description: 'Track your collection value in real-time with automatic price updates'
    },
    {
      icon: Bell,
      title: 'Price Alerts',
      description: 'Get notified when cards hit your target buy or sell prices'
    },
    {
      icon: TrendingUp,
      title: 'Market Insights',
      description: 'Access detailed analytics and trends for smarter trading decisions'
    },
    {
      icon: BarChart3,
      title: 'Performance History',
      description: 'View your portfolio growth and individual card performance over time'
    },
    {
      icon: Shield,
      title: 'Watchlist',
      description: 'Save cards to your watchlist and monitor price movements'
    },
    {
      icon: Zap,
      title: 'Early Access',
      description: 'Be first to know about new features and market opportunities'
    }
  ]

  return (
    <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center p-4">
      <div className="w-full max-w-5xl grid grid-cols-1 lg:grid-cols-2 gap-0 border rounded-lg overflow-hidden bg-card">
        {/* Left Side - Login Form */}
        <div className="p-8 lg:p-12 flex flex-col justify-center">
          <div className="mb-8">
            <h2 className="text-2xl font-bold tracking-tight">
              Sign in to your account
            </h2>
            <p className="text-sm text-muted-foreground mt-2">
              Track your Wonders collection and stay ahead of the market
            </p>
          </div>

          <div className="space-y-4">
              <button
                  onClick={handleDiscordLogin}
                  type="button"
                  className="w-full flex justify-center items-center gap-2 rounded-md bg-[#5865F2] px-3 py-2.5 text-sm font-semibold text-white hover:bg-[#4752C4] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#5865F2] transition-colors"
              >
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037 3.903 3.903 0 0 0-.94 1.933 18.37 18.37 0 0 0-4.814 0 3.902 3.902 0 0 0-.94-1.933.074.074 0 0 0-.079-.037 19.79 19.79 0 0 0-4.885 1.515.074.074 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.118.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.074.074 0 0 0-.032-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.418 2.157-2.418 1.21 0 2.176 1.085 2.157 2.419 0 1.334-.956 2.419-2.157 2.419zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.418 2.157-2.418 1.21 0 2.176 1.085 2.157 2.419 0 1.334-.946 2.419-2.157 2.419z" />
                  </svg>
                  Sign in with Discord
              </button>

              <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                      <span className="w-full border-t border-border" />
                  </div>
                  <div className="relative flex justify-center text-xs uppercase">
                      <span className="bg-card px-2 text-muted-foreground">Or continue with email</span>
                  </div>
              </div>
          </div>

          <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
            <div className="-space-y-px rounded-md shadow-sm">
              <div>
                <label htmlFor="email-address" className="sr-only">
                  Email address
                </label>
                <input
                  id="email-address"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  className="relative block w-full rounded-t-md border-0 py-2 bg-input text-foreground ring-1 ring-inset ring-border placeholder:text-muted-foreground focus:z-10 focus:ring-2 focus:ring-inset focus:ring-primary sm:text-sm sm:leading-6 px-3"
                  placeholder="Email address"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div>
                <label htmlFor="password" className="sr-only">
                  Password
                </label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  className="relative block w-full rounded-b-md border-0 py-2 bg-input text-foreground ring-1 ring-inset ring-border placeholder:text-muted-foreground focus:z-10 focus:ring-2 focus:ring-inset focus:ring-primary sm:text-sm sm:leading-6 px-3"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>

            {error && (
              <div className="text-red-500 text-sm text-center">{error}</div>
            )}

            <div>
              <button
                type="submit"
                className="group relative flex w-full justify-center rounded-md bg-primary px-3 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors"
              >
                Sign in
              </button>
            </div>
          </form>

          <div className="mt-6 text-center text-sm">
            <span className="text-muted-foreground">Don't have an account? </span>
            <Link to={"/signup" as any} className="text-primary hover:underline font-bold">
              Sign Up
            </Link>
          </div>
        </div>

        {/* Right Side - Features */}
        <div className="hidden lg:flex flex-col justify-center p-8 lg:p-12 bg-muted/30 border-l border-border">
          <div className="mb-6">
            <h3 className="text-lg font-bold uppercase tracking-wide">Why Create an Account?</h3>
            <p className="text-sm text-muted-foreground mt-1">Unlock powerful tools to manage your collection</p>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {features.map((feature, index) => (
              <div key={index} className="flex items-start gap-3 p-3 rounded-lg hover:bg-muted/50 transition-colors">
                <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
                  <feature.icon className="w-4.5 h-4.5 text-primary" />
                </div>
                <div>
                  <h4 className="text-sm font-bold">{feature.title}</h4>
                  <p className="text-xs text-muted-foreground mt-0.5">{feature.description}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 pt-6 border-t border-border">
            <p className="text-xs text-muted-foreground text-center">
              Free to use. No credit card required.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
