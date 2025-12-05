import { ImageResponse } from '@vercel/og'

export const config = {
  runtime: 'edge',
}

// Rarity color mapping
const RARITY_COLORS: Record<string, string> = {
  'common': '#9ca3af',
  'uncommon': '#22c55e',
  'rare': '#3b82f6',
  'legendary': '#f59e0b',
  'mythic': '#a855f7',
}

export default async function handler(req: Request) {
  try {
    const { searchParams } = new URL(req.url)

    const cardName = searchParams.get('card') || 'WondersTracker'
    const price = searchParams.get('price') || ''
    const rarity = searchParams.get('rarity') || ''
    const setName = searchParams.get('set') || 'Wonders of the First'

    const rarityColor = RARITY_COLORS[rarity.toLowerCase()] || '#10b981'

    return new ImageResponse(
      (
        <div
          style={{
            height: '100%',
            width: '100%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: '#0a0a0a',
            fontFamily: 'monospace',
            padding: '48px',
          }}
        >
          {/* Top Bar */}
          <div
            style={{
              display: 'flex',
              width: '100%',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '24px',
            }}
          >
            <div
              style={{
                display: 'flex',
                fontSize: '20px',
                color: '#6b7280',
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
              }}
            >
              {setName}
            </div>
            {rarity && (
              <div
                style={{
                  display: 'flex',
                  fontSize: '18px',
                  color: rarityColor,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  padding: '4px 12px',
                  border: `2px solid ${rarityColor}`,
                  borderRadius: '4px',
                }}
              >
                {rarity}
              </div>
            )}
          </div>

          {/* Logo */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '100px',
              height: '100px',
              backgroundColor: '#fff',
              marginBottom: '32px',
            }}
          >
            <span style={{ fontSize: '64px', fontWeight: 'bold', color: '#000' }}>W</span>
          </div>

          {/* Card Name */}
          <div
            style={{
              display: 'flex',
              fontSize: '52px',
              fontWeight: 'bold',
              color: '#fff',
              marginBottom: '16px',
              maxWidth: '90%',
              textAlign: 'center',
            }}
          >
            {cardName}
          </div>

          {/* Price */}
          {price && (
            <div
              style={{
                display: 'flex',
                fontSize: '64px',
                fontWeight: 'bold',
                color: '#10b981',
                marginBottom: '24px',
              }}
            >
              {price}
            </div>
          )}

          {/* Footer */}
          <div
            style={{
              display: 'flex',
              position: 'absolute',
              bottom: '32px',
              fontSize: '20px',
              color: '#6b7280',
              letterSpacing: '0.05em',
            }}
          >
            Track prices at wonderstracker.com
          </div>
        </div>
      ),
      { width: 1200, height: 630 }
    )
  } catch (e: any) {
    console.error('OG Image Error:', e)
    return new Response(`Failed to generate image: ${e.message}`, { status: 500 })
  }
}
