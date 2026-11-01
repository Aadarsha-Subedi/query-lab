import { useQuery } from '@tanstack/react-query'

import { QueryBoundary } from '@/components/QueryBoundary'
import { CodeBlock } from '@/components/typography/Code'
import { Heading } from '@/components/typography/Heading'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { RunTimeline } from '@/features/ask/RunTimeline'
import { formatDateTime, formatDuration, formatNumber } from '@/lib/format'

import { traceDetailQuery, type TraceDetail } from './api'
import { SqlDiff } from './SqlDiff'

function Detail({ run }: { run: TraceDetail }) {
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-2">
        <Heading level={2}>{run.question}</Heading>
        <Badge>{run.status.replace('_', ' ')}</Badge>
        {run.edited && <Badge variant="primary">edited</Badge>}
        {run.feedback && (
          <Badge variant={run.feedback === 'up' ? 'success' : 'danger'}>thumbs {run.feedback}</Badge>
        )}
      </div>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-small sm:grid-cols-4">
        <dt className="text-muted-foreground">Model</dt>
        <dd>
          {run.provider} / {run.model}
        </dd>
        <dt className="text-muted-foreground">Prompt</dt>
        <dd>{run.prompt_version}</dd>
        <dt className="text-muted-foreground">When</dt>
        <dd>{formatDateTime(run.created_at)}</dd>
        <dt className="text-muted-foreground">Time</dt>
        <dd>{formatDuration(run.latency_ms / 1000)}</dd>
        <dt className="text-muted-foreground">LLM calls</dt>
        <dd>{formatNumber(run.llm_calls)}</dd>
        <dt className="text-muted-foreground">Tokens</dt>
        <dd>{formatNumber(run.input_tokens + run.output_tokens)}</dd>
        <dt className="text-muted-foreground">Revisions</dt>
        <dd>{formatNumber(run.revisions)}</dd>
        <dt className="text-muted-foreground">Check</dt>
        <dd>{run.check || 'none'}</dd>
      </dl>
      {run.error_code && <p className="text-body text-danger-foreground">Ended with {run.error_code}.</p>}
      <section aria-label="SQL" className="flex flex-col gap-2">
        {run.diff ? (
          <>
            <Heading level={3}>Proposed against approved</Heading>
            <SqlDiff before={run.proposed_sql} after={run.approved_sql} />
          </>
        ) : (
          run.final_sql && (
            <>
              <Heading level={3}>SQL</Heading>
              <CodeBlock code={run.final_sql} />
            </>
          )
        )}
      </section>
      <section aria-label="Steps" className="flex flex-col gap-2">
        <Heading level={3}>Steps</Heading>
        <RunTimeline steps={run.steps} />
      </section>
    </div>
  )
}

export function TraceDetailView({ runId }: { runId: number }) {
  const query = useQuery(traceDetailQuery(runId))
  return (
    <QueryBoundary
      query={query}
      errorTitle="Couldn't load this trace."
      loading={<Skeleton className="h-64 w-full" />}
    >
      {(run) => <Detail run={run} />}
    </QueryBoundary>
  )
}
