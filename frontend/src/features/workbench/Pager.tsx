import { ArrowLeft01Icon, ArrowRight01Icon } from '@hugeicons/core-free-icons'

import { Button } from '@/components/ui/button'
import { formatNumber } from '@/lib/format'

/** Previous / Next for a paginated list (meta.count, meta.limit, meta.offset). */
export function Pager({
  meta,
  onOffset,
}: {
  meta: { count: number; limit: number; offset: number }
  onOffset: (offset: number | undefined) => void
}) {
  const { count, limit, offset } = meta
  return (
    <nav aria-label="Pages" className="flex items-center justify-between gap-3">
      <span className="text-small text-muted-foreground">
        {count === 0
          ? '0'
          : `${formatNumber(offset + 1)} to ${formatNumber(Math.min(offset + limit, count))}`}{' '}
        of {formatNumber(count)}
      </span>
      <div className="flex gap-2">
        <Button
          variant="secondary"
          size="sm"
          icon={ArrowLeft01Icon}
          disabled={offset === 0}
          onClick={() => {
            onOffset(Math.max(0, offset - limit) || undefined)
          }}
        >
          Previous
        </Button>
        <Button
          variant="secondary"
          size="sm"
          icon={ArrowRight01Icon}
          iconPosition="end"
          disabled={offset + limit >= count}
          onClick={() => {
            onOffset(offset + limit)
          }}
        >
          Next
        </Button>
      </div>
    </nav>
  )
}
