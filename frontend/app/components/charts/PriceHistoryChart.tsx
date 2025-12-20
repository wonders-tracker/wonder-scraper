/**
 * PriceHistoryChart - Lazy-loaded chart for card detail pages.
 *
 * This component is code-split to avoid loading recharts (378KB) on initial page load.
 * It only loads when the user visits a card detail page.
 */
import {
  AreaChart,
  Area,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from 'recharts'

type ChartDataPoint = {
  timestamp: number
  price: number
  date: string
  treatment?: string
  treatmentColor?: string
  isActive?: boolean
}

type Props = {
  data: ChartDataPoint[]
  chartType: 'scatter' | 'line'
  floorPrice?: number
  fmpPrice?: number
}

export function PriceHistoryChart({ data, chartType, floorPrice, fmpPrice }: Props) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        No price data available
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      {chartType === 'scatter' ? (
        <ScatterChart margin={{ top: 20, right: 60, bottom: 30, left: 20 }}>
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
            tickFormatter={(val) => `$${val >= 1000 ? `${(val/1000).toFixed(0)}k` : val.toFixed(0)}`}
            tick={{ fill: '#71717a', fontSize: 10 }}
            axisLine={{ stroke: '#27272a' }}
            tickLine={{ stroke: '#27272a' }}
            domain={['auto', 'auto']}
          />
          {fmpPrice && fmpPrice > 0 && (
            <ReferenceLine
              y={fmpPrice}
              stroke="#3b82f6"
              strokeDasharray="5 5"
              strokeWidth={1.5}
              label={{ value: `FMP $${fmpPrice.toFixed(2)}`, fill: '#3b82f6', fontSize: 9, position: 'insideTopLeft' }}
            />
          )}
          {floorPrice && floorPrice > 0 && (
            <ReferenceLine
              y={floorPrice}
              stroke="#7dd3a8"
              strokeDasharray="3 3"
              strokeWidth={1.5}
              label={{ value: `Floor $${floorPrice.toFixed(2)}`, fill: '#7dd3a8', fontSize: 9, position: 'insideTopLeft' }}
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
        <AreaChart data={data} margin={{ top: 20, right: 60, bottom: 30, left: 20 }}>
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
            tickFormatter={(val) => `$${val >= 1000 ? `${(val/1000).toFixed(0)}k` : val.toFixed(0)}`}
            tick={{ fill: '#71717a', fontSize: 10 }}
            axisLine={{ stroke: '#27272a' }}
            tickLine={{ stroke: '#27272a' }}
            domain={['auto', 'auto']}
          />
          {fmpPrice && fmpPrice > 0 && (
            <ReferenceLine
              y={fmpPrice}
              stroke="#3b82f6"
              strokeDasharray="5 5"
              strokeWidth={1.5}
              label={{ value: `FMP $${fmpPrice.toFixed(2)}`, fill: '#3b82f6', fontSize: 9, position: 'insideTopLeft' }}
            />
          )}
          {floorPrice && floorPrice > 0 && (
            <ReferenceLine
              y={floorPrice}
              stroke="#7dd3a8"
              strokeDasharray="3 3"
              strokeWidth={1.5}
              label={{ value: `Floor $${floorPrice.toFixed(2)}`, fill: '#7dd3a8', fontSize: 9, position: 'insideTopLeft' }}
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
                  </div>
                )
              }
              return null
            }}
          />
          <Area
            type="monotone"
            dataKey="price"
            stroke="#7dd3a8"
            strokeWidth={2}
            fill="url(#priceGradient)"
            dot={false}
            activeDot={{ r: 6, fill: '#7dd3a8', stroke: '#0a0a0a', strokeWidth: 2 }}
          />
        </AreaChart>
      )}
    </ResponsiveContainer>
  )
}

export default PriceHistoryChart
