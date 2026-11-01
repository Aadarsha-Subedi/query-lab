import { Clock01Icon } from '@hugeicons/core-free-icons'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'

import { QueryBoundary } from '@/components/QueryBoundary'
import { EmptyState } from '@/components/ui/data-state'
import { Skeleton } from '@/components/ui/skeleton'
import { RunStatusBadge } from '@/features/ask/RunStatusBadge'
import { historyQuery } from '@/features/history/api'
import { formatRelative } from '@/lib/format'

const SHOWN = 3
const LATEST = { ordering: '-created_at' } as const

/** The last few questions, with their status. Its own loading / error / empty / success box. */
export function RecentRuns() {
  const query = useQuery(historyQuery(LATEST))
  return (
    <QueryBoundary
      query={query}
      errorTitle="Couldn't load your recent questions."
      isEmpty={(page) => page.data.length === 0}
      empty={
        <EmptyState
          icon={Clock01Icon}
          title="No questions yet"
          description="Your recent questions will appear here once you ask one."
        />
      }
      loading={
        <div className="flex flex-col gap-2">
          {Array.from({ length: SHOWN }, (_, index) => (
            <Skeleton key={index} className="h-11 w-full" />
          ))}
        </div>
      }
    >
      {(page) => (
        <ul className="flex flex-col divide-y rounded-lg border bg-surface">
          {page.data.slice(0, SHOWN).map((run) => (
            <li key={run.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3">
              <Link
                to="/ask"
                search={{ run: run.id }}
                className="min-w-0 flex-1 truncate underline-offset-4 hover:underline"
              >
                {run.question}
              </Link>
              <RunStatusBadge status={run.status} />
              <span className="text-small text-muted-foreground">{formatRelative(run.created_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </QueryBoundary>
  )
}
