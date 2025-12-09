import { createFileRoute } from '@tanstack/react-router'
import { CodeBlock } from '../components/ui/code-block'

export const Route = createFileRoute('/docs/blokpax-storefronts')({
  component: DocsBlokpaxStorefronts,
})

const exampleRequest = `curl -H "X-API-Key: wt_your_key" \\
  "https://api.wonderstrader.com/api/v1/blokpax/storefronts"`

const exampleResponse = `[
  {
    "id": 1,
    "slug": "wonders-of-the-first",
    "name": "Wonders of the First",
    "description": "Official WOTF collection",
    "image_url": "https://...",
    "network_id": 1,
    "floor_price_bpx": 50.0,
    "floor_price_usd": 12.50,
    "total_tokens": 10000,
    "listed_count": 250,
    "updated_at": "2024-01-15T10:30:00Z"
  }
]`

const singleStorefrontRequest = `curl -H "X-API-Key: wt_your_key" \\
  "https://api.wonderstrader.com/api/v1/blokpax/storefronts/wonders-of-the-first"`

const snapshotsResponse = `[
  {
    "id": 123,
    "storefront_slug": "wonders-of-the-first",
    "floor_price_bpx": 50.0,
    "floor_price_usd": 12.50,
    "bpx_price_usd": 0.25,
    "listed_count": 250,
    "total_tokens": 10000,
    "timestamp": "2024-01-15T00:00:00Z"
  }
]`

function DocsBlokpaxStorefronts() {
  return (
    <div className="space-y-8">
      <div>
        <div className="flex items-center gap-3 mb-2">
          <span className="bg-brand-300/20 text-brand-300 px-2.5 py-1 rounded text-xs font-bold">GET</span>
          <code className="text-xl font-semibold">/api/v1/blokpax/storefronts</code>
        </div>
        <p className="text-lg text-muted-foreground">
          List all WOTF storefronts with current floor prices.
        </p>
      </div>

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

      {/* Single Storefront */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="font-bold mb-4">Get Single Storefront</h2>
        <div className="flex items-center gap-3 mb-4">
          <span className="bg-brand-300/20 text-brand-300 px-2.5 py-1 rounded text-xs font-bold">GET</span>
          <code className="text-sm font-semibold">/api/v1/blokpax/storefronts/{'{slug}'}</code>
        </div>
        <CodeBlock code={singleStorefrontRequest} language="bash" />
      </section>

      {/* Snapshots */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="font-bold mb-4">Get Price History</h2>
        <div className="flex items-center gap-3 mb-4">
          <span className="bg-brand-300/20 text-brand-300 px-2.5 py-1 rounded text-xs font-bold">GET</span>
          <code className="text-sm font-semibold">/api/v1/blokpax/storefronts/{'{slug}'}/snapshots</code>
        </div>
        <p className="text-sm text-muted-foreground mb-4">
          Get price history snapshots for charts.
        </p>
        <div className="text-xs text-muted-foreground mb-4">
          <span className="text-foreground/70">Query Params:</span>{' '}
          <code className="bg-muted px-1.5 py-0.5 rounded">days</code> (default: 30, max: 365),{' '}
          <code className="bg-muted px-1.5 py-0.5 rounded">limit</code> (default: 100, max: 1000)
        </div>
        <CodeBlock code={snapshotsResponse} language="json" className="text-xs" />
      </section>
    </div>
  )
}
