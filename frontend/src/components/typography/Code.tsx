import { Copy01Icon, Tick02Icon } from '@hugeicons/core-free-icons'
import { useState, type ComponentProps, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Icon } from '@/components/ui/icon'
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

type CodeBlockProps = { code: string; language?: 'sql' | 'text'; className?: string }

/** A block of SQL (or text) with a copy button. */
export function CodeBlock({ code, language = 'sql', className }: CodeBlockProps) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    void navigator.clipboard.writeText(code).then(() => {
      setCopied(true)
    })
  }
  return (
    <div className={cn('group relative rounded-lg border bg-surface-muted', className)}>
      <Button
        variant="ghost"
        size="icon-sm"
        className="absolute top-2 right-2"
        onClick={copy}
        aria-label={copied ? 'Copied' : 'Copy code'}
      >
        <Icon icon={copied ? Tick02Icon : Copy01Icon} size="sm" />
      </Button>
      <pre className="overflow-x-auto p-4 pr-12 font-mono text-code">
        <code>{language === 'sql' ? highlightSql(code) : code}</code>
      </pre>
    </div>
  )
}
