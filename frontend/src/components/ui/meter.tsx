import { cn } from '@/lib/utils'

type MeterProps = {
  value: number
  max: number
  /** What is measured, for screen readers: "Storage used". */
  label: string
  className?: string
}

/** A thin usage bar (storage, counts). Turns to the danger colour at 90%. */
export function Meter({ value, max, label, className }: MeterProps) {
  const fraction = max > 0 ? Math.min(1, value / max) : 0
  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
      className={cn('h-1.5 w-full overflow-hidden rounded-full bg-surface-muted', className)}
    >
      <div
        className={cn('h-full rounded-full', fraction >= 0.9 ? 'bg-danger' : 'bg-primary')}
        style={{ width: `${fraction * 100}%` }}
      />
    </div>
  )
}
