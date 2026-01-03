import { Tooltip } from './ui/tooltip'

type Props = {
  score: number // 0.0 - 1.0
  size?: 'xs' | 'sm' | 'md'
}

const sizes = {
  xs: 'w-1.5 h-1.5',
  sm: 'w-2 h-2',
  md: 'w-2.5 h-2.5',
}

export function ConfidenceIndicator({ score, size = 'sm' }: Props) {
  const color = score >= 0.7 ? 'bg-green-500' : score >= 0.4 ? 'bg-yellow-500' : 'bg-red-500'
  const label = score >= 0.7 ? 'High' : score >= 0.4 ? 'Medium' : 'Low'

  return (
    <Tooltip content={`${label} confidence (${(score * 100).toFixed(0)}%)`}>
      <div className={`${sizes[size]} rounded-full ${color}`} />
    </Tooltip>
  )
}

export default ConfidenceIndicator
