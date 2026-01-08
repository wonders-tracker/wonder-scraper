import * as React from "react"
import { cn } from "@/lib/utils"
import { formatPrice, formatDate } from "@/lib/formatters"

interface ChartDataPoint {
  date: string | Date
  value: number
  label?: string
  [key: string]: unknown
}

interface AccessibleChartWrapperProps {
  children: React.ReactNode
  data: ChartDataPoint[]
  title: string
  description?: string
  valueLabel?: string
  dateLabel?: string
  className?: string
  showDataTable?: boolean
  formatValue?: (value: number) => string
}

/**
 * Wrapper component that adds accessibility to charts
 * - Provides aria-label describing the chart data
 * - Includes a hidden data table for screen readers
 * - Shows the data table on focus for keyboard users
 */
export function AccessibleChartWrapper({
  children,
  data,
  title,
  description,
  valueLabel = "Value",
  dateLabel = "Date",
  className,
  showDataTable = true,
  formatValue = (v) => formatPrice(v),
}: AccessibleChartWrapperProps) {
  // Generate accessible description
  const chartDescription = React.useMemo(() => {
    if (data.length === 0) return `${title}. No data available.`

    const values = data.map((d) => d.value)
    const min = Math.min(...values)
    const max = Math.max(...values)
    const avg = values.reduce((a, b) => a + b, 0) / values.length

    const firstDate = formatDate(data[0].date, { format: "short" })
    const lastDate = formatDate(data[data.length - 1].date, { format: "short" })

    return `${title}. ${description || ""} Chart showing ${data.length} data points from ${firstDate} to ${lastDate}. Values range from ${formatValue(min)} to ${formatValue(max)}, with an average of ${formatValue(avg)}.`
  }, [data, title, description, formatValue])

  return (
    <div
      className={cn("relative", className)}
      role="img"
      aria-label={chartDescription}
    >
      {/* The actual chart */}
      <div aria-hidden="true">{children}</div>

      {/* Accessible data table - hidden but available to screen readers and on focus */}
      {showDataTable && data.length > 0 && (
        <details className="sr-only focus-within:not-sr-only focus-within:absolute focus-within:inset-0 focus-within:bg-background focus-within:z-10 focus-within:overflow-auto focus-within:p-4 focus-within:border focus-within:rounded-md">
          <summary className="cursor-pointer text-sm font-medium text-primary hover:underline focus:outline-none focus:ring-2 focus:ring-ring rounded">
            View chart data as table
          </summary>
          <div className="mt-4">
            <table className="w-full text-sm">
              <caption className="sr-only">{title} data table</caption>
              <thead>
                <tr className="border-b">
                  <th scope="col" className="text-left py-2 font-medium">
                    {dateLabel}
                  </th>
                  <th scope="col" className="text-right py-2 font-medium">
                    {valueLabel}
                  </th>
                  {data[0].label !== undefined && (
                    <th scope="col" className="text-left py-2 font-medium">
                      Label
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {data.map((point, index) => (
                  <tr key={index} className="border-b border-border/50">
                    <td className="py-2">
                      {formatDate(point.date, { format: "medium" })}
                    </td>
                    <td className="py-2 text-right font-mono">
                      {formatValue(point.value)}
                    </td>
                    {point.label !== undefined && (
                      <td className="py-2">{point.label}</td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </div>
  )
}

/**
 * Simple stats summary for chart accessibility
 */
export function ChartStatsSummary({
  data,
  formatValue = (v) => formatPrice(v),
}: {
  data: ChartDataPoint[]
  formatValue?: (value: number) => string
}) {
  if (data.length === 0) return null

  const values = data.map((d) => d.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const avg = values.reduce((a, b) => a + b, 0) / values.length
  const latest = values[values.length - 1]

  return (
    <div
      className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm"
      role="group"
      aria-label="Chart statistics"
    >
      <div>
        <dt className="text-muted-foreground text-caption">Latest</dt>
        <dd className="font-mono font-medium">{formatValue(latest)}</dd>
      </div>
      <div>
        <dt className="text-muted-foreground text-caption">Average</dt>
        <dd className="font-mono font-medium">{formatValue(avg)}</dd>
      </div>
      <div>
        <dt className="text-muted-foreground text-caption">Low</dt>
        <dd className="font-mono font-medium">{formatValue(min)}</dd>
      </div>
      <div>
        <dt className="text-muted-foreground text-caption">High</dt>
        <dd className="font-mono font-medium">{formatValue(max)}</dd>
      </div>
    </div>
  )
}

/**
 * Loading skeleton for charts
 */
export function ChartSkeleton({
  height = 300,
  className,
}: {
  height?: number
  className?: string
}) {
  return (
    <div
      className={cn("animate-pulse bg-muted rounded-md", className)}
      style={{ height }}
      role="img"
      aria-label="Loading chart..."
    >
      <div className="flex items-end justify-around h-full p-4 gap-2">
        {Array.from({ length: 12 }).map((_, i) => (
          <div
            key={i}
            className="bg-muted-foreground/20 rounded-t w-full"
            style={{ height: `${Math.random() * 60 + 20}%` }}
          />
        ))}
      </div>
    </div>
  )
}
