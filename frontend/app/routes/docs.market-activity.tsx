import { createFileRoute } from '@tanstack/react-router'
import { CodeBlock } from '../components/ui/code-block'

export const Route = createFileRoute('/docs/market-activity')({
  component: DocsMarketActivity,
})

const exampleRequest = `curl -H "X-API-Key: wt_your_key" \\
  "https://api.wonderstrader.com/api/v1/market/activity?limit=50"`

const exampleResponse = `[
  {
    "card_id": 42,
    "card_name": "Ember the Flame",
    "price": 15.00,
    "date": "2024-01-15T08:22:00Z",
    "treatment": "Classic Foil",
    "platform": "ebay"
  },
  {
    "card_id": 87,
    "card_name": "Ocean's Fury",
    "price": 22.50,
    "date": "2024-01-15T08:15:00Z",
    "treatment": "Classic Paper",
    "platform": "ebay"
  }
]`

function DocsMarketActivity() {
  return (
    <div className="space-y-8">
      <div>
        <div className="flex items-center gap-3 mb-2">
          <span className="bg-brand-300/20 text-brand-300 px-2.5 py-1 rounded text-xs font-bold">GET</span>
          <code className="text-xl font-semibold">/api/v1/market/activity</code>
        </div>
        <p className="text-lg text-muted-foreground">
          Get recent market activity (sales) across all cards.
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
            <span className="text-xs text-muted-foreground">default: 20</span>
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
        <CodeBlock code={exampleResponse} language="json" className="text-xs" />
      </section>

      {/* Use Cases */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="font-bold mb-4">Use Cases</h2>
        <ul className="space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-2">
            <span className="text-brand-300">•</span>
            <span>Display a live feed of recent sales</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-brand-300">•</span>
            <span>Monitor market velocity</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-brand-300">•</span>
            <span>Trigger alerts when specific cards sell</span>
          </li>
        </ul>
      </section>
    </div>
  )
}
