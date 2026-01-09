/**
 * PriceHistoryChart - Lazy-loaded chart for card detail pages.
 *
 * This component is code-split to avoid loading recharts (378KB) on initial page load.
 * It only loads when the user visits a card detail page.
 */
import { useMemo } from 'react'
import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'

// Note: AreaChart removed - now using ComposedChart for combined price + floor trend

type ChartDataPoint = {
  timestamp: number
  price: number
  date: string
  treatment?: string
  treatmentColor?: string
  isActive?: boolean
  dailyVolume?: number
}

type FloorHistoryPoint = {
  date: string
  floor_price: number | null
  fmp: number | null
  vwap: number | null
  sales_count: number
  treatment: string | null
}

type Props = {
  data: ChartDataPoint[]
  floorHistory?: FloorHistoryPoint[]
}

// Generate well-spaced log scale ticks - max 4-5 ticks for cleaner display
function generateLogTicks(min: number, max: number): number[] {
  const logMin = Math.log10(min)
  const logMax = Math.log10(max)
  const logRange = logMax - logMin

  // Target 3-4 ticks for clean display
  const targetTicks = 4

  // Calculate step in log space
  const logStep = logRange / targetTicks

  // Round step to nice values (0.5, 1, 2 in log space)
  let niceLogStep: number
  if (logStep < 0.3) niceLogStep = 0.25
  else if (logStep < 0.7) niceLogStep = 0.5
  else if (logStep < 1.5) niceLogStep = 1
  else niceLogStep = 2

  // Generate ticks at nice intervals
  const ticks: number[] = []
  const startLog = Math.ceil(logMin / niceLogStep) * niceLogStep

  for (let log = startLog; log <= logMax + 0.01; log += niceLogStep) {
    const val = Math.pow(10, log)
    if (val >= min * 0.9 && val <= max * 1.1) {
      // Round to nice number
      const magnitude = Math.pow(10, Math.floor(Math.log10(val)))
      const normalized = val / magnitude
      let niceVal: number
      if (normalized < 1.5) niceVal = magnitude
      else if (normalized < 3.5) niceVal = 2 * magnitude
      else if (normalized < 7.5) niceVal = 5 * magnitude
      else niceVal = 10 * magnitude

      // Avoid duplicates
      if (ticks.length === 0 || Math.abs(niceVal - ticks[ticks.length - 1]) / niceVal > 0.1) {
        ticks.push(niceVal)
      }
    }
  }

  // Limit to max 5 ticks
  if (ticks.length > 5) {
    const step = Math.ceil(ticks.length / 4)
    return ticks.filter((_, i) => i % step === 0 || i === ticks.length - 1)
  }

  return ticks
}

