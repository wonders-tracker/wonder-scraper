import { ImageResponse } from '@vercel/og'
import { NextRequest } from 'next/server'

export const config = {
  runtime: 'edge',
}

export default async function handler(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url)
    const cardId = searchParams.get('cardId')

    if (!cardId) {
      return new Response('Missing cardId', { status: 400 })
    }

    // Fetch card data from your API
    const API_URL = process.env.VITE_API_URL || 'https://wonderstracker.com/api/v1'

    let cardData: any
    let historyData: any[] = []

    try {
      // Fetch card basic info
      const cardRes = await fetch(`${API_URL}/cards/${cardId}`)
      const basicCard = await cardRes.json()

      // Fetch market data
      const marketRes = await fetch(`${API_URL}/cards/${cardId}/market`)
      const marketData = await marketRes.json()

      cardData = {
        ...basicCard,
        latest_price: marketData.avg_price,
        volume_30d: marketData.volume,
      }

      // Fetch price history for chart
      const historyRes = await fetch(`${API_URL}/cards/${cardId}/history?limit=30`)
      historyData = await historyRes.json()
    } catch (e) {
      return new Response('Failed to fetch card data', { status: 500 })
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
              <div>Track Real-Time TCG Prices at wonderstracker.com</div>
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
