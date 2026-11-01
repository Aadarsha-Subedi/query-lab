import { cn } from '@/lib/utils'

import { diffLines } from './diff'

/** The agent's proposed SQL against the SQL a person approved. Text only; colour plus a +/- marker. */
export function SqlDiff({ before, after }: { before: string; after: string }) {
  const lines = diffLines(before, after)
  return (
    <pre
      aria-label="SQL changes"
      className="overflow-auto rounded-md border bg-surface-muted p-3 font-mono text-code"
    >
      {lines.map((line, index) => (
        <div
          key={index}
          className={cn(
            'whitespace-pre-wrap',
            line.kind === 'removed' && 'bg-danger-subtle text-danger-foreground',
            line.kind === 'added' && 'bg-success-subtle text-success-foreground',
          )}
        >
          <span aria-hidden="true">
            {line.kind === 'removed' ? '- ' : line.kind === 'added' ? '+ ' : '  '}
          </span>
          <span className="sr-only">
            {line.kind === 'removed' ? 'Removed: ' : line.kind === 'added' ? 'Added: ' : ''}
          </span>
          {line.text}
        </div>
      ))}
    </pre>
  )
}
