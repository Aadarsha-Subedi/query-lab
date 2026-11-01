import { AlertCircleIcon, CheckmarkCircle02Icon } from '@hugeicons/core-free-icons'

import { Badge } from '@/components/ui/badge'
import { Icon } from '@/components/ui/icon'
import { formatDuration } from '@/lib/format'

import type { Step } from './types'

const KIND_LABEL: Record<string, string> = {
  plan: 'Plan',
  approval: 'Waiting for you',
  execute: 'Ran the query',
  reflect: 'Checked the result',
  final: 'Finished',
}

function label(step: Step): string {
  if (step.kind === 'approval' && step.actor === 'user') return 'You approved'
  if (step.kind === 'tool') return step.tool_name ? `Tool: ${step.tool_name}` : 'Tool call'
  return KIND_LABEL[step.kind] ?? step.kind
}

/** What the agent did, step by step. Shows exactly what the API gives; output is plain text. */
export function RunTimeline({ steps }: { steps: Step[] }) {
  if (steps.length === 0) return null
  return (
    <ol aria-label="What the agent did" className="flex flex-col gap-2">
      {steps.map((step) => {
        const failed = step.status !== 'ok' && step.status !== ''
        return (
          <li key={step.index} className="rounded-md border bg-surface p-3">
            <details>
              <summary className="flex cursor-pointer list-none items-center gap-2 text-body outline-none focus-visible:ring-2 focus-visible:ring-ring">
                <Icon
                  icon={failed ? AlertCircleIcon : CheckmarkCircle02Icon}
                  size="sm"
                  className={failed ? 'text-danger' : 'text-success'}
                />
                <span className="font-medium">{label(step)}</span>
                {failed && <Badge variant="danger">{step.error_code || step.status}</Badge>}
                <span className="ml-auto text-small text-muted-foreground">
                  {formatDuration(step.latency_ms / 1000)}
                </span>
              </summary>
              {step.output && (
                <pre className="mt-2 max-h-60 overflow-auto rounded-sm bg-surface-muted p-2 font-mono text-code whitespace-pre-wrap">
                  {step.output}
                </pre>
              )}
            </details>
          </li>
        )
      })}
    </ol>
  )
}
