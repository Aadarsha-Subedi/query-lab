import { AlertCircleIcon, CheckmarkCircle02Icon } from '@hugeicons/core-free-icons'

import { Badge } from '@/components/ui/badge'
import { Icon } from '@/components/ui/icon'
import { describeError } from '@/lib/api/errors'
import { formatDuration } from '@/lib/format'

import { describeStep } from './step-text'
import type { Step } from './types'

/** What the agent did, step by step, in plain words (never the raw tool output). */
export function RunTimeline({ steps }: { steps: Step[] }) {
  if (steps.length === 0) return null
  return (
    <ol aria-label="What the agent did" className="flex flex-col gap-3">
      {steps.map((step) => {
        const failed = step.status !== 'ok' && step.status !== ''
        const { stage, note } = describeStep(step)
        const problem = failed && step.error_code ? describeError(step.error_code, '').message : null
        return (
          <li key={step.index} className="flex gap-2">
            <Icon
              icon={failed ? AlertCircleIcon : CheckmarkCircle02Icon}
              size="sm"
              className={failed ? 'mt-0.5 shrink-0 text-danger' : 'mt-0.5 shrink-0 text-success'}
            />
            <div className="flex min-w-0 flex-1 flex-col gap-0.5">
              <div className="flex items-center gap-2 text-body">
                <span className="font-medium">{stage}</span>
                {failed && <Badge variant="danger">{step.error_code || step.status}</Badge>}
                <span className="ml-auto text-small text-muted-foreground">
                  {formatDuration(step.latency_ms / 1000)}
                </span>
              </div>
              {(problem ?? note) && (
                <p className="text-small whitespace-pre-line text-muted-foreground">{problem ?? note}</p>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
