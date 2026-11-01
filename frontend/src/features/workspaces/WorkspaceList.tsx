import {
  Delete02Icon,
  MessageQuestionIcon,
  MoreVerticalIcon,
  Settings02Icon,
} from '@hugeicons/core-free-icons'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from '@tanstack/react-router'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Icon } from '@/components/ui/icon'
import { Meter } from '@/components/ui/meter'
import { Skeleton } from '@/components/ui/skeleton'
import { formatBytes, formatNumber } from '@/lib/format'

import { workspaceLimitsQuery, workspacesQuery, type WorkspaceInfo } from './api'
import { CreateWorkspaceDialog } from './CreateWorkspaceDialog'
import { DeleteWorkspaceDialog } from './DeleteWorkspaceDialog'

/** Ask, edit tables and delete, in one menu. The demo can only be asked. */
function WorkspaceActions({ workspace, onDelete }: { workspace: WorkspaceInfo; onDelete: () => void }) {
  const demo = workspace.kind === 'demo'
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          icon={MoreVerticalIcon}
          aria-label={`Actions for ${workspace.name}`}
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem asChild>
          <Link to="/ask" search={demo ? {} : { workspace: workspace.id ?? undefined }}>
            <Icon icon={MessageQuestionIcon} size="sm" />
            Ask
          </Link>
        </DropdownMenuItem>
        {!demo && workspace.id !== null && (
          <>
            <DropdownMenuItem asChild>
              <Link to="/workspaces/$id" params={{ id: String(workspace.id) }}>
                <Icon icon={Settings02Icon} size="sm" />
                Edit tables
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onSelect={onDelete}>
              <Icon icon={Delete02Icon} size="sm" />
              Delete workspace
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function WorkspaceCard({ workspace }: { workspace: WorkspaceInfo }) {
  const demo = workspace.kind === 'demo'
  const [deleting, setDeleting] = useState(false)
  return (
    <Card className="relative transition-colors duration-fast hover:bg-surface-muted">
      <CardHeader className="grid-cols-[1fr_auto]">
        <CardTitle className="flex flex-wrap items-center gap-2">
          {/* The whole card is the link (the stretched ::after), and opens the workspace's schema. */}
          <Link
            to="/ask"
            search={{ tab: 'schema', ...(demo ? {} : { workspace: workspace.id ?? undefined }) }}
            className="rounded-sm outline-none after:absolute after:inset-0 after:rounded-lg focus-visible:after:ring-2 focus-visible:after:ring-ring"
          >
            {workspace.name}
          </Link>
          {demo && <Badge variant="info">Shared · read only</Badge>}
          {workspace.status !== 'ready' && <Badge variant="warning">{workspace.status}</Badge>}
        </CardTitle>
        <div className="relative z-10 col-start-2 row-span-2 row-start-1 -mt-1 -mr-2">
          <WorkspaceActions
            workspace={workspace}
            onDelete={() => {
              setDeleting(true)
            }}
          />
        </div>
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
      {!demo && workspace.id !== null && (
        <DeleteWorkspaceDialog workspace={workspace} open={deleting} onOpenChange={setDeleting} />
      )}
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
