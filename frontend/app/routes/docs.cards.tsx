import { createFileRoute } from '@tanstack/react-router'
import { CodeBlock } from '../components/ui/code-block'

export const Route = createFileRoute('/docs/cards')({
  component: DocsCards,
})

const exampleRequest = `curl -H "X-API-Key: wt_your_key" \\
  "https://api.wonderstrader.com/api/v1/cards?product_type=Single&time_period=30d&slim=true"`

const exampleResponse = `[
  {
    "id": 42,
    "name": "Ember the Flame",
    "slug": "ember-the-flame",
    "set_name": "Genesis",
    "rarity_id": 3,
    "rarity_name": "Rare",
    "product_type": "Single",
    "floor_price": 12.50,
    "vwap": 14.25,
    "latest_price": 15.00,
    "lowest_ask": 13.99,
    "max_price": 45.00,
    "volume": 23,
    "inventory": 8,
    "price_delta": 5.3,
    "floor_delta": 20.0,
    "last_treatment": "Classic Foil"
  }
]`

function DocsCards() {
  return (
    <div className="space-y-8">
      <div>
        <div className="flex items-center gap-3 mb-2">
          <span className="bg-brand-300/20 text-brand-300 px-2.5 py-1 rounded text-xs font-bold">GET</span>
          <code className="text-xl font-semibold">/api/v1/cards</code>
        </div>
        <p className="text-lg text-muted-foreground">
          List all cards with current market data.
        </p>
      </div>

      {/* Parameters */}
      <section className="border rounded-lg overflow-hidden bg-card">
        <div className="px-6 py-3 border-b border-border bg-muted/30">
          <h2 className="font-bold">Query Parameters</h2>
        </div>
        <div className="divide-y divide-border">
          <div className="px-6 py-4 flex gap-4">
            <code className="text-brand-300 font-mono text-sm w-32 flex-shrink-0">skip</code>
            <div>
              <span className="text-xs bg-muted px-2 py-0.5 rounded mr-2">integer</span>
              <span className="text-xs text-muted-foreground">default: 0</span>
              <p className="text-sm text-muted-foreground mt-1">Offset for pagination</p>
            </div>
          </div>
          <div className="px-6 py-4 flex gap-4">
            <code className="text-brand-300 font-mono text-sm w-32 flex-shrink-0">limit</code>
            <div>
              <span className="text-xs bg-muted px-2 py-0.5 rounded mr-2">integer</span>
              <span className="text-xs text-muted-foreground">default: 100, max: 500</span>
              <p className="text-sm text-muted-foreground mt-1">Items per page</p>
            </div>
          </div>
          <div className="px-6 py-4 flex gap-4">
            <code className="text-brand-300 font-mono text-sm w-32 flex-shrink-0">search</code>
            <div>
              <span className="text-xs bg-muted px-2 py-0.5 rounded mr-2">string</span>
              <p className="text-sm text-muted-foreground mt-1">Search by card name</p>
            </div>
          </div>
          <div className="px-6 py-4 flex gap-4">
            <code className="text-brand-300 font-mono text-sm w-32 flex-shrink-0">time_period</code>
            <div>
              <span className="text-xs bg-muted px-2 py-0.5 rounded mr-2">string</span>
              <span className="text-xs text-muted-foreground">default: 7d</span>
              <p className="text-sm text-muted-foreground mt-1">
                Time period for stats: <code className="bg-muted px-1 rounded">24h</code>, <code className="bg-muted px-1 rounded">7d</code>, <code className="bg-muted px-1 rounded">30d</code>, <code className="bg-muted px-1 rounded">90d</code>, <code className="bg-muted px-1 rounded">all</code>
              </p>
            </div>
          </div>
          <div className="px-6 py-4 flex gap-4">
            <code className="text-brand-300 font-mono text-sm w-32 flex-shrink-0">product_type</code>
            <div>
              <span className="text-xs bg-muted px-2 py-0.5 rounded mr-2">string</span>
              <p className="text-sm text-muted-foreground mt-1">
                Filter by type: <code className="bg-muted px-1 rounded">Single</code>, <code className="bg-muted px-1 rounded">Box</code>, <code className="bg-muted px-1 rounded">Pack</code>, <code className="bg-muted px-1 rounded">Bundle</code>, <code className="bg-muted px-1 rounded">Proof</code>
              </p>
            </div>
          </div>
          <div className="px-6 py-4 flex gap-4">
            <code className="text-brand-300 font-mono text-sm w-32 flex-shrink-0">slim</code>
            <div>
              <span className="text-xs bg-muted px-2 py-0.5 rounded mr-2">boolean</span>
              <span className="text-xs text-muted-foreground">default: false</span>
              <p className="text-sm text-muted-foreground mt-1">Return lightweight payload (~50% smaller)</p>
            </div>
          </div>
          <div className="px-6 py-4 flex gap-4">
            <code className="text-brand-300 font-mono text-sm w-32 flex-shrink-0">include_total</code>
            <div>
              <span className="text-xs bg-muted px-2 py-0.5 rounded mr-2">boolean</span>
              <span className="text-xs text-muted-foreground">default: false</span>
              <p className="text-sm text-muted-foreground mt-1">Include total count (slower, enables pagination metadata)</p>
            </div>
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
            <code className="text-brand-300 font-mono w-32 flex-shrink-0">floor_price</code>
            <span className="text-muted-foreground">Average of 4 lowest sales (base treatment preferred)</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-32 flex-shrink-0">vwap</code>
            <span className="text-muted-foreground">Volume Weighted Average Price</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-32 flex-shrink-0">latest_price</code>
            <span className="text-muted-foreground">Most recent sale price</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-32 flex-shrink-0">lowest_ask</code>
            <span className="text-muted-foreground">Cheapest active listing</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-32 flex-shrink-0">price_delta</code>
            <span className="text-muted-foreground">Last sale vs rolling average (%)</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-32 flex-shrink-0">floor_delta</code>
            <span className="text-muted-foreground">Last sale vs floor price (%)</span>
          </div>
        </div>
      </section>
    </div>
  )
}
