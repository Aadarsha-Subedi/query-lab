import { Badge } from '@/components/ui/badge'

import { RUN_STATUS } from './run-status'

export function RunStatusBadge({ status }: { status: string }) {
  const { label, variant } = RUN_STATUS[status] ?? { label: status, variant: 'neutral' as const }
  return <Badge variant={variant}>{label}</Badge>
}
