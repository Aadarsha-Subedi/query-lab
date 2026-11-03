import type { ComponentProps, ReactNode } from 'react'

import {
  CodeBlock as UiCodeBlock,
  CodeBlockActions,
  CodeBlockContent,
  CodeBlockCopyButton,
  CodeBlockLine,
} from '@/components/ui/code-block'
import { cn } from '@/lib/utils'

/** Inline code: column names, IDs, values. */
export function Code({ className, ...props }: ComponentProps<'code'>) {
  return (
    <code
      className={cn('rounded-sm bg-surface-muted px-1 py-0.5 font-mono text-code text-foreground', className)}
      {...props}
    />
  )
}

const SQL_KEYWORDS = new Set(
  (
    'select from where join left right inner outer full on group by order having limit offset as and or not in ' +
    'is null case when then else end with distinct count sum avg min max union all desc asc between like ' +
    'interval date_trunc coalesce extract over partition'
  ).split(' '),
)

/** Minimal SQL highlighting: keywords, strings, numbers. No parser, no dependency. */
function highlightSql(sql: string): ReactNode[] {
  return sql.split(/('(?:[^']|'')*'|\b\d+(?:\.\d+)?\b|\b[a-z_]+\b)/gi).map((part, index) => {
    if (part.startsWith("'")) {
      return (
        <span key={index} className="text-success-foreground">
          {part}
        </span>
      )
    }
    if (/^\d/.test(part)) {
      return (
        <span key={index} className="text-warning-foreground">
          {part}
        </span>
      )
    }
    if (SQL_KEYWORDS.has(part.toLowerCase())) {
      return (
        <span key={index} className="font-medium text-primary">
          {part}
        </span>
      )
    }
    return part
  })
}

type CodeBlockProps = { code: string; language?: 'sql' | 'text'; wrap?: boolean; className?: string }

/** A block of SQL (or text): the shadcn Code Block, with a copy button and our small SQL colouring. */
export function CodeBlock({ code, language = 'sql', wrap = true, className }: CodeBlockProps) {
  return (
    <UiCodeBlock className={className}>
      <CodeBlockActions>
        <CodeBlockCopyButton value={code} />
      </CodeBlockActions>
      <CodeBlockContent wrap={wrap}>
        {code.split('\n').map((line, index) => (
          <CodeBlockLine key={index}>{language === 'sql' ? highlightSql(line) : line}</CodeBlockLine>
        ))}
      </CodeBlockContent>
    </UiCodeBlock>
  )
}
