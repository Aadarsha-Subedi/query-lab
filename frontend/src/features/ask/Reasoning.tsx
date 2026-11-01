import { DatabaseIcon, Loading03Icon, SparklesIcon } from '@hugeicons/core-free-icons'

import { Icon } from '@/components/ui/icon'
import { cn } from '@/lib/utils'

type ReasoningProps = {
  /** What the agent has been doing, in order. The last one is what it is doing now. */
  stages: string[]
  /** Tables it looked at. */
  sources?: string[]
  /** Its notes so far, oldest first. The newest are shown; older ones fade. */
  reasoning?: string[]
  /** False once the run stopped: the stage stops shimmering and the spinner goes. */
  active?: boolean
  className?: string
}

/** How many notes stay on screen. */
const VISIBLE = 4

/**
 * The agent thinking out loud: the current stage shimmers, its notes appear under it and the
 * older ones fade away. Nothing here is paced by a timer; each real step the agent finishes
 * adds a stage and a note, so the pace is the agent's own.
 */
export function Reasoning({
  stages,
  sources = [],
  reasoning = [],
  active = true,
  className,
}: ReasoningProps) {
  const current = stages.at(-1)
  const notes = reasoning.slice(-VISIBLE)
  if (current === undefined) return null
  return (
    <div className={cn('flex flex-col gap-3', className)}>
      <p role="status" className="flex items-center gap-2 text-body font-medium">
        <Icon
          icon={active ? Loading03Icon : SparklesIcon}
          size="sm"
          className={cn('shrink-0 text-muted-foreground', active && 'animate-spin')}
        />
        <span className={active ? 'text-shimmer' : 'text-muted-foreground'}>{current}</span>
      </p>
      {notes.length > 0 && (
        <ul aria-label="The agent's notes" className="flex flex-col gap-2 pl-6">
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
        <ul aria-label="Tables it looked at" className="flex flex-wrap gap-2 pl-6">
          {sources.map((source) => (
            <li
              key={source}
              className="inline-flex items-center gap-1.5 rounded-md border bg-surface px-2 py-1 text-small"
            >
              <Icon icon={DatabaseIcon} size="sm" className="text-muted-foreground" />
              <span className="font-mono">{source}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
