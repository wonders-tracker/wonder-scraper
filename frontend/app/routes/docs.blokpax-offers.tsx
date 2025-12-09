import { createFileRoute } from '@tanstack/react-router'
import { CodeBlock } from '../components/ui/code-block'

export const Route = createFileRoute('/docs/blokpax-offers')({
  component: DocsBlokpaxOffers,
})

const exampleRequest = `curl -H "X-API-Key: wt_your_key" \\
  "https://api.wonderstrader.com/api/v1/blokpax/offers?storefront=wonders-of-the-first"`

const exampleResponse = `[
  {
    "id": 5678,
    "token_id": 4521,
    "storefront_slug": "wonders-of-the-first",
    "token_name": "Ember the Flame #4521",
    "offer_price_bpx": 65.0,
    "offer_price_usd": 16.25,
    "list_price_bpx": 75.0,
    "list_price_usd": 18.75,
    "discount_percent": 13.3,
    "offerer_address": "0x1234...abcd",
    "owner_address": "0x5678...efgh",
    "expires_at": "2024-01-22T14:32:00Z",
    "created_at": "2024-01-15T14:32:00Z"
  }
]`

function DocsBlokpaxOffers() {
  return (
    <div className="space-y-8">
      <div>
        <div className="flex items-center gap-3 mb-2">
          <span className="bg-brand-300/20 text-brand-300 px-2.5 py-1 rounded text-xs font-bold">GET</span>
          <code className="text-xl font-semibold">/api/v1/blokpax/offers</code>
        </div>
        <p className="text-lg text-muted-foreground">
          Get active offers on Blokpax listings.
        </p>
      </div>

      {/* Parameters */}
      <section className="border rounded-lg overflow-hidden bg-card">
        <div className="px-6 py-3 border-b border-border bg-muted/30">
          <h2 className="font-bold">Query Parameters</h2>
        </div>
        <div className="divide-y divide-border">
          <div className="px-6 py-4 flex gap-4">
            <code className="text-brand-300 font-mono text-sm w-32 flex-shrink-0">storefront</code>
            <div>
              <span className="text-xs bg-muted px-2 py-0.5 rounded mr-2">string</span>
              <span className="text-xs text-muted-foreground">optional</span>
              <p className="text-sm text-muted-foreground mt-1">Filter by storefront slug</p>
            </div>
          </div>
          <div className="px-6 py-4 flex gap-4">
            <code className="text-brand-300 font-mono text-sm w-32 flex-shrink-0">token_id</code>
            <div>
              <span className="text-xs bg-muted px-2 py-0.5 rounded mr-2">integer</span>
              <span className="text-xs text-muted-foreground">optional</span>
              <p className="text-sm text-muted-foreground mt-1">Get offers for a specific token</p>
            </div>
          </div>
          <div className="px-6 py-4 flex gap-4">
            <code className="text-brand-300 font-mono text-sm w-32 flex-shrink-0">min_price_usd</code>
            <div>
              <span className="text-xs bg-muted px-2 py-0.5 rounded mr-2">number</span>
              <span className="text-xs text-muted-foreground">optional</span>
              <p className="text-sm text-muted-foreground mt-1">Minimum offer price in USD</p>
            </div>
          </div>
          <div className="px-6 py-4 flex gap-4">
            <code className="text-brand-300 font-mono text-sm w-32 flex-shrink-0">limit</code>
            <div>
              <span className="text-xs bg-muted px-2 py-0.5 rounded mr-2">integer</span>
              <span className="text-xs text-muted-foreground">default: 50</span>
              <p className="text-sm text-muted-foreground mt-1">Max results to return (max: 200)</p>
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
            <code className="text-brand-300 font-mono w-36 flex-shrink-0">offer_price_bpx</code>
            <span className="text-muted-foreground">Offered amount in BPX tokens</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-36 flex-shrink-0">offer_price_usd</code>
            <span className="text-muted-foreground">Offered amount in USD</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-36 flex-shrink-0">list_price_bpx</code>
            <span className="text-muted-foreground">Current listing price in BPX</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-36 flex-shrink-0">discount_percent</code>
            <span className="text-muted-foreground">Offer discount from list price</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-36 flex-shrink-0">offerer_address</code>
            <span className="text-muted-foreground">Wallet making the offer</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-36 flex-shrink-0">owner_address</code>
            <span className="text-muted-foreground">Current token owner wallet</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-36 flex-shrink-0">expires_at</code>
            <span className="text-muted-foreground">When the offer expires</span>
          </div>
        </div>
      </section>

      {/* Offer Analysis */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="font-bold mb-4">Offer Analysis</h2>
        <p className="text-sm text-muted-foreground mb-4">
          Use offer data to understand market sentiment and find opportunities:
        </p>
        <ul className="space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-2">
            <span className="text-brand-300">•</span>
            <span><strong className="text-foreground">High offer activity</strong> - Strong buyer interest</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-brand-300">•</span>
            <span><strong className="text-foreground">Low discount offers</strong> - Items priced competitively</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-brand-300">•</span>
            <span><strong className="text-foreground">High discount offers</strong> - Buyers seeking deals</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-brand-300">•</span>
            <span><strong className="text-foreground">Offer-to-list ratio</strong> - Market liquidity indicator</span>
          </li>
        </ul>
      </section>

      {/* Use Cases */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="font-bold mb-4">Use Cases</h2>
        <ul className="space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-2">
            <span className="text-brand-300">•</span>
            <span>Monitor offers on your listings</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-brand-300">•</span>
            <span>Find tokens with strong buyer interest</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-brand-300">•</span>
            <span>Identify underpriced listings (high offers)</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-brand-300">•</span>
            <span>Track collection-wide offer trends</span>
          </li>
        </ul>
      </section>
    </div>
  )
}
