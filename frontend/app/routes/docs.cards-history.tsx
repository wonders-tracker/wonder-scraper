import { createFileRoute } from '@tanstack/react-router'
import { CodeBlock } from '../components/ui/code-block'

export const Route = createFileRoute('/docs/cards-history')({
  component: DocsCardsHistory,
})

const exampleRequest = `curl -H "X-API-Key: wt_your_key" \\
  "https://api.wonderstrader.com/api/v1/cards/42/history?limit=20"`

const exampleResponse = `[
  {
    "id": 1234,
    "card_id": 42,
    "price": 15.00,
    "title": "WOTF Ember the Flame Classic Foil Genesis",
    "sold_date": "2024-01-15T08:22:00Z",
    "listing_type": "sold",
    "treatment": "Classic Foil",
    "bid_count": 3,
    "url": "https://www.ebay.com/itm/...",
    "image_url": "https://...",
    "seller_name": "CardShop123",
    "seller_feedback_score": 1250,
    "seller_feedback_percent": 99.8,
    "condition": "Near Mint",
    "shipping_cost": 4.50,
    "quantity": 1,
    "platform": "ebay",
    "scraped_at": "2024-01-15T10:00:00Z"
  }
]`

function DocsCardsHistory() {
  return (
    <div className="space-y-8">
      <div>
        <div className="flex items-center gap-3 mb-2">
          <span className="bg-brand-300/20 text-brand-300 px-2.5 py-1 rounded text-xs font-bold">GET</span>
          <code className="text-xl font-semibold">/api/v1/cards/{'{card_id}'}/history</code>
        </div>
        <p className="text-lg text-muted-foreground">
          Get sales history for a card.
        </p>
      </div>

      {/* Parameters */}
      <section className="border rounded-lg overflow-hidden bg-card">
        <div className="px-6 py-3 border-b border-border bg-muted/30">
          <h2 className="font-bold">Query Parameters</h2>
        </div>
        <div className="divide-y divide-border">
          <div className="px-6 py-4 flex gap-4">
            <code className="text-brand-300 font-mono text-sm w-32 flex-shrink-0">limit</code>
            <div>
              <span className="text-xs bg-muted px-2 py-0.5 rounded mr-2">integer</span>
              <span className="text-xs text-muted-foreground">default: 50, max: 200</span>
              <p className="text-sm text-muted-foreground mt-1">Items per page</p>
            </div>
          </div>
          <div className="px-6 py-4 flex gap-4">
            <code className="text-brand-300 font-mono text-sm w-32 flex-shrink-0">offset</code>
            <div>
              <span className="text-xs bg-muted px-2 py-0.5 rounded mr-2">integer</span>
              <span className="text-xs text-muted-foreground">default: 0</span>
              <p className="text-sm text-muted-foreground mt-1">Offset for pagination</p>
            </div>
          </div>
          <div className="px-6 py-4 flex gap-4">
            <code className="text-brand-300 font-mono text-sm w-32 flex-shrink-0">paginated</code>
            <div>
              <span className="text-xs bg-muted px-2 py-0.5 rounded mr-2">boolean</span>
              <span className="text-xs text-muted-foreground">default: false</span>
              <p className="text-sm text-muted-foreground mt-1">Return paginated response with metadata</p>
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
            <code className="text-brand-300 font-mono w-44 flex-shrink-0">treatment</code>
            <span className="text-muted-foreground">Card treatment (Classic Paper, Foil, Gilded, etc.)</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-44 flex-shrink-0">seller_name</code>
            <span className="text-muted-foreground">eBay seller username</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-44 flex-shrink-0">seller_feedback_score</code>
            <span className="text-muted-foreground">Seller's total feedback count</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-44 flex-shrink-0">seller_feedback_percent</code>
            <span className="text-muted-foreground">Seller's positive feedback percentage</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-44 flex-shrink-0">bid_count</code>
            <span className="text-muted-foreground">Number of bids (auction listings)</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-44 flex-shrink-0">platform</code>
            <span className="text-muted-foreground">Source platform (ebay, opensea)</span>
          </div>
        </div>
      </section>
    </div>
  )
}
