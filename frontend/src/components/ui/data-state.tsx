/*
 * Building blocks for a component's own data states (docs/design-system.md,
 * section 13). A component that fetches renders one of these inside its own
 * box; nothing here is page-level.
 */
import { AlertCircleIcon, RefreshIcon } from '@hugeicons/core-free-icons'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Icon, type IconSvgElement } from '@/components/ui/icon'
import { cn } from '@/lib/utils'

type ErrorStateProps = {
  /** What happened, in plain words: "Couldn't load run history." */
  title: string
  /** Why (if known) and what to do next. */
  description: string
  /** Manual retry for this component only. There are no automatic retries. */
  onRetry: () => void
  retrying?: boolean
  /** X-Request-ID of the failed call, shown for bug reports. */
  requestId?: string
  className?: string
}

export function ErrorState({
  title,
  description,
  onRetry,
  retrying = false,
  requestId,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn('flex flex-col items-start gap-3 rounded-md bg-danger-subtle p-4', className)}
    >
      <div className="flex gap-3">
        <Icon icon={AlertCircleIcon} size="md" className="text-danger-foreground" />
        <div className="flex flex-col gap-1">
          <p className="text-body font-medium text-danger-foreground">{title}</p>
          <p className="text-small text-foreground">{description}</p>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3 pl-8">
        <Button variant="secondary" size="sm" icon={RefreshIcon} loading={retrying} onClick={onRetry}>
          Try again
        </Button>
        {requestId && (
          <code className="font-mono text-caption text-muted-foreground select-all" title="Request id">
            Request {requestId}
          </code>
        )}
      </div>
    </div>
  )
}

type EmptyStateProps = {
  icon: IconSvgElement
  title: string
  description: string
  /** At most one next step. */
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center gap-2 px-4 py-8 text-center', className)}>
      <Icon icon={icon} size="lg" className="text-muted-foreground" />
      <p className="text-body font-medium text-foreground">{title}</p>
      <p className="max-w-sm text-small text-muted-foreground">{description}</p>
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
