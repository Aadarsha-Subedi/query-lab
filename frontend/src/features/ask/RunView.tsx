import { ArrowReloadHorizontalIcon } from '@hugeicons/core-free-icons'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Bubble, BubbleContent } from '@/components/ui/bubble'
import { Button } from '@/components/ui/button'
import { Message, MessageContent } from '@/components/ui/message'
import { Skeleton } from '@/components/ui/skeleton'
import { describeError } from '@/lib/api/errors'

import { ApprovalCard } from './ApprovalCard'
import { runQuery } from './api'
import { Feedback } from './Feedback'
import { ResultTable } from './ResultTable'
import { runStatusLabel } from './run-status'
import { Reasoning } from './Reasoning'
import { describeStep } from './step-text'
import { mergeSteps } from './steps'
import { isFinished, type RunDetail, type Step } from './types'
import { useRunStream } from './useRunStream'

/** The running agent, in its own words: built from the steps that have really arrived. */
function LiveReasoning({ steps }: { steps: Step[] }) {
  const texts = steps.map(describeStep)
  const sources = [...new Set(texts.flatMap((text) => (text.source ? [text.source] : [])))]
  return (
    <Reasoning
      stages={texts.length > 0 ? texts.map((text) => text.stage) : ['Getting started']}
      reasoning={texts.flatMap((text) => (text.note ? [text.note] : []))}
      sources={sources}
    />
  )
}

function Body({
  run,
  stream,
  reconnect,
}: {
  run: RunDetail
  stream: ReturnType<typeof useRunStream>['state']
  reconnect: () => void
}) {
  const steps = mergeSteps(run.steps, stream.steps)
  const failure = run.error_code ? describeError(run.error_code, '') : null
  return (
    <div className="flex flex-col gap-6">
      <Message align="end">
        <MessageContent>
          <Bubble align="end" variant="muted">
            <BubbleContent className="text-body whitespace-pre-wrap">{run.question}</BubbleContent>
          </Bubble>
        </MessageContent>
      </Message>
      <Message>
        <MessageContent className="gap-4">
          <div aria-live="polite" className="sr-only">
            {runStatusLabel(run.status)}
          </div>
          {failure && (
            <p role="alert" className="text-body text-danger-foreground">
              {failure.message} {failure.hint}
            </p>
          )}
          {run.status === 'running' && <LiveReasoning steps={steps} />}
          {(run.status === 'cancelled' || run.status === 'expired') && (
            <p className="text-small text-muted-foreground">
              {run.status === 'cancelled'
                ? 'This run was cancelled.'
                : 'This run expired before it was approved.'}
            </p>
          )}
          {stream.phase === 'dropped' && !isFinished(run.status) && run.status !== 'awaiting_approval' && (
            <div
              role="alert"
              className="flex flex-wrap items-center gap-3 rounded-md border bg-surface-muted p-3 text-body"
            >
              <span>
                {stream.failure
                  ? `${describeError(stream.failure, 'The live connection could not open.').message} ${describeError(stream.failure, '').hint}`
                  : 'The live connection was lost. The run keeps going on the server.'}
              </span>
              <Button size="sm" variant="secondary" icon={ArrowReloadHorizontalIcon} onClick={reconnect}>
                Reconnect
              </Button>
            </div>
          )}
          {run.status === 'awaiting_approval' && run.pending && (
            <ApprovalCard runId={run.id} pending={run.pending} onDecided={reconnect} />
          )}
          {run.status === 'succeeded' && (
            <>
              {run.has_result && <ResultTable runId={run.id} />}
              <Feedback runId={run.id} vote={run.feedback ?? null} />
            </>
          )}
        </MessageContent>
      </Message>
    </div>
  )
}

/** One run: live while it works, then approval, result and feedback. All in one box. */
export function RunView({ runId }: { runId: number }) {
  const query = useQuery(runQuery(runId))
  const { state: stream, reconnect } = useRunStream(runId)
  const queryClient = useQueryClient()

  // The stream says when the run paused or finished; fetch the stored run once then.
  const endedFor = useRef<string | null>(null)
  useEffect(() => {
    if (stream.phase !== 'ended') return
    const key = `${runId}:${stream.status ?? ''}:${stream.lastIndex ?? ''}`
    if (endedFor.current === key) return
    endedFor.current = key
    void queryClient.invalidateQueries({ queryKey: ['run', runId], exact: true })
    void queryClient.invalidateQueries({ queryKey: ['agent-limits'] })
  }, [stream.phase, stream.status, stream.lastIndex, runId, queryClient])

  return (
    <QueryBoundary
      query={query}
      errorTitle="Couldn't load this run."
      loading={
        <div className="flex flex-col gap-3">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      }
    >
      {(run) => <Body run={run} stream={stream} reconnect={reconnect} />}
    </QueryBoundary>
  )
}
