import { ImageResponse } from '@vercel/og'

export const config = {
  runtime: 'edge',
}

// API URL for edge function (calls Railway directly since this runs server-side)
const API_BASE = process.env.API_URL || 'https://wonder-scraper-production.up.railway.app'
const API_URL = `${API_BASE}/api/v1`
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://wonderstracker.com'

export default async function handler(req: Request) {
  try {
    const { searchParams } = new URL(req.url)
    const cardId = searchParams.get('cardId')

    if (!cardId) {
      return new Response('Missing cardId', { status: 400 })
    }

    let cardData: any
    let historyData: any[] = []

    // Fetch card basic info
    try {
      const cardRes = await fetch(`${API_URL}/cards/${cardId}`)
      if (!cardRes.ok) {
        return new Response(`Card API error: ${cardRes.status}`, { status: 404 })
      }
      const basicCard = await cardRes.json()

      // Fetch market data
      const marketRes = await fetch(`${API_URL}/cards/${cardId}/market`)
      const marketData = marketRes.ok ? await marketRes.json() : {}

      cardData = {
        ...basicCard,
        latest_price: marketData.avg_price || basicCard.latest_price,
        volume_30d: marketData.volume || basicCard.volume_30d,
      }
    } catch (e: any) {
      return new Response(`Failed to fetch card: ${e.message}`, { status: 500 })
    }

    // Fetch price history for chart (optional - continue if fails)
    try {
      const historyRes = await fetch(`${API_URL}/cards/${cardId}/history?limit=30`)
      if (historyRes.ok) {
        const historyJson = await historyRes.json()
        historyData = Array.isArray(historyJson) ? historyJson : (historyJson.data || [])
      }
    } catch (e) {
      // Continue with empty history
      historyData = []
    }

    // Ensure we have card data
    if (!cardData || !cardData.name) {
      return new Response('Card not found', { status: 404 })
    }

    // Prepare chart data (last 10 points for simplicity)
    const chartPoints = historyData
      .filter(h => h.price && h.sold_date)
      .slice(-10)
      .map((h, idx) => ({
        x: idx * 110, // Spacing
        y: 280 - (h.price / (cardData.latest_price || 1)) * 100, // Scale to fit
        price: h.price
      }))

    return new ImageResponse(
      (
        <div
          style={{
            height: '100%',
            width: '100%',
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: '#0a0a0a',
            color: '#ffffff',
            fontFamily: 'monospace',
            padding: '48px',
          }}
        >
          {/* Header - Card Name */}
          <div
            style={{
              display: 'flex',
              fontSize: '52px',
              fontWeight: 'bold',
              marginBottom: '24px',
              textTransform: 'uppercase',
              letterSpacing: '-0.02em',
            }}
          >
            {cardData.name}
          </div>

          {/* Price */}
          <div
            style={{
              display: 'flex',
              fontSize: '72px',
              fontWeight: 'bold',
              color: '#10b981',
              marginBottom: '32px',
            }}
          >
            ${cardData.latest_price?.toFixed(2) || '---'}
          </div>

          {/* Chart Area */}
          <div
            style={{
              display: 'flex',
              flex: 1,
              border: '2px solid #333',
              borderRadius: '8px',
              padding: '24px',
              position: 'relative',
              marginBottom: '32px',
            }}
          >
            {/* Simple line chart representation */}
            <svg width="100%" height="100%" viewBox="0 0 1100 300">
              {/* Grid lines */}
              <line x1="0" y1="75" x2="1100" y2="75" stroke="#333" strokeWidth="1" strokeDasharray="5,5" />
              <line x1="0" y1="150" x2="1100" y2="150" stroke="#333" strokeWidth="1" strokeDasharray="5,5" />
              <line x1="0" y1="225" x2="1100" y2="225" stroke="#333" strokeWidth="1" strokeDasharray="5,5" />

              {/* Line chart */}
              {chartPoints.length > 1 && (
                <polyline
                  points={chartPoints.map(p => `${p.x},${p.y}`).join(' ')}
                  fill="none"
                  stroke="#10b981"
                  strokeWidth="4"
                />
              )}

              {/* Data points */}
              {chartPoints.map((point, idx) => (
                <circle
                  key={idx}
                  cx={point.x}
                  cy={point.y}
                  r="6"
                  fill="#10b981"
                  opacity="0.8"
                />
              ))}
            </svg>
          </div>

          {/* Footer - Promotional Banner */}
          <div
            style={{
              display: 'flex',
              backgroundColor: '#000000',
              padding: '24px',
              borderRadius: '8px',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '24px',
              fontWeight: 'bold',
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ color: '#10b981' }}>▶</div>
              <div>Track Real-Time TCG Prices at {SITE_URL.replace('https://', '')}</div>
            </div>
          </div>
        </div>
      ),
      {
        width: 1200,
        height: 630,
      }
    )
  } catch (e: any) {
    console.error('OG Image Error:', e)
    return new Response(`Failed to generate image: ${e.message}`, {
      status: 500,
    })
  }
}
