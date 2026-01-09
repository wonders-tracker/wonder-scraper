import { createFileRoute, Link } from '@tanstack/react-router'
import { ArrowLeft, Sparkles, TrendingUp, Shield, Zap, Mail, Globe } from 'lucide-react'

export const Route = createFileRoute('/changelog')({
  component: Changelog,
})

type ChangelogEntry = {
  version: string
  date: string
  title: string
  description: string
  features: {
    icon: React.ReactNode
    title: string
    description: string
    details?: string[]
    screenshot?: string // placeholder for future
  }[]
}

const changelog: ChangelogEntry[] = [
  {
    version: "January 2025",
    date: "2025-01-07",
    title: "Smarter Pricing, Confidence Scores & OpenSea",
    description: "Major improvements to how we calculate and display prices. Now you'll know not just what a card is worth, but how confident you can be in that price.",
    features: [
      {
        icon: <TrendingUp className="w-5 h-5" />,
        title: "Fair Market Price (FMP) Algorithm",
        description: "Our new pricing algorithm uses statistical methods to give you accurate, outlier-resistant prices.",
        details: [
          "MAD-trimmed mean: Analyzes 8 recent sales and removes statistical outliers using Median Absolute Deviation",
          "Dynamic multipliers: Treatment prices are calculated from actual sales data, not fixed ratios",
          "Liquidity adjustment: Prices factor in supply/demand balance",
          "Fallback formula: BaseSetPrice × RarityMultiplier × TreatmentMultiplier when sales data is sparse",
        ],
      },
      {
        icon: <Shield className="w-5 h-5" />,
        title: "Confidence Scores",
        description: "Every price now has a confidence indicator so you know how reliable it is.",
        details: [
          "Green dot (70%+): High confidence - stable prices, good data",
          "Yellow dot (40-70%): Medium confidence - some volatility or limited data",
          "Red dot (<40%): Low confidence - volatile market or sparse data",
          "Based on: listing count (35%), price spread (25%), recency (25%), volatility (15%)",
        ],
      },
      {
        icon: <Sparkles className="w-5 h-5" />,
        title: "Order Book Analysis",
        description: "We now analyze active listings to find the true floor price, not just past sales.",
        details: [
          "Scans all active listings across platforms",
          "Adaptive price bucketing finds where liquidity clusters",
          "Filters outlier listings (damaged cards, price manipulation)",
          "Falls back to sales data when listings are sparse",
        ],
      },
      {
        icon: <TrendingUp className="w-5 h-5" />,
        title: "Volatility Tracking",
        description: "See which cards have stable prices vs. wild swings.",
        details: [
          "Coefficient of variation calculated per card/treatment",
          "Volatile cards show lower confidence scores",
          "Helps you know when to trust a price vs. wait for stability",
        ],
      },
      {
        icon: <Globe className="w-5 h-5" />,
        title: "OpenSea Integration",
        description: "NFT sales from OpenSea are now included alongside eBay and Blokpax.",
        details: [
          "Track Wonders NFT sales and floor prices",
          "NFT traits displayed on listings",
          "Complete market picture across all platforms",
        ],
      },
      {
        icon: <Zap className="w-5 h-5" />,
        title: "Reliability Improvements",
        description: "Under-the-hood improvements for faster, more reliable data.",
        details: [
          "Circuit breakers prevent cascade failures",
          "Auto-recovery from browser crashes",
          "Smarter retry logic reduces data gaps",
          "Discord alerts for system health",
        ],
      },
      {
        icon: <Mail className="w-5 h-5" />,
        title: "Better Emails",
        description: "Redesigned email templates that actually work everywhere.",
        details: [
          "Table-based layouts work in all email clients (yes, even Outlook)",
          "Deal detection: cards selling below floor are highlighted",
          "Unsubscribe option for marketing emails",
          "Cleaner, more readable design",
        ],
      },
    ],
  },
]

function Changelog() {
  return (
    <div className="min-h-screen bg-background text-foreground font-mono">
      <div className="max-w-3xl mx-auto px-4 py-12">
        {/* Header */}
        <div className="mb-12">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to app
          </Link>
          <h1 className="text-3xl font-bold uppercase tracking-tight mb-2">Changelog</h1>
          <p className="text-muted-foreground">What's new in WondersTracker</p>
        </div>

        {/* Entries */}
        <div className="space-y-16">
          {changelog.map((entry) => (
            <article key={entry.version} className="relative">
              {/* Version badge */}
              <div className="flex items-center gap-4 mb-6">
                <span className="bg-brand-400/20 text-brand-400 px-3 py-1 text-xs font-bold uppercase tracking-wider">
                  {entry.version}
                </span>
                <span className="text-xs text-muted-foreground">{entry.date}</span>
              </div>

              {/* Title */}
              <h2 className="text-2xl font-bold mb-3">{entry.title}</h2>
              <p className="text-muted-foreground mb-8 leading-relaxed">{entry.description}</p>

              {/* Features */}
              <div className="space-y-8">
                {entry.features.map((feature, i) => (
                  <div key={i} className="border border-border rounded-lg p-6 bg-card">
                    <div className="flex items-start gap-4">
                      <div className="p-2 bg-muted rounded-lg text-brand-400">
                        {feature.icon}
                      </div>
                      <div className="flex-1">
                        <h3 className="font-bold text-lg mb-2">{feature.title}</h3>
                        <p className="text-muted-foreground mb-4">{feature.description}</p>

                        {feature.details && (
                          <ul className="space-y-2">
                            {feature.details.map((detail, j) => (
                              <li key={j} className="flex items-start gap-2 text-sm text-muted-foreground">
                                <span className="text-brand-400 mt-1">→</span>
                                <span>{detail}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>

        {/* Footer */}
        <div className="mt-16 pt-8 border-t border-border text-center">
          <p className="text-sm text-muted-foreground mb-4">
            Have feedback or feature requests?
          </p>
          <a
            href="https://discord.gg/wonderstracker"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 bg-[#5865F2] text-white px-4 py-2 rounded text-sm font-medium hover:bg-[#4752c4] transition-colors"
          >
            Join our Discord
          </a>
        </div>
      </div>
    </div>
  )
}
