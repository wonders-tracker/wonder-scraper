/**
 * PriceHistoryChart - Lazy-loaded chart for card detail pages.
 *
 * This component is code-split to avoid loading recharts (378KB) on initial page load.
 * It only loads when the user visits a card detail page.
 */
import { useMemo } from 'react'
import {
  ComposedChart,
  Area,
  Line,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from 'recharts'

// Note: AreaChart removed - now using ComposedChart for combined price + floor trend

type ChartDataPoint = {
  timestamp: number
  price: number
  date: string
  treatment?: string
  treatmentColor?: string
  isActive?: boolean
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
  chartType: 'scatter' | 'line'
  floorPrice?: number
  lowestAsk?: number
  floorHistory?: FloorHistoryPoint[]
}

// Generate well-spaced log scale ticks
function generateLogTicks(min: number, max: number): number[] {
  const ticks: number[] = []
  const logMin = Math.floor(Math.log10(min))
  const logMax = Math.ceil(Math.log10(max))

  // Standard "nice" multipliers for log scale
  const multipliers = [1, 2, 5]

  for (let power = logMin; power <= logMax; power++) {
    for (const mult of multipliers) {
      const val = mult * Math.pow(10, power)
      if (val >= min * 0.9 && val <= max * 1.1) {
        ticks.push(val)
      }
    }
  }

  // If we have too many ticks (>7), reduce to just powers of 10 and maybe 5s
  if (ticks.length > 7) {
    const filtered = ticks.filter(t => {
      const mantissa = t / Math.pow(10, Math.floor(Math.log10(t)))
      return mantissa === 1 || mantissa === 5
    })
    // If still too many, just use powers of 10
    if (filtered.length > 6) {
      return ticks.filter(t => {
        const mantissa = t / Math.pow(10, Math.floor(Math.log10(t)))
        return mantissa === 1
      })
    }
    return filtered
  }

  return ticks
}

export function PriceHistoryChart({ data, chartType, floorPrice, lowestAsk, floorHistory }: Props) {
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
  const refPrices = [floorPrice, lowestAsk].filter((p): p is number => p !== undefined && p > 0)
  const allPrices = [...prices, ...floorPrices, ...refPrices]

  // For log scale, find min/max and add padding in log space
  const minPrice = Math.min(...allPrices)
  const maxPrice = Math.max(...allPrices)

  // Pad in log space for even visual padding
  const logMin = Math.log10(minPrice)
  const logMax = Math.log10(maxPrice)
  const logPadding = (logMax - logMin) * 0.1

  const yMin = Math.pow(10, logMin - logPadding)
  const yMax = Math.pow(10, logMax + logPadding)

  // Generate clean log scale ticks
  const yTicks = generateLogTicks(yMin, yMax)

  // Check if we have floor history to show
  const hasFloorHistory = floorHistoryData.length > 1

  return (
    <ResponsiveContainer width="100%" height="100%">
      {chartType === 'scatter' ? (
        <ScatterChart margin={{ top: 20, right: 50, bottom: 30, left: 20 }}>
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
          <YAxis
            dataKey="price"
            orientation="right"
            scale="log"
            domain={[yMin, yMax]}
            ticks={yTicks}
            tickFormatter={(val) => `$${val >= 1000 ? `${(val/1000).toFixed(0)}k` : val < 10 ? val.toFixed(2) : val.toFixed(0)}`}
            tick={{ fill: '#71717a', fontSize: 10 }}
            axisLine={{ stroke: '#27272a' }}
            tickLine={{ stroke: '#27272a' }}
            allowDataOverflow
          />
          {floorPrice && floorPrice > 0 && (
            <ReferenceLine
              y={floorPrice}
              stroke="#7dd3a8"
              strokeDasharray="3 3"
              strokeWidth={1.5}
              label={{ value: `Floor $${floorPrice >= 1000 ? `${(floorPrice/1000).toFixed(1)}k` : floorPrice.toFixed(0)}`, fill: '#7dd3a8', fontSize: 9, position: 'insideBottomRight' }}
            />
          )}
          {lowestAsk && lowestAsk > 0 && (
            <ReferenceLine
              y={lowestAsk}
              stroke="#3b82f6"
              strokeDasharray="5 5"
              strokeWidth={1.5}
              label={{ value: `Ask $${lowestAsk >= 1000 ? `${(lowestAsk/1000).toFixed(1)}k` : lowestAsk.toFixed(0)}`, fill: '#3b82f6', fontSize: 9, position: 'insideTopRight' }}
            />
          )}
          <RechartsTooltip
            cursor={{ strokeDasharray: '3 3', stroke: '#71717a' }}
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const d = payload[0].payload as ChartDataPoint
                return (
                  <div className="bg-black/90 border border-border rounded p-3 shadow-lg">
                    <div className="text-brand-300 font-bold font-mono text-lg">${d.price.toFixed(2)}</div>
                    <div className="text-muted-foreground text-xs mt-1">{d.date}</div>
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
                    <div className="text-[10px] text-muted-foreground mt-1">
                      {d.isActive ? '◆ Active Listing' : '● Sold'}
                    </div>
                  </div>
                )
              }
              return null
            }}
          />
          <Scatter
            data={data}
            shape={(props: any) => {
              const { cx, cy, payload } = props
              if (!cx || !cy || !payload) return <g />

              if (payload.isActive) {
                const size = 7
                return (
                  <polygon
                    points={`${cx},${cy-size} ${cx+size},${cy} ${cx},${cy+size} ${cx-size},${cy}`}
                    fill={payload.treatmentColor || '#3b82f6'}
                    stroke="#0a0a0a"
                    strokeWidth={2}
                    style={{ filter: 'drop-shadow(0 0 4px rgba(59,130,246,0.5))' }}
                  />
                )
              }

              return (
                <circle
                  cx={cx}
                  cy={cy}
                  r={6}
                  fill={payload.treatmentColor || '#7dd3a8'}
                  stroke="#0a0a0a"
                  strokeWidth={2}
                  style={{ filter: 'drop-shadow(0 0 3px rgba(0,0,0,0.5))' }}
                />
              )
            }}
          />
        </ScatterChart>
      ) : (
        <ComposedChart data={hasFloorHistory ? combinedData : data} margin={{ top: 20, right: 50, bottom: 30, left: 20 }}>
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
          <YAxis
            orientation="right"
            scale="log"
            domain={[yMin, yMax]}
            ticks={yTicks}
            tickFormatter={(val) => `$${val >= 1000 ? `${(val/1000).toFixed(0)}k` : val < 10 ? val.toFixed(2) : val.toFixed(0)}`}
            tick={{ fill: '#71717a', fontSize: 10 }}
            axisLine={{ stroke: '#27272a' }}
            tickLine={{ stroke: '#27272a' }}
            allowDataOverflow
          />
          {/* Only show current floor reference line if no historical floor data */}
          {!hasFloorHistory && floorPrice && floorPrice > 0 && (
            <ReferenceLine
              y={floorPrice}
              stroke="#7dd3a8"
              strokeDasharray="3 3"
              strokeWidth={1.5}
              label={{ value: `Floor $${floorPrice >= 1000 ? `${(floorPrice/1000).toFixed(1)}k` : floorPrice.toFixed(0)}`, fill: '#7dd3a8', fontSize: 9, position: 'insideBottomRight' }}
            />
          )}
          {lowestAsk && lowestAsk > 0 && (
            <ReferenceLine
              y={lowestAsk}
              stroke="#3b82f6"
              strokeDasharray="5 5"
              strokeWidth={1.5}
              label={{ value: `Ask $${lowestAsk >= 1000 ? `${(lowestAsk/1000).toFixed(1)}k` : lowestAsk.toFixed(0)}`, fill: '#3b82f6', fontSize: 9, position: 'insideTopRight' }}
            />
          )}
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
          {/* Historical floor price trend line - rendered first so it's behind price line */}
          {hasFloorHistory && (
            <Line
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
          <Area
            type="monotone"
            dataKey="price"
            stroke="#7dd3a8"
            strokeWidth={2}
            fill="url(#priceGradient)"
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
      )}
    </ResponsiveContainer>
  )
}

export default PriceHistoryChart
