import { Badge } from '@/components/ui/badge'

type Variant = 'neutral' | 'primary' | 'success' | 'warning' | 'danger'

/** One wording and colour for a run's status, wherever it is shown. */
export const RUN_STATUS: Record<string, { label: string; variant: Variant }> = {
  running: { label: 'Working', variant: 'primary' },
  awaiting_approval: { label: 'Needs approval', variant: 'warning' },
  succeeded: { label: 'Done', variant: 'success' },
  failed: { label: 'Failed', variant: 'danger' },
  cancelled: { label: 'Cancelled', variant: 'neutral' },
  expired: { label: 'Expired', variant: 'neutral' },
}

export function runStatusLabel(status: string): string {
  return RUN_STATUS[status]?.label ?? status
}

export function RunStatusBadge({ status }: { status: string }) {
  const { label, variant } = RUN_STATUS[status] ?? { label: status, variant: 'neutral' as const }
  return <Badge variant={variant}>{label}</Badge>
}
