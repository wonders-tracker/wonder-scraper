import { createFileRoute } from '@tanstack/react-router'
import { CodeBlock } from '../components/ui/code-block'

export const Route = createFileRoute('/docs/cards-active')({
  component: DocsCardsActive,
})

const exampleRequest = `curl -H "X-API-Key: wt_your_key" \\
  "https://api.wonderstrader.com/api/v1/cards/42/active"`

const exampleResponse = `[
  {
    "id": 5678,
    "card_id": 42,
    "price": 14.99,
    "title": "WOTF Ember the Flame Classic Paper Genesis",
    "listing_type": "active",
    "treatment": "Classic Paper",
    "url": "https://www.ebay.com/itm/...",
    "image_url": "https://...",
    "seller_name": "CardDealer99",
    "seller_feedback_score": 500,
    "seller_feedback_percent": 100.0,
    "condition": "Near Mint",
    "shipping_cost": 3.99,
    "quantity": 1,
    "platform": "ebay",
    "scraped_at": "2024-01-15T10:00:00Z"
  }
]`

function DocsCardsActive() {
  return (
    <div className="space-y-8">
      <div>
        <div className="flex items-center gap-3 mb-2">
          <span className="bg-brand-300/20 text-brand-300 px-2.5 py-1 rounded text-xs font-bold">GET</span>
          <code className="text-xl font-semibold">/api/v1/cards/{'{card_id}'}/active</code>
        </div>
        <p className="text-lg text-muted-foreground">
          Get currently active listings for a card.
        </p>
      </div>

      {/* Parameters */}
      <section className="border rounded-lg overflow-hidden bg-card">
        <div className="px-6 py-3 border-b border-border bg-muted/30">
          <h2 className="font-bold">Query Parameters</h2>
        </div>
        <div className="px-6 py-4 flex gap-4">
          <code className="text-brand-300 font-mono text-sm w-32 flex-shrink-0">limit</code>
          <div>
            <span className="text-xs bg-muted px-2 py-0.5 rounded mr-2">integer</span>
            <span className="text-xs text-muted-foreground">default: 50</span>
            <p className="text-sm text-muted-foreground mt-1">Max items to return</p>
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
        <p className="text-sm text-muted-foreground mb-4">
          Same structure as <code className="bg-muted px-1 rounded">/history</code> but with <code className="bg-muted px-1 rounded">listing_type: "active"</code>.
        </p>
        <CodeBlock code={exampleResponse} language="json" className="text-xs" />
      </section>

      {/* Notes */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="font-bold mb-4">Notes</h2>
        <ul className="space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-2">
            <span className="text-brand-300">•</span>
            <span>Active listings are sorted by price ascending (cheapest first)</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-brand-300">•</span>
            <span>Listings are refreshed every 15 minutes</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-brand-300">•</span>
            <span>The <code className="bg-muted px-1 rounded">lowest_ask</code> field on card detail uses this data</span>
          </li>
        </ul>
      </section>
    </div>
  )
}
