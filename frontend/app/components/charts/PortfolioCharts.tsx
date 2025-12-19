/**
 * PortfolioCharts - Lazy-loaded chart components for portfolio page.
 */
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
} from 'recharts'

type PieData = {
  name: string
  value: number
  color: string
}

type LineData = {
  date: string
  value: number
}

type PortfolioPieChartProps = {
  data: PieData[]
}

type PortfolioLineChartProps = {
  data: LineData[]
}

export function PortfolioPieChart({ data }: PortfolioPieChartProps) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={40}
          outerRadius={70}
          paddingAngle={2}
          dataKey="value"
        >
          {data.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={entry.color} />
          ))}
        </Pie>
        <RechartsTooltip
          content={({ active, payload }) => {
            if (active && payload && payload.length) {
              const d = payload[0].payload as PieData
              return (
                <div className="bg-card border border-border rounded p-2 text-xs shadow-lg">
                  <div className="font-bold">{d.name}</div>
                  <div className="text-muted-foreground">${d.value.toLocaleString()}</div>
                </div>
              )
            }
            return null
          }}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}

export function PortfolioLineChart({ data }: PortfolioLineChartProps) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#333" />
        <XAxis
          dataKey="date"
          tick={{ fill: '#71717a', fontSize: 10 }}
          axisLine={{ stroke: '#27272a' }}
        />
        <YAxis
          tick={{ fill: '#71717a', fontSize: 10 }}
          axisLine={{ stroke: '#27272a' }}
          tickFormatter={(val) => `$${val >= 1000 ? `${(val/1000).toFixed(0)}k` : val}`}
        />
        <RechartsTooltip
          content={({ active, payload, label }) => {
            if (active && payload && payload.length) {
              return (
                <div className="bg-card border border-border rounded p-2 text-xs shadow-lg">
                  <div className="font-bold">{label}</div>
                  <div className="text-brand-300">${payload[0].value?.toLocaleString()}</div>
                </div>
              )
            }
            return null
          }}
        />
        <Line
          type="monotone"
          dataKey="value"
          stroke="#7dd3a8"
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

export default { PortfolioPieChart, PortfolioLineChart }
