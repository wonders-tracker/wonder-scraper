/**
 * TreatmentFloors - Price floors by treatment type
 */

import { cn } from '@/lib/utils'
import { TreatmentBadge } from '../TreatmentBadge'

type TreatmentFloor = {
  name: string
  min_price: number
  count: number
}

type TreatmentFloorsProps = {
  treatments: TreatmentFloor[]
  className?: string
}

export function TreatmentFloors({ treatments, className }: TreatmentFloorsProps) {
  if (!treatments || treatments.length === 0) {
    return null
  }

  return (
    <div className={cn('bg-card border border-border rounded-lg overflow-hidden', className)}>
      <div className="px-3 py-2 border-b border-border bg-muted/30">
        <span className="text-xs font-semibold">Treatment Floors</span>
      </div>
      <div className="divide-y divide-border/50">
        {treatments.map((treatment) => (
          <div
            key={treatment.name}
            className="flex items-center justify-between px-3 py-2"
          >
            <div className="flex items-center gap-2">
              <TreatmentBadge treatment={treatment.name} size="xs" linkToBrowse />
              <span className="text-[10px] text-muted-foreground">
                {treatment.count} sales
              </span>
            </div>
            <span className="text-sm font-mono font-medium text-brand-300">
              ${treatment.min_price.toFixed(2)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
