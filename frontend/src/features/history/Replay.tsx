import { ArrowLeft01Icon, ArrowRight01Icon } from '@hugeicons/core-free-icons'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Heading } from '@/components/typography/Heading'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { CodeBlock } from '@/components/typography/Code'
import { replayQuery } from '@/features/history/replay-api'
import { RunTimeline } from '@/features/ask/RunTimeline'
import { formatDateTime } from '@/lib/format'

import type { RunDetail } from '@/features/ask/types'

function Stepper({ run }: { run: RunDetail }) {
  const [shown, setShown] = useState(Math.min(1, run.steps.length))
  const steps = run.steps.slice(0, shown)
  const current = run.steps[shown - 1]
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Heading level={2}>{run.question}</Heading>
        <Badge>{run.status}</Badge>
        <span className="text-small text-muted-foreground">{formatDateTime(run.created_at)}</span>
      </div>
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          icon={ArrowLeft01Icon}
          disabled={shown <= 1}
          onClick={() => {
            setShown(shown - 1)
          }}
        >
          Previous step
        </Button>
        <span aria-live="polite" className="text-small text-muted-foreground">
          Step {shown} of {run.steps.length}
        </span>
        <Button
          variant="secondary"
          size="sm"
          icon={ArrowRight01Icon}
          iconPosition="end"
          disabled={shown >= run.steps.length}
          onClick={() => {
            setShown(shown + 1)
          }}
        >
          Next step
        </Button>
      </div>
      <RunTimeline steps={steps} />
      {current && Object.keys(current.input).length > 0 && (
        <section aria-label="Step input">
          <p className="mb-1 text-small font-medium">Input of this step</p>
          <CodeBlock code={JSON.stringify(current.input, null, 2)} language="text" />
        </section>
      )}
      {run.final_sql && shown === run.steps.length && (
        <section aria-label="Final SQL">
          <p className="mb-1 text-small font-medium">Final SQL</p>
          <CodeBlock code={run.final_sql} />
        </section>
      )}
    </div>
  )
}

/** A stored run played back one step at a time. No model call and no query: the API replays the trace. */
export function Replay({ runId }: { runId: number }) {
  const query = useQuery(replayQuery(runId))
  return (
    <QueryBoundary
      query={query}
      errorTitle="Couldn't load this replay."
      isEmpty={(run) => run.steps.length === 0}
      empty={<p className="text-body text-muted-foreground">This run has no recorded steps.</p>}
      loading={
        <div className="flex flex-col gap-3">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      }
    >
      {(run) => <Stepper key={run.id} run={run} />}
    </QueryBoundary>
  )
}
