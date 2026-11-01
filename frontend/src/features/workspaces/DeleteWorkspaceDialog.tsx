import { Delete02Icon } from '@hugeicons/core-free-icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { errorText } from '@/lib/api/error-text'

import { deleteWorkspace, type WorkspaceInfo } from './api'

/** Deleting drops every table and row in the workspace for good, so the name must be typed. */
export function DeleteWorkspaceDialog({
  workspace,
  open,
  onOpenChange,
  onDeleted,
}: {
  workspace: WorkspaceInfo
  /** Controlled by the actions menu that opens it. */
  open: boolean
  onOpenChange: (open: boolean) => void
  onDeleted?: () => void
}) {
  const setOpen = onOpenChange
  const [typed, setTyped] = useState('')
  const queryClient = useQueryClient()
  const id = workspace.id
  const mutation = useMutation({
    mutationFn: () => {
      if (id === null) throw new Error('The demo workspace cannot be deleted.')
      return deleteWorkspace(id)
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['workspaces'] })
      setOpen(false)
      onDeleted?.()
    },
  })
  const failure = mutation.isError ? errorText(mutation.error) : null

  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) {
          setTyped('')
          mutation.reset()
        }
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete {workspace.name}?</AlertDialogTitle>
          <AlertDialogDescription>
            Every table and row in it is removed for good. Past runs stay in your history, but their results
            can no longer be fetched. Type the workspace name to confirm.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <Input
          aria-label="Type the workspace name"
          autoComplete="off"
          value={typed}
          onChange={(event) => {
            setTyped(event.target.value)
          }}
        />
        {failure && (
          <p role="alert" className="text-small text-danger-foreground">
            {failure.message} {failure.hint}
          </p>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel />
          {/* Not AlertDialogAction: it would close the dialog before the server answers. */}
          <Button
            variant="destructive"
            icon={Delete02Icon}
            loading={mutation.isPending}
            disabled={typed !== workspace.name}
            onClick={() => {
              mutation.mutate()
            }}
          >
            Delete workspace
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
