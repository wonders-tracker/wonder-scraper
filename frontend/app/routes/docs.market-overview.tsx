import { createFileRoute } from '@tanstack/react-router'
import { CodeBlock } from '../components/ui/code-block'

export const Route = createFileRoute('/docs/market-overview')({
  component: DocsMarketOverview,
})

const exampleRequest = `curl -H "X-API-Key: wt_your_key" \\
  "https://api.wonderstrader.com/api/v1/market/overview?time_period=7d"`

const exampleResponse = `[
  {
    "id": 42,
    "slug": "ember-the-flame",
    "name": "Ember the Flame",
    "set_name": "Genesis",
    "rarity_id": 3,
    "latest_price": 15.00,
    "avg_price": 14.10,
    "vwap": 14.25,
    "floor_price": 12.50,
    "volume_period": 23,
    "volume_change": 0,
    "price_delta_period": 5.3,
    "deal_rating": -2.5,
    "market_cap": 345.00
  }
]`

function DocsMarketOverview() {
  return (
    <div className="space-y-8">
      <div>
        <div className="flex items-center gap-3 mb-2">
          <span className="bg-brand-300/20 text-brand-300 px-2.5 py-1 rounded text-xs font-bold">GET</span>
          <code className="text-xl font-semibold">/api/v1/market/overview</code>
        </div>
        <p className="text-lg text-muted-foreground">
          Get market-wide statistics and trends.
        </p>
      </div>

      {/* Parameters */}
      <section className="border rounded-lg overflow-hidden bg-card">
        <div className="px-6 py-3 border-b border-border bg-muted/30">
          <h2 className="font-bold">Query Parameters</h2>
        </div>
        <div className="px-6 py-4 flex gap-4">
          <code className="text-brand-300 font-mono text-sm w-32 flex-shrink-0">time_period</code>
          <div>
            <span className="text-xs bg-muted px-2 py-0.5 rounded mr-2">string</span>
            <span className="text-xs text-muted-foreground">default: 30d</span>
            <p className="text-sm text-muted-foreground mt-1">
              Period: <code className="bg-muted px-1 rounded">1h</code>, <code className="bg-muted px-1 rounded">24h</code>, <code className="bg-muted px-1 rounded">7d</code>, <code className="bg-muted px-1 rounded">30d</code>, <code className="bg-muted px-1 rounded">90d</code>, <code className="bg-muted px-1 rounded">all</code>
            </p>
          </div>
        </div>
      </section>

      {/* Example Request */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="font-bold mb-4">Example Request</h2>
        <CodeBlock code={exampleRequest} language="bash" />
      </section>

      {/* Response */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="font-bold mb-4">Response</h2>
        <CodeBlock code={exampleResponse} language="json" className="text-xs" />
      </section>

      {/* Response Fields */}
      <section className="border rounded-lg overflow-hidden bg-card">
        <div className="px-6 py-3 border-b border-border bg-muted/30">
          <h2 className="font-bold">Response Fields</h2>
        </div>
        <div className="divide-y divide-border text-sm">
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-40 flex-shrink-0">volume_period</code>
            <span className="text-muted-foreground">Number of sales in time period</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-40 flex-shrink-0">price_delta_period</code>
            <span className="text-muted-foreground">Price change % (last sale vs floor)</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-40 flex-shrink-0">deal_rating</code>
            <span className="text-muted-foreground">Deal score (last sale vs VWAP)</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-40 flex-shrink-0">market_cap</code>
            <span className="text-muted-foreground">latest_price × volume_period</span>
          </div>
        </div>
      </section>

      {/* Caching */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="font-bold mb-4">Caching</h2>
        <p className="text-sm text-muted-foreground">
          Responses are cached for <strong className="text-foreground">2 minutes</strong>.
          Check the <code className="bg-muted px-1 rounded">X-Cache</code> header (<code className="bg-muted px-1 rounded">HIT</code> or <code className="bg-muted px-1 rounded">MISS</code>).
        </p>
      </section>
    </div>
  )
}
