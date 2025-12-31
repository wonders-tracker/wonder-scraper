import { createFileRoute, useRouter, Link } from '@tanstack/react-router'
import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '../utils/auth'
import { useCurrentUser } from '../context/UserContext'
import {
  Zap,
  Check,
  Database,
  TrendingUp,
  BarChart3,
  Shield,
  Sparkles,
  ArrowRight,
  Loader2
} from 'lucide-react'

export const Route = createFileRoute('/upgrade')({
  component: Upgrade
})

interface SubscriptionStatus {
  tier: string
  status: string | null
  product_type: string | null
  is_pro: boolean
  is_api_subscriber: boolean
  has_api_access: boolean
  current_period_end: string | null
}

function Upgrade() {
  const router = useRouter()
  const { user } = useCurrentUser()
  const isLoggedIn = !!user
  const [isRedirecting, setIsRedirecting] = useState(false)

  // Get current subscription status
  const { data: subscription } = useQuery<SubscriptionStatus>({
    queryKey: ['subscription-status'],
    queryFn: async () => {
      const res = await api.get('billing/status')
      return res.json()
    },
    enabled: isLoggedIn
  })

  // Create checkout mutation
  const checkoutMutation = useMutation({
    mutationFn: async () => {
      const res = await api.post('billing/checkout')
      return res.json<{ checkout_url: string }>()
    },
    onSuccess: (data) => {
      setIsRedirecting(true)
      window.location.href = data.checkout_url
    }
  })

  const features = [
    {
      icon: Database,
      title: 'API Access Included',
      description: '10,000 API requests/month included with Pro. Build apps, bots, and integrations.'
    },
    {
      icon: TrendingUp,
      title: 'Real-Time Price Data',
      description: 'Access price history, market trends, and sales data via API.'
    },
    {
      icon: BarChart3,
      title: 'Pro Dashboard',
      description: 'Advanced analytics, market insights, and portfolio tracking tools.'
    },
    {
      icon: Shield,
      title: 'Priority Support',
      description: 'Get help faster with priority Discord and email support.'
    },
    {
      icon: Sparkles,
      title: 'Early Access',
      description: 'Be first to try new features and provide feedback.'
    },
    {
      icon: Zap,
      title: 'Usage-Based Scaling',
      description: 'Need more requests? Pay only $0.001 per additional request.'
    }
  ]

  const handleUpgrade = () => {
    if (!isLoggedIn) {
      router.navigate({ to: '/login' })
      return
    }
    checkoutMutation.mutate()
  }

  // Show different state if already Pro
  if (subscription?.is_pro) {
    return (
      <div className="min-h-screen bg-zinc-950 py-12 px-4">
        <div className="max-w-2xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-brand-300/10 border border-brand-300/30 mb-6">
            <Check className="w-5 h-5 text-brand-300" />
            <span className="text-brand-300 font-medium">You're on Pro!</span>
          </div>

          <h1 className="text-4xl font-bold text-white mb-4">
            Thanks for being a Pro member
          </h1>

          <p className="text-zinc-400 text-lg mb-8">
            You have full access to all Pro features including API access.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              to="/profile"
              className="px-6 py-3 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg font-medium transition-colors"
            >
              View Profile
            </Link>
            <a
              href="#"
              onClick={async (e) => {
                e.preventDefault()
                try {
                  const res = await api.get('billing/portal').json<{ portal_url: string }>()
                  window.location.href = res.portal_url
                } catch (err) {
                  console.error('Failed to get portal URL', err)
                }
              }}
              className="px-6 py-3 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg font-medium transition-colors"
            >
              Manage Subscription
            </a>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-zinc-950 py-12 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-400/10 border border-brand-400/30 mb-4">
            <Zap className="w-4 h-4 text-brand-300" />
            <span className="text-brand-300 text-sm font-medium">Pro Plan</span>
          </div>

          <h1 className="text-4xl sm:text-5xl font-bold text-white mb-4">
            Unlock the Full Power of<br />
            <span className="text-brand-300">
              Wonders Tracker
            </span>
          </h1>

          <p className="text-zinc-400 text-lg max-w-2xl mx-auto">
            Get API access, advanced analytics, and priority support.
            Build integrations, track portfolios, and stay ahead of the market.
          </p>
        </div>

        {/* Pricing Card */}
        <div className="max-w-md mx-auto mb-16">
          <div className="relative bg-zinc-900 rounded-2xl border border-zinc-800 p-8 overflow-hidden">
            {/* Glow effect */}
            <div className="absolute -top-24 -right-24 w-48 h-48 bg-brand-400/20 rounded-full blur-3xl" />

            <div className="relative">
              <div className="flex items-baseline gap-2 mb-2">
                <span className="text-5xl font-bold text-white">$9.99</span>
                <span className="text-zinc-500">/month</span>
              </div>

              <p className="text-zinc-400 mb-6">
                Everything you need to track and build
              </p>

              <ul className="space-y-3 mb-8">
                {[
                  'Pro dashboard & analytics',
                  '10k API requests/month included',
                  'Real-time price data access',
                  'Priority support',
                  'Early access to new features',
                  '$0.001/request for additional usage'
                ].map((item) => (
                  <li key={item} className="flex items-center gap-3 text-zinc-300">
                    <Check className="w-5 h-5 text-brand-300 flex-shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>

              <button
                onClick={handleUpgrade}
                disabled={checkoutMutation.isPending || isRedirecting}
                className="w-full py-4 px-6 bg-brand-400 hover:bg-brand-300 text-gray-900 font-semibold rounded-xl transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {checkoutMutation.isPending || isRedirecting ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Redirecting to checkout...
                  </>
                ) : (
                  <>
                    {isLoggedIn ? 'Upgrade to Pro' : 'Sign in to Upgrade'}
                    <ArrowRight className="w-5 h-5" />
                  </>
                )}
              </button>

              {checkoutMutation.isError && (
                <p className="text-red-400 text-sm mt-3 text-center">
                  Failed to create checkout. Please try again.
                </p>
              )}

              {/* Continue as free option */}
              <div className="mt-4 text-center">
                <Link
                  to="/"
                  className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
                >
                  Continue with free account
                </Link>
              </div>
            </div>
          </div>
        </div>

        {/* Features Grid */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-16">
          {features.map((feature) => (
            <div
              key={feature.title}
              className="p-6 bg-zinc-900/50 border border-zinc-800 rounded-xl hover:border-zinc-700 transition-colors"
            >
              <feature.icon className="w-10 h-10 text-brand-300 mb-4" />
              <h3 className="text-white font-semibold mb-2">{feature.title}</h3>
              <p className="text-zinc-400 text-sm">{feature.description}</p>
            </div>
          ))}
        </div>

        {/* FAQ */}
        <div className="max-w-2xl mx-auto">
          <h2 className="text-2xl font-bold text-white text-center mb-8">
            Frequently Asked Questions
          </h2>

          <div className="space-y-4">
            {[
              {
                q: 'What happens if I exceed my included requests?',
                a: 'You\'ll be charged $0.001 per additional request. That\'s just $1 per 1,000 extra requests. No surprises.'
              },
              {
                q: 'Can I cancel anytime?',
                a: 'Yes! Cancel anytime from your account. You\'ll keep Pro access until the end of your billing period.'
              },
              {
                q: 'What can I build with the API?',
                a: 'Discord bots, portfolio trackers, price alerts, spreadsheet integrations, or any app that needs WOTF market data.'
              },
              {
                q: 'What about API-only access?',
                a: 'Need just API access without Pro features? Request API access and pay only for what you use ($0.001/request).'
              }
            ].map((faq) => (
              <div key={faq.q} className="p-4 bg-zinc-900/50 border border-zinc-800 rounded-lg">
                <h3 className="text-white font-medium mb-2">{faq.q}</h3>
                <p className="text-zinc-400 text-sm">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
