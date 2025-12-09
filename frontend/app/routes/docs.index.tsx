import { createFileRoute, Link } from '@tanstack/react-router'
import { Code, Key, Database, Activity, Server, ArrowRight, Scale } from 'lucide-react'

export const Route = createFileRoute('/docs/')({
  component: DocsOverview,
})

function DocsOverview() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">API Documentation</h1>
        <p className="text-lg text-muted-foreground">
          Programmatic access to WondersTracker market data for Wonders of the First trading cards.
        </p>
      </div>

      {/* Base URL */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="text-lg font-bold mb-3">Base URL</h2>
        <div className="bg-zinc-900 rounded-lg p-4 font-mono text-sm">
          <code className="text-brand-300">https://api.wonderstrader.com/api/v1</code>
        </div>
      </section>

      {/* Data Sources */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="text-lg font-bold mb-4">Data Sources</h2>
        <p className="text-muted-foreground mb-4">
          Data is aggregated from multiple marketplaces:
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="border rounded-lg p-4 bg-muted/20">
            <div className="font-bold mb-1">eBay</div>
            <div className="text-sm text-muted-foreground">Sales, listings, seller info</div>
            <div className="text-xs text-brand-300 mt-2">Every 15 min</div>
          </div>
          <div className="border rounded-lg p-4 bg-muted/20">
            <div className="font-bold mb-1">Blokpax</div>
            <div className="text-sm text-muted-foreground">NFT floors, sales, offers</div>
            <div className="text-xs text-brand-300 mt-2">Every 30 min</div>
          </div>
          <div className="border rounded-lg p-4 bg-muted/20">
            <div className="font-bold mb-1">OpenSea</div>
            <div className="text-sm text-muted-foreground">NFT sales, collection stats</div>
            <div className="text-xs text-brand-300 mt-2">Every 30 min</div>
          </div>
        </div>
      </section>

      {/* Quick Start */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="text-lg font-bold mb-4">Quick Start</h2>
        <div className="bg-zinc-900 rounded-lg p-4 font-mono text-sm overflow-x-auto">
          <pre className="text-zinc-300">{`# Get all cards
curl -H "X-API-Key: wt_your_key" \\
  "https://api.wonderstrader.com/api/v1/cards"

# Get a specific card
curl -H "X-API-Key: wt_your_key" \\
  "https://api.wonderstrader.com/api/v1/cards/42"

# Get market overview
curl -H "X-API-Key: wt_your_key" \\
  "https://api.wonderstrader.com/api/v1/market/overview?time_period=7d"`}</pre>
        </div>
      </section>

      {/* Endpoint Sections */}
      <section>
        <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
          <Code className="w-5 h-5 text-brand-300" />
          API Sections
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Link
            to="/docs/authentication"
            className="border rounded-lg p-5 bg-card hover:border-primary/50 hover:bg-muted/20 transition-colors group"
          >
            <div className="flex items-center gap-3 mb-2">
              <Key className="w-5 h-5 text-amber-500" />
              <span className="font-bold">Authentication</span>
              <ArrowRight className="w-4 h-4 ml-auto text-muted-foreground group-hover:text-primary transition-colors" />
            </div>
            <p className="text-sm text-muted-foreground">API keys, rate limits, and security</p>
          </Link>

          <Link
            to="/docs/cards"
            className="border rounded-lg p-5 bg-card hover:border-primary/50 hover:bg-muted/20 transition-colors group"
          >
            <div className="flex items-center gap-3 mb-2">
              <Database className="w-5 h-5 text-blue-500" />
              <span className="font-bold">Cards API</span>
              <ArrowRight className="w-4 h-4 ml-auto text-muted-foreground group-hover:text-primary transition-colors" />
            </div>
            <p className="text-sm text-muted-foreground">Card data, pricing, sales history</p>
          </Link>

          <Link
            to="/docs/market-overview"
            className="border rounded-lg p-5 bg-card hover:border-primary/50 hover:bg-muted/20 transition-colors group"
          >
            <div className="flex items-center gap-3 mb-2">
              <Activity className="w-5 h-5 text-green-500" />
              <span className="font-bold">Market API</span>
              <ArrowRight className="w-4 h-4 ml-auto text-muted-foreground group-hover:text-primary transition-colors" />
            </div>
            <p className="text-sm text-muted-foreground">Market overview, activity, treatments</p>
          </Link>

          <Link
            to="/docs/blokpax-summary"
            className="border rounded-lg p-5 bg-card hover:border-primary/50 hover:bg-muted/20 transition-colors group"
          >
            <div className="flex items-center gap-3 mb-2">
              <Server className="w-5 h-5 text-purple-500" />
              <span className="font-bold">Blokpax API</span>
              <ArrowRight className="w-4 h-4 ml-auto text-muted-foreground group-hover:text-primary transition-colors" />
            </div>
            <p className="text-sm text-muted-foreground">NFT storefronts, sales, offers</p>
          </Link>
        </div>
      </section>

      {/* Terms of Use */}
      <section className="border rounded-lg p-6 bg-card border-amber-500/30">
        <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
          <Scale className="w-5 h-5 text-amber-500" />
          Terms of Use
        </h2>
        <div className="space-y-4 text-sm text-muted-foreground">
          <p>
            By using the WondersTrader API, you agree to the following terms:
          </p>
          <div className="space-y-3">
            <div className="flex items-start gap-3">
              <span className="text-amber-500 font-bold">1.</span>
              <div>
                <span className="text-foreground font-medium">Attribution Required</span>
                <p className="mt-1">
                  If you use our API data to create price guides, market reports, valuations,
                  or any derivative content, you <strong className="text-foreground">must</strong> attribute
                  WondersTrader as your data source.
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <span className="text-amber-500 font-bold">2.</span>
              <div>
                <span className="text-foreground font-medium">Link Back Required</span>
                <p className="mt-1">
                  All published content using our data must include a visible link to{' '}
                  <code className="text-brand-300 bg-muted px-1.5 py-0.5 rounded">wonderstrader.com</code>
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <span className="text-amber-500 font-bold">3.</span>
              <div>
                <span className="text-foreground font-medium">Disclosure Required</span>
                <p className="mt-1">
                  You must clearly disclose that your content was created using WondersTrader API data.
                  Example: <em className="text-foreground">"Data provided by WondersTrader"</em> or{' '}
                  <em className="text-foreground">"Powered by WondersTrader API"</em>
                </p>
              </div>
            </div>
          </div>
          <div className="mt-4 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
            <p className="text-amber-200 text-xs">
              Failure to comply with these terms may result in API access revocation.
              For commercial use or licensing inquiries, contact us.
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}
