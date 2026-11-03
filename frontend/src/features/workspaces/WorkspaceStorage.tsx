import { useQuery } from '@tanstack/react-query'

import { Progress, ProgressLabel, ProgressValue } from '@/components/ui/progress'
import { formatBytes } from '@/lib/format'
import { cn } from '@/lib/utils'

import { workspaceQuery } from './api'

/** How full a private workspace is, as a shadcn Progress. Shows nothing while loading or if it fails (it is a hint, not a gate). */
export function WorkspaceStorage({ workspaceId, className }: { workspaceId: number; className?: string }) {
  const query = useQuery(workspaceQuery(workspaceId))
  const workspace = query.data
  if (!workspace || workspace.bytes_allowed === null) return null
  const allowed = workspace.bytes_allowed
  return (
    <Progress
      value={workspace.bytes_used}
      max={allowed}
      className={cn(
        'w-48 gap-1.5',
        workspace.bytes_used / allowed >= 0.9 && '[&_[data-slot=progress-indicator]]:bg-danger',
        className,
      )}
    >
      <ProgressLabel className="text-small text-muted-foreground">Storage</ProgressLabel>
      <ProgressValue className="text-small">
        {() => `${formatBytes(workspace.bytes_used)} of ${formatBytes(allowed)}`}
      </ProgressValue>
    </Progress>
  )
}
