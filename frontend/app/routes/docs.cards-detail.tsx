import { createFileRoute } from '@tanstack/react-router'
import { CodeBlock } from '../components/ui/code-block'

export const Route = createFileRoute('/docs/cards-detail')({
  component: DocsCardsDetail,
})

const exampleRequest = `# By ID
curl -H "X-API-Key: wt_your_key" \\
  "https://api.wonderstrader.com/api/v1/cards/42"

# By slug
curl -H "X-API-Key: wt_your_key" \\
  "https://api.wonderstrader.com/api/v1/cards/ember-the-flame"`

const exampleResponse = `{
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
  "avg_price": 14.10,
  "fair_market_price": 13.80,
  "volume": 23,
  "inventory": 8,
  "price_delta": 5.3,
  "floor_delta": 20.0,
  "last_treatment": "Classic Foil",
  "last_updated": "2024-01-15T10:30:00Z"
}`

function DocsCardsDetail() {
  return (
    <div className="space-y-8">
      <div>
        <div className="flex items-center gap-3 mb-2">
          <span className="bg-brand-300/20 text-brand-300 px-2.5 py-1 rounded text-xs font-bold">GET</span>
          <code className="text-xl font-semibold">/api/v1/cards/{'{card_id}'}</code>
        </div>
        <p className="text-lg text-muted-foreground">
          Get detailed information for a specific card. Accepts numeric ID or URL slug.
        </p>
      </div>

      {/* Parameters */}
      <section className="border rounded-lg overflow-hidden bg-card">
        <div className="px-6 py-3 border-b border-border bg-muted/30">
          <h2 className="font-bold">Path Parameters</h2>
        </div>
        <div className="px-6 py-4">
          <code className="text-brand-300 font-mono text-sm">card_id</code>
          <span className="text-xs bg-muted px-2 py-0.5 rounded ml-2">string | integer</span>
          <span className="text-xs bg-red-500/20 text-red-400 px-2 py-0.5 rounded ml-2">required</span>
          <p className="text-sm text-muted-foreground mt-2">
            Card ID (numeric) or slug (e.g., <code className="bg-muted px-1 rounded">ember-the-flame</code>)
          </p>
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

      {/* Additional Fields */}
      <section className="border rounded-lg overflow-hidden bg-card">
        <div className="px-6 py-3 border-b border-border bg-muted/30">
          <h2 className="font-bold">Additional Fields (Detail Only)</h2>
        </div>
        <div className="divide-y divide-border text-sm">
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-40 flex-shrink-0">fair_market_price</code>
            <span className="text-muted-foreground">Calculated FMP using weighted formula</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-40 flex-shrink-0">avg_price</code>
            <span className="text-muted-foreground">Simple average from latest snapshot</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-40 flex-shrink-0">last_updated</code>
            <span className="text-muted-foreground">Last market snapshot timestamp</span>
          </div>
        </div>
      </section>
    </div>
  )
}
