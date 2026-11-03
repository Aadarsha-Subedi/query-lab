import { CheckmarkCircle02Icon, DatabaseIcon, Loading03Icon } from '@hugeicons/core-free-icons'
import { useState } from 'react'

import { Icon } from '@/components/ui/icon'
import {
  TraceCollapsible,
  TraceCollapsibleContent,
  TraceCollapsibleTrigger,
  TraceDescription,
  TraceIcon,
  TraceLine,
  TraceTitle,
} from '@/components/ui/trace'
import { cn } from '@/lib/utils'

type ReasoningProps = {
  /** What the agent has been doing, in order. The last one is what it is doing now. */
  stages: string[]
  /** Tables it looked at. */
  sources?: string[]
  /** Its notes so far, oldest first. The newest are shown; older ones fade. */
  reasoning?: string[]
  /** False once the run stopped: the line reads "Thought" and stops shimmering. */
  active?: boolean
  className?: string
}

/** How many notes stay on screen. */
const VISIBLE = 4

/**
 * shadcn Reasoning, on Trace: a line that shimmers with the current stage while the agent works and
 * reads "Thought" when it is done. It opens while the agent works and closes after, unless the person
 * opened or closed it. Nothing here is paced by a timer; each real step the agent finishes adds a stage
 * and a note.
 */
export function Reasoning({
  stages,
  sources = [],
  reasoning = [],
  active = true,
  className,
}: ReasoningProps) {
  const [open, setOpen] = useState<boolean>()
  const current = stages.at(-1)
  const notes = reasoning.slice(-VISIBLE)
  if (current === undefined) return null
  const line = (
    <TraceLine status={active ? 'running' : undefined}>
      <TraceIcon>
        <Icon
          icon={active ? Loading03Icon : CheckmarkCircle02Icon}
          size="sm"
          className={active ? 'animate-spin' : ''}
        />
      </TraceIcon>
      <TraceTitle>{active ? current : 'Thought'}</TraceTitle>
      {!active && (
        <TraceDescription>{stages.length === 1 ? '1 step' : `${stages.length} steps`}</TraceDescription>
      )}
    </TraceLine>
  )
  return (
    <div className={className}>
      <div role="status">
        {notes.length === 0 && sources.length === 0 ? (
          line
        ) : (
          <TraceCollapsible open={open ?? active} onOpenChange={setOpen}>
            <TraceCollapsibleTrigger>{line}</TraceCollapsibleTrigger>
            <TraceCollapsibleContent className="flex flex-col gap-3">
              {notes.length > 0 && (
                <ul aria-label="The agent's notes" className="flex flex-col gap-2">
                  {notes.map((note, index) => {
                    // The newest note is the clearest; each older one is a step fainter.
                    const age = notes.length - 1 - index
                    return (
                      <li
                        key={`${reasoning.length - notes.length + index}`}
                        className={cn(
                          'text-body whitespace-pre-line text-foreground',
                          age === 1 && 'opacity-70',
                          age === 2 && 'opacity-50',
                          age >= 3 && 'opacity-30',
                        )}
                      >
                        {note}
                      </li>
                    )
                  })}
                </ul>
              )}
              {sources.length > 0 && (
                <ul aria-label="Tables it looked at" className="flex flex-wrap gap-2">
                  {sources.map((source) => (
                    <li
                      key={source}
                      className="inline-flex items-center gap-1.5 rounded-md border bg-surface px-2 py-1 text-small text-foreground"
                    >
                      <Icon icon={DatabaseIcon} size="sm" className="text-muted-foreground" />
                      <span className="font-mono">{source}</span>
                    </li>
                  ))}
                </ul>
              )}
            </TraceCollapsibleContent>
          </TraceCollapsible>
        )}
      </div>
    </div>
  )
}
