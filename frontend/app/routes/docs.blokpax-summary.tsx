import { createFileRoute } from '@tanstack/react-router'
import { CodeBlock } from '../components/ui/code-block'

export const Route = createFileRoute('/docs/blokpax-summary')({
  component: DocsBlokpaxSummary,
})

const exampleRequest = `curl -H "X-API-Key: wt_your_key" \\
  "https://api.wonderstrader.com/api/v1/blokpax/summary"`

const exampleResponse = `{
  "storefronts": [
    {
      "slug": "wonders-of-the-first",
      "name": "Wonders of the First",
      "floor_price_usd": 12.50,
      "floor_price_bpx": 50.0,
      "listed_count": 250,
      "total_tokens": 10000
    }
  ],
  "totals": {
    "total_listed": 250,
    "total_tokens": 10000,
    "lowest_floor_usd": 12.50,
    "recent_sales_24h": 15,
    "volume_7d_usd": 1250.00
  }
}`

function DocsBlokpaxSummary() {
  return (
    <div className="space-y-8">
      <div>
        <div className="flex items-center gap-3 mb-2">
          <span className="bg-brand-300/20 text-brand-300 px-2.5 py-1 rounded text-xs font-bold">GET</span>
          <code className="text-xl font-semibold">/api/v1/blokpax/summary</code>
        </div>
        <p className="text-lg text-muted-foreground">
          Get a summary of all WOTF Blokpax data for dashboard display.
        </p>
      </div>

      {/* Overview */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="font-bold mb-4">About Blokpax</h2>
        <p className="text-sm text-muted-foreground">
          Blokpax is an NFT marketplace where WOTF digital cards are traded. Prices are tracked in both BPX (Blokpax token) and USD.
        </p>
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
          <h2 className="font-bold">Totals Fields</h2>
        </div>
        <div className="divide-y divide-border text-sm">
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-40 flex-shrink-0">total_listed</code>
            <span className="text-muted-foreground">Total NFTs currently listed for sale</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-40 flex-shrink-0">total_tokens</code>
            <span className="text-muted-foreground">Total NFTs in existence</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-40 flex-shrink-0">lowest_floor_usd</code>
            <span className="text-muted-foreground">Lowest floor price across all storefronts</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-40 flex-shrink-0">recent_sales_24h</code>
            <span className="text-muted-foreground">Number of sales in last 24 hours</span>
          </div>
          <div className="px-6 py-3 flex gap-4">
            <code className="text-brand-300 font-mono w-40 flex-shrink-0">volume_7d_usd</code>
            <span className="text-muted-foreground">Total USD volume in last 7 days</span>
          </div>
        </div>
      </section>

      {/* BPX Token */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="font-bold mb-4">BPX Token</h2>
        <p className="text-sm text-muted-foreground">
          BPX is the native token of the Blokpax marketplace. All prices are tracked in both BPX and USD:
        </p>
        <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
          <li><code className="text-brand-300">price_bpx</code> - Price in BPX tokens</li>
          <li><code className="text-brand-300">price_usd</code> - Price in US dollars (converted at time of snapshot)</li>
        </ul>
      </section>
    </div>
  )
}
