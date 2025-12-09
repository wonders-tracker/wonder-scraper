import { useMemo } from 'react'

// WOTF card images from Blokpax - featuring a variety of rarities and art styles
const CARD_IMAGES = [
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/51?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/52?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/53?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/54?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/55?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/56?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/57?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/58?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/59?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/60?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/61?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/62?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/63?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/64?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/65?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/66?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/67?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/68?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/69?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/70?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/71?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/72?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/73?w=400',
  'https://blokpax.imgix.net/tokens/1/0xc88b8b20bf5e22cee2a2c79fa3a475fe0c412988/74?w=400',
]

interface CardGridBackgroundProps {
  /** Number of rows in the grid */
  rows?: number
  /** Number of columns in the grid */
  cols?: number
  /** Animation duration in seconds */
  animationDuration?: number
}

export function CardGridBackground({
  rows = 8,
  cols = 10,
  animationDuration = 30
}: CardGridBackgroundProps) {
  // Generate a shuffled grid of card images
  const gridCards = useMemo(() => {
    const cards: string[] = []
    const totalCards = rows * cols

    // Fill the grid with shuffled images (repeat as needed)
    for (let i = 0; i < totalCards; i++) {
      cards.push(CARD_IMAGES[i % CARD_IMAGES.length])
    }

    // Shuffle using Fisher-Yates
    for (let i = cards.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [cards[i], cards[j]] = [cards[j], cards[i]]
    }

    return cards
  }, [rows, cols])

  return (
    <div className="absolute inset-0 overflow-hidden">
      {/* Animated card grid container */}
      <div
        className="absolute inset-0 animate-card-grid"
        style={{
          // Rotate the entire grid 45 degrees
          transform: 'rotate(-15deg) scale(1.5)',
          transformOrigin: 'center center',
          // CSS animation for slow diagonal scroll
          animation: `cardGridScroll ${animationDuration}s linear infinite`,
        }}
      >
        {/* Grid wrapper - oversized to account for rotation */}
        <div
          className="grid gap-3"
          style={{
            gridTemplateColumns: `repeat(${cols}, 120px)`,
            gridTemplateRows: `repeat(${rows}, 168px)`,
            // Center the grid and add extra space for animation
            width: `${cols * 123}px`,
            height: `${rows * 171}px`,
            marginLeft: '-20%',
            marginTop: '-20%',
          }}
        >
          {gridCards.map((imageUrl, index) => (
            <div
              key={index}
              className="rounded-lg overflow-hidden shadow-lg opacity-40"
              style={{
                width: '120px',
                height: '168px',
              }}
            >
              <img
                src={imageUrl}
                alt=""
                className="w-full h-full object-cover"
                loading="lazy"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Dark gradient scrim overlay */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: `
            linear-gradient(135deg,
              rgba(0, 0, 0, 0.95) 0%,
              rgba(0, 0, 0, 0.85) 25%,
              rgba(0, 0, 0, 0.75) 50%,
              rgba(0, 0, 0, 0.85) 75%,
              rgba(0, 0, 0, 0.95) 100%
            )
          `,
        }}
      />

      {/* Vignette effect for depth */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: `radial-gradient(
            ellipse at center,
            transparent 0%,
            rgba(0, 0, 0, 0.3) 70%,
            rgba(0, 0, 0, 0.6) 100%
          )`,
        }}
      />

      {/* Add the animation keyframes via style tag */}
      <style>{`
        @keyframes cardGridScroll {
          0% {
            transform: rotate(-15deg) scale(1.5) translate(0, 0);
          }
          100% {
            transform: rotate(-15deg) scale(1.5) translate(-10%, -10%);
          }
        }
      `}</style>
    </div>
  )
}
