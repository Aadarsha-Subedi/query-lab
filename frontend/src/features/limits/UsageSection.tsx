import { useQuery } from '@tanstack/react-query'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Heading } from '@/components/typography/Heading'
import { Badge } from '@/components/ui/badge'
import { Progress, ProgressLabel, ProgressValue } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDateTime, formatNumber } from '@/lib/format'
import { cn } from '@/lib/utils'

import { limitsQuery, type AgentLimits } from './api'

/** One limit as a shadcn Progress: a label, "used of allowed", and a bar that turns red when nearly full. */
function LimitRow({ label, used, allowed }: { label: string; used: number; allowed: number }) {
  const nearlyFull = allowed > 0 && used / allowed >= 0.9
  return (
    <Progress
      value={used}
      max={allowed}
      className={cn('gap-2', nearlyFull && '[&_[data-slot=progress-indicator]]:bg-danger')}
    >
      <ProgressLabel className="text-body">{label}</ProgressLabel>
      <ProgressValue className="text-body">
        {(_formatted, value) => `${formatNumber(value ?? used)} of ${formatNumber(allowed)}`}
      </ProgressValue>
    </Progress>
  )
}

function Details({ limits }: { limits: AgentLimits }) {
  const { default_key, unfinished_runs, streams, has_own_key } = limits
  return (
    <div className="flex max-w-[var(--reading-max)] flex-col gap-5">
      {has_own_key ? (
        <p className="text-body">
          <span className="text-muted-foreground">Your own key: </span>No daily limit from us
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          <LimitRow
            label="Questions today on the shared key"
            used={default_key.used}
            allowed={default_key.allowed}
          />
          <p className="text-small text-muted-foreground">Resets {formatDateTime(default_key.resets_at)}</p>
        </div>
      )}
      <LimitRow label="Open questions" used={unfinished_runs.count} allowed={unfinished_runs.allowed} />
      <LimitRow label="Live views" used={streams.open} allowed={streams.allowed} />
    </div>
  )
}

function Summary({ limits }: { limits: AgentLimits }) {
  const { default_key, has_own_key, unfinished_runs } = limits
  const exhausted = !has_own_key && default_key.remaining <= 0
  const runsFull = unfinished_runs.count >= unfinished_runs.allowed
  const label = exhausted
    ? 'Daily limit reached'
    : runsFull
      ? 'Open questions full'
      : has_own_key
        ? 'Own key'
        : `${formatNumber(default_key.remaining)} left today`
  return <Badge variant={exhausted || runsFull ? 'danger' : 'neutral'}>{label}</Badge>
}

/**
 * What is left before a limit: the shared key's daily asks, open questions and live views. Read once
 * (no refresh timer); it has its own loading and error box. Open questions are still running or
 * waiting for approval; live views are pages showing a run as it happens.
 */
export function UsageSection() {
  const query = useQuery(limitsQuery())
  return (
    <section aria-labelledby="usage" className="flex flex-col gap-4">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div className="flex max-w-[var(--reading-max)] flex-col gap-1">
          <Heading level={2} id="usage">
            Usage
          </Heading>
          <p className="text-body text-muted-foreground">
            What is left before a limit. Open questions are still running or waiting for your approval. Live
            views are pages showing a run as it happens.
          </p>
        </div>
        {query.data && <Summary limits={query.data} />}
      </div>
      <QueryBoundary
        query={query}
        errorTitle="Couldn't load your usage."
        loading={<Skeleton className="h-24 w-full max-w-[var(--reading-max)]" />}
      >
        {(limits) => <Details limits={limits} />}
      </QueryBoundary>
    </section>
  )
}
