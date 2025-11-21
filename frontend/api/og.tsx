import { ImageResponse } from '@vercel/og'

export const config = {
  runtime: 'edge',
}

export default async function handler(request: Request) {
  try {
    const { searchParams } = new URL(request.url)
    
    const cardName = searchParams.get('card') || 'WondersTracker'
    const price = searchParams.get('price') || ''
    
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
            backgroundColor: '#000',
            fontFamily: 'monospace',
          }}
        >
          {/* Logo Box */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '120px',
              height: '120px',
              backgroundColor: '#fff',
              marginBottom: '40px',
            }}
          >
            <span
              style={{
                fontSize: '80px',
                fontWeight: 'bold',
                color: '#000',
              }}
            >
              W
            </span>
          </div>
          
          {/* Card Name */}
          <div
            style={{
              display: 'flex',
              fontSize: '48px',
              fontWeight: 'bold',
              color: '#fff',
              marginBottom: '20px',
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
                fontSize: '36px',
                color: '#10b981',
                marginBottom: '20px',
              }}
            >
              {price}
            </div>
          )}
          
          {/* Footer */}
          <div
            style={{
              display: 'flex',
              fontSize: '24px',
              color: '#6b7280',
              marginTop: '20px',
            }}
          >
            wonderstracker.com
          </div>
        </div>
      ),
      {
        width: 1200,
        height: 630,
      }
    )
  } catch (e: any) {
    console.log(`${e.message}`)
    return new Response(`Failed to generate the image`, {
      status: 500,
    })
  }
}

