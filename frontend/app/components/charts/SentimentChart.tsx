/**
 * SentimentChart - Lazy-loaded chart component for market sentiment visualization.
 *
 * This component is code-split from the main market page to avoid loading
 * the 368KB recharts bundle on initial page load.
 */
import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
  ReferenceLine,
} from 'recharts'
import clsx from 'clsx'

type SentimentData = {
  name: string
  value: number
  fill: string
  topCard?: {
    name: string
    price_delta_24h: number
  }
}

type Props = {
  data: SentimentData[]
}

export function SentimentChart({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={data} margin={{ left: 10, right: 30, bottom: 20 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} interval={0} />
        <YAxis tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
        <ReferenceLine y={0} stroke="hsl(var(--border))" />
        <RechartsTooltip
          content={({ active, payload }) => {
            if (active && payload && payload.length) {
              const d = payload[0].payload as SentimentData
              return (
                <div className="bg-card border border-border rounded-md p-2 text-xs shadow-lg">
                  <div className="font-bold mb-1">{d.name}</div>
                  <div className="text-muted-foreground">{d.value} assets</div>
                  {d.topCard && (
                    <div className="mt-1 pt-1 border-t border-border">
                      <span className="text-muted-foreground">Top: </span>
                      <span className="font-bold">{d.topCard.name}</span>
                      <span className={clsx("ml-1 font-mono", d.topCard.price_delta_24h > 0 ? "text-brand-300" : "text-red-500")}>
                        {d.topCard.price_delta_24h > 0 ? '+' : ''}{d.topCard.price_delta_24h?.toFixed(1)}%
                      </span>
                    </div>
                  )}
                </div>
              )
            }
            return null
          }}
        />
        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
          {data.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={entry.fill} />
          ))}
        </Bar>
      </ComposedChart>
    </ResponsiveContainer>
  )
}

export default SentimentChart
