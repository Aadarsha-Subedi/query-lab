import { MessageQuestionIcon, Settings02Icon } from '@hugeicons/core-free-icons'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Meter } from '@/components/ui/meter'
import { Skeleton } from '@/components/ui/skeleton'
import { formatBytes, formatNumber } from '@/lib/format'

import { workspaceLimitsQuery, workspacesQuery, type WorkspaceInfo } from './api'
import { CreateWorkspaceDialog } from './CreateWorkspaceDialog'
import { DeleteWorkspaceDialog } from './DeleteWorkspaceDialog'

function WorkspaceCard({ workspace }: { workspace: WorkspaceInfo }) {
  const demo = workspace.kind === 'demo'
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {workspace.name}
          {demo && <Badge variant="info">Shared · read only</Badge>}
          {workspace.status !== 'ready' && <Badge variant="warning">{workspace.status}</Badge>}
        </CardTitle>
        <CardDescription>
          {formatNumber(workspace.tables)} {workspace.tables === 1 ? 'table' : 'tables'}
          {workspace.bytes_allowed !== null && (
            <>
              {' · '}
              {formatBytes(workspace.bytes_used)} of {formatBytes(workspace.bytes_allowed)}
            </>
          )}
        </CardDescription>
      </CardHeader>
      {workspace.bytes_allowed !== null && (
        <CardContent>
          <Meter
            value={workspace.bytes_used}
            max={workspace.bytes_allowed}
            label={`Storage used in ${workspace.name}`}
          />
        </CardContent>
      )}
      <CardFooter className="flex flex-wrap gap-2">
        <Button asChild icon={MessageQuestionIcon} size="sm">
          <Link to="/ask" search={demo ? {} : { workspace: workspace.id ?? undefined }}>
            Ask
          </Link>
        </Button>
        {!demo && workspace.id !== null && (
          <>
            <Button asChild variant="secondary" icon={Settings02Icon} size="sm">
              <Link to="/workspaces/$id" params={{ id: String(workspace.id) }}>
                Edit tables
              </Link>
            </Button>
            <DeleteWorkspaceDialog workspace={workspace} />
          </>
        )}
      </CardFooter>
    </Card>
  )
}

/** The demo plus your own workspaces, with the cap and a create button. */
export function WorkspaceList() {
  const query = useQuery(workspacesQuery)
  const limits = useQuery(workspaceLimitsQuery)
  const atCap = limits.data ? limits.data.workspaces.used >= limits.data.workspaces.allowed : false

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-body text-muted-foreground">
          {limits.data
            ? `${formatNumber(limits.data.workspaces.used)} of ${formatNumber(limits.data.workspaces.allowed)} private workspaces used.`
            : 'Private workspaces are yours alone.'}
        </p>
        <CreateWorkspaceDialog disabled={atCap} />
      </div>
      <QueryBoundary
        query={query}
        errorTitle="Couldn't load your workspaces."
        isEmpty={(items) => items.length === 0}
        empty={<p className="text-body text-muted-foreground">No workspaces.</p>}
        loading={
          <div className="grid gap-4 md:grid-cols-2">
            {Array.from({ length: 2 }, (_, index) => (
              <Skeleton key={index} className="h-36 w-full" />
            ))}
          </div>
        }
      >
        {(items) => (
          <div className="grid gap-4 md:grid-cols-2">
            {items.map((workspace) => (
              <WorkspaceCard key={workspace.id ?? 'demo'} workspace={workspace} />
            ))}
          </div>
        )}
      </QueryBoundary>
      {atCap && (
        <p role="status" className="flex items-center gap-1.5 text-small text-muted-foreground">
          You are at the limit. Delete a workspace to create another.
        </p>
      )}
    </div>
  )
}
