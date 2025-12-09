import { createFileRoute } from '@tanstack/react-router'
import { CodeBlock } from '../components/ui/code-block'

export const Route = createFileRoute('/docs/market-treatments')({
  component: DocsMarketTreatments,
})

const exampleRequest = `curl -H "X-API-Key: wt_your_key" \\
  "https://api.wonderstrader.com/api/v1/market/treatments"`

const exampleResponse = `[
  {
    "name": "Classic Paper",
    "min_price": 0.99,
    "count": 1250
  },
  {
    "name": "Classic Foil",
    "min_price": 4.99,
    "count": 890
  },
  {
    "name": "Gilded Paper",
    "min_price": 15.00,
    "count": 220
  },
  {
    "name": "Gilded Foil",
    "min_price": 45.00,
    "count": 125
  },
  {
    "name": "Artist Proof Paper",
    "min_price": 75.00,
    "count": 45
  },
  {
    "name": "Artist Proof Foil",
    "min_price": 150.00,
    "count": 22
  }
]`

function DocsMarketTreatments() {
  return (
    <div className="space-y-8">
      <div>
        <div className="flex items-center gap-3 mb-2">
          <span className="bg-brand-300/20 text-brand-300 px-2.5 py-1 rounded text-xs font-bold">GET</span>
          <code className="text-xl font-semibold">/api/v1/market/treatments</code>
        </div>
        <p className="text-lg text-muted-foreground">
          Get price floors by treatment variant.
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

      {/* Treatment Tiers */}
      <section className="border rounded-lg p-6 bg-card">
        <h2 className="font-bold mb-4">Treatment Tiers</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="border rounded-lg p-4 bg-muted/20">
            <h3 className="font-bold text-sm mb-2">Classic</h3>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li>• Classic Paper - Standard card</li>
              <li>• Classic Foil - Foil version</li>
            </ul>
          </div>
          <div className="border rounded-lg p-4 bg-muted/20">
            <h3 className="font-bold text-sm mb-2">Gilded</h3>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li>• Gilded Paper - Gold-bordered standard</li>
              <li>• Gilded Foil - Gold-bordered foil</li>
            </ul>
          </div>
          <div className="border rounded-lg p-4 bg-muted/20">
            <h3 className="font-bold text-sm mb-2">Artist Proof</h3>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li>• Artist Proof Paper - AP standard</li>
              <li>• Artist Proof Foil - AP foil</li>
            </ul>
          </div>
          <div className="border rounded-lg p-4 bg-muted/20">
            <h3 className="font-bold text-sm mb-2">Special</h3>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li>• Other variants may exist</li>
              <li>• Serialized cards (/50, /100)</li>
            </ul>
          </div>
        </div>
      </section>
    </div>
  )
}
