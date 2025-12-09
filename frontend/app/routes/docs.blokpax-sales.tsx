import { createFileRoute } from '@tanstack/react-router'
import { CodeBlock } from '../components/ui/code-block'

export const Route = createFileRoute('/docs/blokpax-sales')({
  component: DocsBlokpaxSales,
})

const exampleRequest = `curl -H "X-API-Key: wt_your_key" \\
  "https://api.wonderstrader.com/api/v1/blokpax/sales?storefront=wonders-of-the-first&days=7"`

const exampleResponse = `[
  {
    "id": 12345,
    "token_id": 4521,
    "storefront_slug": "wonders-of-the-first",
    "token_name": "Ember the Flame #4521",
    "price_bpx": 75.0,
    "price_usd": 18.75,
    "seller_address": "0x1234...abcd",
    "buyer_address": "0x5678...efgh",
    "sold_at": "2024-01-15T14:32:00Z",
    "tx_hash": "0xabcd...1234"
  },
  {
    "id": 12344,
    "token_id": 2847,
    "storefront_slug": "wonders-of-the-first",
    "token_name": "Ocean's Fury #2847",
    "price_bpx": 120.0,
    "price_usd": 30.00,
    "seller_address": "0xaaaa...bbbb",
    "buyer_address": "0xcccc...dddd",
    "sold_at": "2024-01-15T13:15:00Z",
    "tx_hash": "0xefgh...5678"
  }
]`

function DocsBlokpaxSales() {
  return (
    <div className="space-y-8">
      <div>
        <div className="flex items-center gap-3 mb-2">
          <span className="bg-brand-300/20 text-brand-300 px-2.5 py-1 rounded text-xs font-bold">GET</span>
          <code className="text-xl font-semibold">/api/v1/blokpax/sales</code>
        </div>
        <p className="text-lg text-muted-foreground">
          Get recent sales from Blokpax marketplace.
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
            <code className="text-brand-300 font-mono text-sm w-32 flex-shrink-0">days</code>
            <div>
              <span className="text-xs bg-muted px-2 py-0.5 rounded mr-2">integer</span>
              <span className="text-xs text-muted-foreground">default: 7</span>
              <p className="text-sm text-muted-foreground mt-1">Number of days to look back (max: 90)</p>
            </div>
          </div>
          <div className="px-6 py-4 flex gap-4">
            <code className="text-brand-300 font-mono text-sm w-32 flex-shrink-0">limit</code>
            <div>
              <span className="text-xs bg-muted px-2 py-0.5 rounded mr-2">integer</span>
              <span className="text-xs text-muted-foreground">default: 50</span>
              <p className="text-sm text-muted-foreground mt-1">Max results to return (max: 500)</p>
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
            <code className="text-brand-300 font-mono w-36 flex-shrink-0">token_id</code>
            <span className="text-muted-foreground">Unique token identifier on Blokpax</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-36 flex-shrink-0">token_name</code>
            <span className="text-muted-foreground">Full name including token number</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-36 flex-shrink-0">price_bpx</code>
            <span className="text-muted-foreground">Sale price in BPX tokens</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-36 flex-shrink-0">price_usd</code>
            <span className="text-muted-foreground">Sale price converted to USD</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-36 flex-shrink-0">seller_address</code>
            <span className="text-muted-foreground">Wallet address of seller</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-36 flex-shrink-0">buyer_address</code>
            <span className="text-muted-foreground">Wallet address of buyer</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-36 flex-shrink-0">tx_hash</code>
            <span className="text-muted-foreground">Blockchain transaction hash</span>
          </div>
        </div>
      </section>

      {/* Use Cases */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="font-bold mb-4">Use Cases</h2>
        <ul className="space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-2">
            <span className="text-brand-300">•</span>
            <span>Track sales velocity across storefronts</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-brand-300">•</span>
            <span>Identify whale buyers and sellers</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-brand-300">•</span>
            <span>Calculate volume-weighted average prices</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-brand-300">•</span>
            <span>Monitor specific token sales</span>
          </li>
        </ul>
      </section>
    </div>
  )
}