export function PriceHistoryChart({ data, floorHistory }: Props) {
  // Transform floor history to chart format
  const floorHistoryData = useMemo(() => {
    if (!floorHistory || floorHistory.length === 0) return []
    return floorHistory
      .filter(h => h.floor_price !== null)
      .map(h => ({
        timestamp: new Date(h.date).getTime(),
        floorPrice: h.floor_price,
        vwap: h.vwap,
      }))
  }, [floorHistory])

  // Merge sales data with floor history for combined chart
  const combinedData = useMemo(() => {
    if (floorHistoryData.length === 0) return data

    // Create a map of timestamps to floor prices
    const floorMap = new Map<number, { floorPrice: number | null, vwap: number | null }>()
    floorHistoryData.forEach(h => {
      // Round to day for matching
      const dayTs = new Date(h.timestamp).setHours(0, 0, 0, 0)
      floorMap.set(dayTs, { floorPrice: h.floorPrice, vwap: h.vwap })
    })

    // Add floor data to each sales point
    const enrichedData = data.map(d => {
      const dayTs = new Date(d.timestamp).setHours(0, 0, 0, 0)
      const floorData = floorMap.get(dayTs)
      return {
        ...d,
        historicalFloor: floorData?.floorPrice ?? null,
        historicalVwap: floorData?.vwap ?? null,
      }
    })

    // Also add floor-only points for days without sales
    const salesDays = new Set(data.map(d => new Date(d.timestamp).setHours(0, 0, 0, 0)))
    const floorOnlyPoints = floorHistoryData
      .filter(h => !salesDays.has(new Date(h.timestamp).setHours(0, 0, 0, 0)))
      .map(h => ({
        timestamp: h.timestamp,
        price: null as number | null,
        date: new Date(h.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' }),
        historicalFloor: h.floorPrice,
        historicalVwap: h.vwap,
      }))

    return [...enrichedData, ...floorOnlyPoints].sort((a, b) => a.timestamp - b.timestamp)
  }, [data, floorHistoryData])
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        No price data available
      </div>
    )
  }

  // Calculate Y-axis domain for log scale (include floor history prices)
  const prices = data.map(d => d.price).filter(p => p > 0)
  const floorPrices = floorHistoryData.map(h => h.floorPrice).filter((p): p is number => p !== null && p > 0)
  const allPrices = [...prices, ...floorPrices]

  // For log scale, find min/max and add padding in log space
  const minPrice = Math.min(...allPrices)
  const maxPrice = Math.max(...allPrices)

  // Calculate log values
  const logMin = Math.log10(minPrice)
  const logMax = Math.log10(maxPrice)
  const logRange = logMax - logMin

  // Add more padding when there's little variation or few data points
  // Minimum spread of 0.5 log units (about 3x range) for readability
  const minLogSpread = 0.5
  const effectiveLogRange = Math.max(logRange, minLogSpread)

  // More padding (20%) for better visual spacing
  const logPadding = effectiveLogRange * 0.2

  // If prices are very close (< 0.1 log spread), center and expand equally
  let yMin: number, yMax: number
  if (logRange < 0.1) {
    const center = (logMin + logMax) / 2
    yMin = Math.pow(10, center - minLogSpread / 2 - logPadding)
    yMax = Math.pow(10, center + minLogSpread / 2 + logPadding)
  } else {
    yMin = Math.pow(10, logMin - logPadding)
    yMax = Math.pow(10, logMax + logPadding)
  }

  // Generate clean log scale ticks
  const yTicks = generateLogTicks(yMin, yMax)

  // Check if we have floor history to show
  const hasFloorHistory = floorHistoryData.length > 1

  return (
    <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={hasFloorHistory ? combinedData : data} margin={{ top: 10, right: 0, bottom: 20, left: 0 }}>
          <defs>
            <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#7dd3a8" stopOpacity={0.15}/>
              <stop offset="95%" stopColor="#7dd3a8" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" strokeOpacity={0.3} vertical={false} />
          <XAxis
            dataKey="timestamp"
            type="number"
            domain={['dataMin', 'dataMax']}
            tickFormatter={(ts) => new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            tick={{ fill: '#71717a', fontSize: 10 }}
            axisLine={{ stroke: '#27272a' }}
            tickLine={{ stroke: '#27272a' }}
          />
          {/* Left Y-axis for volume bars - hidden, just for scaling */}
          <YAxis
            yAxisId="volume"
            orientation="left"
            domain={[0, 'auto']}
            hide
            width={1}
          />
          {/* Right Y-axis for price (log scale) */}
          <YAxis
            yAxisId="price"
            orientation="right"
            scale="log"
            domain={[yMin, yMax]}
            ticks={yTicks}
            tickFormatter={(val) => `$${val >= 1000 ? `${(val/1000).toFixed(0)}k` : val < 10 ? val.toFixed(0) : val.toFixed(0)}`}
            tick={{ fill: '#71717a', fontSize: 9 }}
            axisLine={false}
            tickLine={false}
            width={28}
            allowDataOverflow
          />
          <RechartsTooltip
            cursor={{ strokeDasharray: '3 3', stroke: '#71717a' }}
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const d = payload[0].payload as any
                return (
                  <div className="bg-black/90 border border-border rounded p-3 shadow-lg">
                    {d.price && <div className="text-brand-300 font-bold font-mono text-lg">${d.price.toFixed(2)}</div>}
                    {d.historicalFloor && (
                      <div className="text-gray-400 font-mono text-sm mt-1">
                        Floor: ${d.historicalFloor.toFixed(2)}
                      </div>
                    )}
                    <div className="text-muted-foreground text-xs mt-1">{d.date}</div>
                    {d.dailyVolume > 0 && (
                      <div className="text-blue-400 text-xs mt-1">
                        {d.dailyVolume} sale{d.dailyVolume > 1 ? 's' : ''} this day
                      </div>
                    )}
                    {d.treatment && (
                      <div className="mt-2">
                        <span
                          className="px-2 py-0.5 rounded text-[9px] uppercase font-bold"
                          style={{
                            backgroundColor: `${d.treatmentColor}30`,
                            color: d.treatmentColor
                          }}
                        >
                          {d.treatment}
                        </span>
                      </div>
                    )}
                  </div>
                )
              }
              return null
            }}
          />
          {/* Volume bars - rendered first so they're behind the price line */}
          <Bar
            yAxisId="volume"
            dataKey="dailyVolume"
            fill="#3b82f6"
            fillOpacity={0.2}
            stroke="none"
            barSize={8}
            name="Daily Volume"
          />
          {/* Historical floor price trend line - rendered second so it's behind price line */}
          {hasFloorHistory && (
            <Line
              yAxisId="price"
              type="monotone"
              dataKey="historicalFloor"
              stroke="#6b7280"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              dot={false}
              connectNulls
              name="Floor Trend"
            />
          )}
          {/* Main price line with smooth curve */}
          <Line
            yAxisId="price"
            type="monotone"
            dataKey="price"
            stroke="#7dd3a8"
            strokeWidth={2.5}
            connectNulls={false}
            dot={(props: any) => {
              const { cx, cy, payload } = props
              if (!cx || !cy || !payload || payload.price === null) return <g />

              if (payload.isActive) {
                const size = 5
                return (
                  <polygon
                    key={`dot-${cx}-${cy}`}
                    points={`${cx},${cy-size} ${cx+size},${cy} ${cx},${cy+size} ${cx-size},${cy}`}
                    fill={payload.treatmentColor || '#3b82f6'}
                    stroke="#0a0a0a"
                    strokeWidth={1.5}
                  />
                )
              }

              return (
                <circle
                  key={`dot-${cx}-${cy}`}
                  cx={cx}
                  cy={cy}
                  r={4}
                  fill={payload.treatmentColor || '#7dd3a8'}
                  stroke="#0a0a0a"
                  strokeWidth={1.5}
                />
              )
            }}
            activeDot={{ r: 6, fill: '#7dd3a8', stroke: '#0a0a0a', strokeWidth: 2 }}
          />
        </ComposedChart>
    </ResponsiveContainer>
  )
}

export default PriceHistoryChart
