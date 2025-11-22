import { cn } from "@/lib/utils"
import React, { useEffect, useMemo, useRef, useState } from "react"

// --- Types ---

export type Frame = number[][] // [row][col] brightness 0..1

interface MatrixProps extends React.HTMLAttributes<HTMLDivElement> {
  rows: number
  cols: number
  pattern?: Frame
  frames?: Frame[]
  fps?: number
  autoplay?: boolean
  loop?: boolean
  size?: number
  gap?: number
  palette?: { on: string; off: string }
  brightness?: number
  mode?: "default" | "vu"
  levels?: number[] // For VU mode: 0-1 per column
  onFrame?: (index: number) => void
}

// --- Presets ---

export const digits: Frame[] = [
  [[1,1,1,1,1],[1,0,0,0,1],[1,0,0,0,1],[1,0,0,0,1],[1,0,0,0,1],[1,0,0,0,1],[1,1,1,1,1]], // 0
  [[0,0,1,0,0],[0,1,1,0,0],[0,0,1,0,0],[0,0,1,0,0],[0,0,1,0,0],[0,0,1,0,0],[0,1,1,1,0]], // 1
  [[1,1,1,1,1],[0,0,0,0,1],[0,0,0,0,1],[1,1,1,1,1],[1,0,0,0,0],[1,0,0,0,0],[1,1,1,1,1]], // 2
  [[1,1,1,1,1],[0,0,0,0,1],[0,0,0,0,1],[1,1,1,1,1],[0,0,0,0,1],[0,0,0,0,1],[1,1,1,1,1]], // 3
  [[1,0,0,0,1],[1,0,0,0,1],[1,0,0,0,1],[1,1,1,1,1],[0,0,0,0,1],[0,0,0,0,1],[0,0,0,0,1]], // 4
  [[1,1,1,1,1],[1,0,0,0,0],[1,0,0,0,0],[1,1,1,1,1],[0,0,0,0,1],[0,0,0,0,1],[1,1,1,1,1]], // 5
  [[1,1,1,1,1],[1,0,0,0,0],[1,0,0,0,0],[1,1,1,1,1],[1,0,0,0,1],[1,0,0,0,1],[1,1,1,1,1]], // 6
  [[1,1,1,1,1],[0,0,0,0,1],[0,0,0,0,1],[0,0,0,1,0],[0,0,1,0,0],[0,1,0,0,0],[1,0,0,0,0]], // 7
  [[1,1,1,1,1],[1,0,0,0,1],[1,0,0,0,1],[1,1,1,1,1],[1,0,0,0,1],[1,0,0,0,1],[1,1,1,1,1]], // 8
  [[1,1,1,1,1],[1,0,0,0,1],[1,0,0,0,1],[1,1,1,1,1],[0,0,0,0,1],[0,0,0,0,1],[1,1,1,1,1]], // 9
]

export const loader: Frame[] = Array.from({ length: 12 }, (_, i) => {
  const angle = (i / 12) * Math.PI * 2
  const frame = Array(7).fill(0).map(() => Array(7).fill(0))
  const cx = 3, cy = 3
  
  // Draw a rotating line/dot
  const x = Math.round(cx + Math.cos(angle) * 3)
  const y = Math.round(cy + Math.sin(angle) * 3)
  if (x >= 0 && x < 7 && y >= 0 && y < 7) frame[y][x] = 1
  
  return frame
})

export const pulse: Frame[] = Array.from({ length: 16 }, (_, i) => {
  const frame = Array(7).fill(0).map(() => Array(7).fill(0))
  const radius = (i % 8) / 2
  const cx = 3, cy = 3
  
  for(let y=0; y<7; y++) {
    for(let x=0; x<7; x++) {
      const dist = Math.sqrt((x-cx)**2 + (y-cy)**2)
      if (Math.abs(dist - radius) < 0.8) frame[y][x] = 1 - Math.abs(dist - radius)
    }
  }
  return frame
})

