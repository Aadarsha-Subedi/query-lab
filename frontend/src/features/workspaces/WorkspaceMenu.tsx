import { DatabaseIcon, MoreVerticalIcon, PlayIcon, Upload04Icon } from '@hugeicons/core-free-icons'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Icon } from '@/components/ui/icon'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { formatBytes, formatNumber } from '@/lib/format'

import { workspaceLimitsQuery } from './api'
import { ImportDialog } from './ImportPanel'
import { SqlConsole } from './SqlConsole'
import { WorkspaceStorage } from './WorkspaceStorage'

type Overlay = 'storage' | 'import' | 'query' | null

/** What the workspace has used and may use: this workspace, then all of the user's workspaces together. */
function StorageDialog({
  workspaceId,
  open,
  onOpenChange,
}: {
  workspaceId: number
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const limits = useQuery({ ...workspaceLimitsQuery, enabled: open })
  const data = limits.data
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Storage capacity</DialogTitle>
          <DialogDescription>
            How much of your space this workspace and your workspaces use.
          </DialogDescription>
        </DialogHeader>
        <WorkspaceStorage workspaceId={workspaceId} className="w-full" />
        {data && (
          <dl className="grid grid-cols-[1fr_auto] gap-x-6 gap-y-2 text-body">
            <dt className="text-muted-foreground">Per workspace</dt>
            <dd>{formatBytes(data.bytes.per_workspace)}</dd>
            <dt className="text-muted-foreground">All your workspaces</dt>
            <dd>
              {formatBytes(data.bytes.used)} of {formatBytes(data.bytes.allowed)}
            </dd>
            <dt className="text-muted-foreground">Workspaces</dt>
            <dd>
              {formatNumber(data.workspaces.used)} of {formatNumber(data.workspaces.allowed)}
            </dd>
            <dt className="text-muted-foreground">Largest dump</dt>
            <dd>{formatBytes(data.max_dump_bytes)}</dd>
          </dl>
        )}
      </DialogContent>
    </Dialog>
  )
}

/**
 * The three-dots menu of a private workspace on the Schema page: view storage, import a dump, run a
 * query. The query opens in a side sheet; what you typed is kept (see stores/query-draft.ts).
 */
export function WorkspaceMenu({ workspaceId }: { workspaceId: number }) {
  const [overlay, setOverlay] = useState<Overlay>(null)
  const close = (next: boolean) => {
    if (!next) setOverlay(null)
  }
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" icon={MoreVerticalIcon} aria-label="Workspace actions" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            onSelect={() => {
              setOverlay('storage')
            }}
          >
            <Icon icon={DatabaseIcon} size="sm" />
            View storage capacity
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => {
              setOverlay('import')
            }}
          >
            <Icon icon={Upload04Icon} size="sm" />
            Import dump
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => {
              setOverlay('query')
            }}
          >
            <Icon icon={PlayIcon} size="sm" />
            Run query
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <StorageDialog workspaceId={workspaceId} open={overlay === 'storage'} onOpenChange={close} />
      <ImportDialog workspaceId={workspaceId} open={overlay === 'import'} onOpenChange={close} />
      <Sheet open={overlay === 'query'} onOpenChange={close}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
          <SheetHeader>
            <SheetTitle>Run query</SheetTitle>
            <SheetDescription>Read-only SQL on this workspace. Your last query is kept.</SheetDescription>
          </SheetHeader>
          <div className="px-4 pb-4">
            <SqlConsole workspaceId={workspaceId} />
          </div>
        </SheetContent>
      </Sheet>
    </>
  )
}
