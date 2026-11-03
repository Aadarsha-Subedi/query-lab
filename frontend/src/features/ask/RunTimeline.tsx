import { AlertCircleIcon, CheckmarkCircle02Icon } from '@hugeicons/core-free-icons'

import { Icon } from '@/components/ui/icon'
import {
  Trace,
  TraceCollapsible,
  TraceCollapsibleContent,
  TraceCollapsibleTrigger,
  TraceDescription,
  TraceIcon,
  TraceLine,
  TraceTitle,
} from '@/components/ui/trace'
import { describeError } from '@/lib/api/errors'
import { formatDuration } from '@/lib/format'

import { describeStep } from './step-text'
import type { Step } from './types'

function StepLine({ step }: { step: Step }) {
  const failed = step.status !== 'ok' && step.status !== ''
  const { stage, note } = describeStep(step)
  const problem = failed && step.error_code ? describeError(step.error_code, '').message : null
  const detail = problem ?? note
  const line = (
    <TraceLine status={failed ? 'error' : undefined}>
      <TraceIcon>
        <Icon icon={failed ? AlertCircleIcon : CheckmarkCircle02Icon} size="sm" />
      </TraceIcon>
      <TraceTitle>{failed ? `${stage} failed` : stage}</TraceTitle>
      <TraceDescription>{formatDuration(step.latency_ms / 1000)}</TraceDescription>
    </TraceLine>
  )
  if (!detail) return <div role="listitem">{line}</div>
  // Like shadcn Tool: a plain line while there is nothing to show, a collapsible once there is.
  return (
    <div role="listitem">
      <TraceCollapsible>
        <TraceCollapsibleTrigger>{line}</TraceCollapsibleTrigger>
        <TraceCollapsibleContent className="whitespace-pre-line">{detail}</TraceCollapsibleContent>
      </TraceCollapsible>
    </div>
  )
}

/**
 * What the agent did, in plain words (never the raw tool output): shadcn Chain of Thought, a summary
 * line that opens into one line per step, each opening into what it found.
 */
export function RunTimeline({ steps }: { steps: Step[] }) {
  if (steps.length === 0) return null
  const failed = steps.filter((step) => step.status !== 'ok' && step.status !== '').length
  return (
    <TraceCollapsible defaultOpen>
      <TraceCollapsibleTrigger>
        <TraceLine status={failed > 0 ? 'error' : undefined}>
          <TraceIcon>
            <Icon icon={failed > 0 ? AlertCircleIcon : CheckmarkCircle02Icon} size="sm" />
          </TraceIcon>
          <TraceTitle>
            {steps.length === 1 ? 'Worked through 1 step' : `Worked through ${steps.length} steps`}
          </TraceTitle>
        </TraceLine>
      </TraceCollapsibleTrigger>
      <TraceCollapsibleContent keepMounted>
        <Trace role="list" aria-label="What the agent did">
          {steps.map((step) => (
            <StepLine key={step.index} step={step} />
          ))}
        </Trace>
      </TraceCollapsibleContent>
    </TraceCollapsible>
  )
}
