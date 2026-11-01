import { RefreshIcon } from '@hugeicons/core-free-icons'
import { useQuery } from '@tanstack/react-query'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDateTime, formatNumber } from '@/lib/format'

import { limitsQuery, type AgentLimits } from './api'

function Details({ limits }: { limits: AgentLimits }) {
  const { default_key, unfinished_runs, streams, has_own_key } = limits
  return (
    <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-2 text-small">
      <dt className="text-muted-foreground">{has_own_key ? 'Your own key' : 'Shared key, used today'}</dt>
      <dd>
        {has_own_key
          ? 'No daily limit from us'
          : `${formatNumber(default_key.used)} of ${formatNumber(default_key.allowed)}`}
      </dd>
      {!has_own_key && (
        <>
          <dt className="text-muted-foreground">Resets</dt>
          <dd>{formatDateTime(default_key.resets_at)}</dd>
        </>
      )}
      <dt className="text-muted-foreground">Open runs</dt>
      <dd>
        {formatNumber(unfinished_runs.count)} of {formatNumber(unfinished_runs.allowed)}
      </dd>
      <dt className="text-muted-foreground">Live streams</dt>
      <dd>
        {formatNumber(streams.open)} of {formatNumber(streams.allowed)}
      </dd>
    </dl>
  )
}

/**
 * Header chip: questions left on the shared key today. It has its own loading and error
 * state and is read once; it refreshes when the page is reloaded or the user presses it.
 */
export function LimitsIndicator({ workspace }: { workspace?: number }) {
  const query = useQuery(limitsQuery(workspace))

  if (query.isPending || (query.isError && query.isFetching)) {
    return <Skeleton aria-busy="true" className="h-6 w-28" />
  }
  if (query.isError) {
    return (
      <Button
        variant="ghost"
        size="sm"
        icon={RefreshIcon}
        onClick={() => {
          void query.refetch()
        }}
      >
        Limits unavailable
      </Button>
    )
  }

  const { default_key, has_own_key, unfinished_runs } = query.data
  const exhausted = !has_own_key && default_key.remaining <= 0
  const runsFull = unfinished_runs.count >= unfinished_runs.allowed
  const label = has_own_key ? 'Own key' : `${formatNumber(default_key.remaining)} left today`

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Usage limits: ${label}`}
          className="rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Badge variant={exhausted || runsFull ? 'danger' : 'neutral'}>
            {exhausted ? 'Daily limit reached' : runsFull ? 'Open runs full' : label}
          </Badge>
        </button>
      </PopoverTrigger>
      <PopoverContent align="end">
        <Details limits={query.data} />
      </PopoverContent>
    </Popover>
  )
}
