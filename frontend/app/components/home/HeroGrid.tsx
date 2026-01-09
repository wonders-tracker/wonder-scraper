/**
 * HeroGrid - Animated card grid background for hero section
 *
 * Shows product card images in a tilted grid that auto-animates
 * with subtle motion. Has a dark scrim overlay for text readability.
 */

import { useEffect, useRef } from 'react'
import { gsap } from 'gsap'

type HeroGridProps = {
  /** Array of image URLs to display in the grid */
  images: string[]
  /** Whether to pause animation */
  paused?: boolean
}

export function HeroGrid({ images, paused = false }: HeroGridProps) {
  const rowRefs = useRef<(HTMLDivElement | null)[]>([])
  const animationRef = useRef<number>(0)

  // Fill grid with images (4 rows x 7 cols = 28 items)
  const totalItems = 28
  const gridImages = images.length > 0
    ? Array.from({ length: totalItems }, (_, i) => images[i % images.length])
    : []

  useEffect(() => {
    if (paused || gridImages.length === 0) return

    // Continuous infinite scroll - alternating directions per row
    rowRefs.current.forEach((row, index) => {
      if (row) {
        const direction = index % 2 === 0 ? 1 : -1
        const duration = 60 + (index * 10) // Very slow, varied per row

        // Start from opposite side so it scrolls across
        gsap.set(row, { x: direction * -200 })

        // Infinite scroll in one direction
        gsap.to(row, {
          x: direction * 200,
          duration: duration,
          ease: 'none',
          repeat: -1,
          repeatRefresh: true,
          onRepeat: () => {
            // Reset to start position on each repeat
            gsap.set(row, { x: direction * -200 })
          }
        })
      }
    })

    return () => {
      rowRefs.current.forEach(row => {
        if (row) gsap.killTweensOf(row)
      })
    }
  }, [paused, gridImages.length])

  if (gridImages.length === 0) {
    return null
  }

  return (
    <div className="absolute inset-0 overflow-hidden">
      {/* Animated grid */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div
          className="grid grid-rows-4 grid-cols-1 gap-3 rotate-[-12deg] origin-center"
          style={{
            width: '140vw',
            height: '140vh',
            transform: 'rotate(-12deg) translateY(-10%)'
          }}
        >
          {Array.from({ length: 4 }, (_, rowIndex) => (
            <div
              key={rowIndex}
              className="grid gap-3 grid-cols-7"
              style={{ willChange: 'transform' }}
              ref={el => {
                if (el) rowRefs.current[rowIndex] = el
              }}
            >
              {Array.from({ length: 7 }, (_, itemIndex) => {
                const imageUrl = gridImages[rowIndex * 7 + itemIndex]
                return (
                  <div
                    key={itemIndex}
                    className="aspect-[2.5/3.5] rounded-lg overflow-hidden bg-zinc-900/50"
                  >
                    {imageUrl && (
                      <img
                        src={imageUrl}
                        alt=""
                        className="w-full h-full object-cover opacity-40"
                        loading="lazy"
                      />
                    )}
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Dark scrim overlay for text readability */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'linear-gradient(to bottom, rgba(9,9,11,0.4) 0%, rgba(9,9,11,0.6) 50%, rgba(9,9,11,0.85) 100%)'
        }}
      />

      {/* Radial gradient for center focus */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse at center, transparent 0%, rgba(9,9,11,0.3) 70%)'
        }}
      />
    </div>
  )
}
