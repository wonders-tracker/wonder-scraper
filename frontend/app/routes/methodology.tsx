import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/methodology')({
  component: MethodologyPage,
})

function MethodologyPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">Methodology</h1>

      <div className="space-y-8 text-sm">
        {/* Data Sources */}
        <section>
          <h2 className="text-xl font-bold mb-3 text-primary">Data Sources</h2>
          <p className="text-muted-foreground mb-4">
            WondersTracker aggregates market data from multiple sources to provide comprehensive
            price tracking for Wonders of the First TCG cards.
          </p>
          <ul className="list-disc list-inside space-y-2 text-muted-foreground">
            <li>
              <span className="font-semibold text-foreground">eBay</span> - Completed sales and active listings
              are scraped every 15 minutes to capture real transaction prices.
            </li>
            <li>
              <span className="font-semibold text-foreground">Blokpax</span> - Floor prices, active listings,
              and sales data updated every 30 minutes.
            </li>
          </ul>
        </section>

        {/* Price Calculation */}
        <section>
          <h2 className="text-xl font-bold mb-3 text-primary">Price Calculation</h2>
          <p className="text-muted-foreground mb-4">
            Our pricing methodology focuses on actual completed transactions rather than asking prices.
          </p>
          <div className="bg-muted/30 rounded-lg p-4 space-y-3">
            <div>
              <span className="font-semibold">Latest Price</span>
              <p className="text-muted-foreground text-xs">
                The most recent completed sale price for the card.
              </p>
            </div>
            <div>
              <span className="font-semibold">Average Price</span>
              <p className="text-muted-foreground text-xs">
                Mean of all completed sales within the selected time period.
              </p>
            </div>
            <div>
              <span className="font-semibold">Floor Price</span>
              <p className="text-muted-foreground text-xs">
                The lowest current asking price across all tracked marketplaces.
              </p>
            </div>
            <div>
              <span className="font-semibold">VWAP (Volume Weighted Average Price)</span>
              <p className="text-muted-foreground text-xs">
                Average price weighted by transaction volume, giving more weight to higher-volume price points.
              </p>
            </div>
          </div>
        </section>

        {/* Update Frequency */}
        <section>
          <h2 className="text-xl font-bold mb-3 text-primary">Update Frequency</h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-muted/30 rounded-lg p-4">
              <div className="text-2xl font-bold text-brand-400">15 min</div>
              <div className="text-xs text-muted-foreground">eBay data refresh</div>
            </div>
            <div className="bg-muted/30 rounded-lg p-4">
              <div className="text-2xl font-bold text-brand-400">30 min</div>
              <div className="text-xs text-muted-foreground">Blokpax data refresh</div>
            </div>
          </div>
        </section>

        {/* Deal Rating */}
        <section>
          <h2 className="text-xl font-bold mb-3 text-primary">Deal Rating System</h2>
          <p className="text-muted-foreground mb-4">
            Each listing is assigned a deal rating based on how its price compares to recent market data.
          </p>
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="px-2 py-0.5 rounded text-xs font-bold bg-green-500/20 text-green-500">Great Deal</span>
              <span className="text-muted-foreground text-xs">15%+ below average market price</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="px-2 py-0.5 rounded text-xs font-bold bg-brand-400/20 text-brand-400">Good Deal</span>
              <span className="text-muted-foreground text-xs">5-15% below average market price</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="px-2 py-0.5 rounded text-xs font-bold bg-yellow-500/20 text-yellow-500">Fair Price</span>
              <span className="text-muted-foreground text-xs">Within 5% of average market price</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="px-2 py-0.5 rounded text-xs font-bold bg-red-500/20 text-red-500">Overpriced</span>
              <span className="text-muted-foreground text-xs">5%+ above average market price</span>
            </div>
          </div>
        </section>

        {/* Limitations */}
        <section>
          <h2 className="text-xl font-bold mb-3 text-primary">Limitations</h2>
          <ul className="list-disc list-inside space-y-2 text-muted-foreground">
            <li>Prices are based on publicly available data and may not capture all private sales.</li>
            <li>Card condition (PSA grades, etc.) is not always distinguishable from listing data.</li>
            <li>Treatment detection (Foil, Stonefoil, etc.) relies on title parsing and may occasionally be inaccurate.</li>
            <li>Historical data prior to our tracking start date is not available.</li>
          </ul>
        </section>

        {/* Contact */}
        <section className="border-t border-border pt-6">
          <p className="text-muted-foreground text-xs">
            Questions about our methodology? Join our{' '}
            <a
              href="https://discord.gg/Kx4fFj7V"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Discord community
            </a>{' '}
            to discuss.
          </p>
        </section>
      </div>
    </div>
  )
}