export const wave: Frame[] = Array.from({ length: 24 }, (_, t) => {
  const frame = Array(7).fill(0).map(() => Array(7).fill(0))
  for(let x=0; x<7; x++) {
    const y = 3 + Math.sin((x + t) * 0.5) * 2.5
    const yInt = Math.round(y)
    if(yInt >= 0 && yInt < 7) frame[yInt][x] = 1
  }
  return frame
})

export const snake: Frame[] = [] // Placeholder for snake if needed

export const chevronLeft: Frame = [
  [0,0,1,0,0],
  [0,1,0,0,0],
  [1,0,0,0,0],
  [0,1,0,0,0],
  [0,0,1,0,0],
]

export const chevronRight: Frame = [
  [0,0,1,0,0],
  [0,0,0,1,0],
  [0,0,0,0,1],
  [0,0,0,1,0],
  [0,0,1,0,0],
]

export const vu = (rows: number, levels: number[]): Frame => {
  const cols = levels.length
  const frame = Array(rows).fill(0).map(() => Array(cols).fill(0))
  
  for(let c=0; c<cols; c++) {
    const level = Math.round(levels[c] * rows)
    for(let r=0; r<rows; r++) {
      if (rows - 1 - r < level) frame[r][c] = 1
    }
  }
  return frame
}

// --- Component ---

export function Matrix({
  rows,
  cols,
  pattern,
  frames,
  fps = 12,
  autoplay = true,
  loop = true,
  size = 10,
  gap = 2,
  palette = { on: 'currentColor', off: 'var(--muted-foreground)' }, // Using CSS vars if possible, or inherit
  brightness = 1,
  mode = "default",
  levels = [],
  onFrame,
  className,
  ...props
}: MatrixProps) {
  const [frameIndex, setFrameIndex] = useState(0)
  const requestRef = useRef<number>()
  const previousTimeRef = useRef<number>()
  
  // Determine current frame data
  const currentFrameData = useMemo(() => {
    if (mode === "vu") {
      return vu(rows, levels)
    }
    if (pattern) return pattern
    if (frames && frames.length > 0) return frames[frameIndex % frames.length]
    // Empty frame fallback
    return Array(rows).fill(0).map(() => Array(cols).fill(0))
  }, [mode, rows, levels, pattern, frames, frameIndex, cols])

  // Animation Loop
  const animate = (time: number) => {
    if (previousTimeRef.current !== undefined) {
      const deltaTime = time - previousTimeRef.current
      if (deltaTime >= 1000 / fps) {
        setFrameIndex((prev) => {
          const next = prev + 1
          if (frames && next >= frames.length && !loop) return prev
          if (onFrame) onFrame(next % (frames?.length || 1))
          return next
        })
        previousTimeRef.current = time
      }
    } else {
      previousTimeRef.current = time
    }
    requestRef.current = requestAnimationFrame(animate)
  }

  useEffect(() => {
    if (autoplay && frames && frames.length > 1 && mode === 'default') {
      requestRef.current = requestAnimationFrame(animate)
    }
    return () => {
      if (requestRef.current) cancelAnimationFrame(requestRef.current)
    }
  }, [autoplay, frames, fps, loop, mode])

  // Calculate dimensions
  const width = cols * size + (cols - 1) * gap
  const height = rows * size + (rows - 1) * gap

  return (
    <div
      role="img"
      className={cn("inline-block select-none", className)}
      style={{ width, height }}
      {...props}
    >
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        {Array.from({ length: rows }).map((_, r) =>
          Array.from({ length: cols }).map((_, c) => {
            const isOn = currentFrameData[r]?.[c] > 0
            // Brightness could modulate opacity or color
            const cellBrightness = currentFrameData[r]?.[c] || 0
            
            return (
              <circle
                key={`${r}-${c}`}
                cx={c * (size + gap) + size / 2}
                cy={r * (size + gap) + size / 2}
                r={size / 2}
                fill={isOn ? palette.on : palette.off}
                opacity={isOn ? cellBrightness * brightness : 0.2} // Dim off state
                style={{ transition: 'opacity 0.1s ease' }}
              />
            )
          })
        )}
      </svg>
    </div>
  )
}

