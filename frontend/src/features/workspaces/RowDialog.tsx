import { FloppyDiskIcon } from '@hugeicons/core-free-icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ApiError } from '@/lib/api'
import { errorText } from '@/lib/api/error-text'

import { insertRows, invalidateWorkspace, patchRow, type TableSpec } from './api'
import { cellText } from '@/lib/cell'

const NULL = '__null__'

type Props = {
  workspaceId: number
  table: TableSpec
  /** Present when editing: the current values by column and the hidden row id. */
  row?: Record<string, unknown>
  rowId?: number
  trigger: ReactNode
}

/** Turns what the user typed into what to send. Empty means "not given" on insert and NULL on edit; text keeps ''. */
function toValue(type: string, raw: string, editing: boolean): unknown {
  if (type === 'boolean') {
    if (raw === NULL) return editing ? null : undefined
    return raw === 'true'
  }
  if (raw === '') return type === 'text' ? '' : editing ? null : undefined
  return raw
}

export function RowDialog({ workspaceId, table, row, rowId, trigger }: Props) {
  const queryClient = useQueryClient()
  const editing = rowId !== undefined
  const columns = table.columns.filter((column) => !column.hidden)
  const initial = () =>
    Object.fromEntries(
      columns.map((column) => {
        const current = row?.[column.name]
        if (column.type === 'boolean')
          return [column.name, current === true ? 'true' : current === false ? 'false' : NULL]
        return [column.name, cellText(current)]
      }),
    )
  const [open, setOpen] = useState(false)
  const [values, setValues] = useState<Record<string, string>>(initial)
  const mutation = useMutation({
    mutationFn: (): Promise<unknown> => {
      const payload: Record<string, unknown> = {}
      for (const column of columns) {
        const value = toValue(column.type, values[column.name] ?? '', editing)
        if (value !== undefined) payload[column.name] = value
      }
      return editing
        ? patchRow(workspaceId, table.name, rowId, payload)
        : insertRows(workspaceId, table.name, [payload])
    },
    onSuccess: async () => {
      await invalidateWorkspace(queryClient, workspaceId)
      setOpen(false)
    },
  })
  const failure = mutation.isError ? errorText(mutation.error) : null
  const fieldErrors = new Map<string, string>()
  if (mutation.error instanceof ApiError) {
    for (const item of mutation.error.errors) {
      const column = /^rows\[\d+\]\.(.+)$/.exec(item.field ?? '')?.[1] ?? item.field
      if (column) fieldErrors.set(column, item.message)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (next) setValues(initial())
        mutation.reset()
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{editing ? `Edit row ${rowId}` : `Add a row to ${table.name}`}</DialogTitle>
          <DialogDescription>
            {editing
              ? 'Empty clears a value (NULL), except text.'
              : 'Leave a column empty to use its default.'}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          {columns.map((column) => {
            const id = `cell-${column.name}`
            const error = fieldErrors.get(column.name)
            return (
              <div key={column.name} className="grid gap-1.5">
                <Label htmlFor={id}>
                  <span className="font-mono">{column.name}</span>
                  <span className="ml-2 text-small text-muted-foreground">{column.type}</span>
                </Label>
                {column.type === 'boolean' ? (
                  <Select
                    value={values[column.name] ?? NULL}
                    onValueChange={(next) => {
                      setValues((previous) => ({ ...previous, [column.name]: next }))
                    }}
                  >
                    <SelectTrigger id={id}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={NULL}>{editing ? 'NULL' : 'Default'}</SelectItem>
                      <SelectItem value="true">true</SelectItem>
                      <SelectItem value="false">false</SelectItem>
                    </SelectContent>
                  </Select>
                ) : (
                  <Input
                    id={id}
                    autoComplete="off"
                    value={values[column.name] ?? ''}
                    aria-invalid={error ? true : undefined}
                    aria-describedby={error ? `${id}-error` : undefined}
                    onChange={(event) => {
                      setValues((previous) => ({ ...previous, [column.name]: event.target.value }))
                    }}
                  />
                )}
                {error && (
                  <p id={`${id}-error`} role="alert" className="text-small text-danger-foreground">
                    {error}
                  </p>
                )}
              </div>
            )
          })}
          {failure && fieldErrors.size === 0 && (
            <p role="alert" className="text-small text-danger-foreground">
              {failure.message} {failure.hint}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button
            icon={FloppyDiskIcon}
            loading={mutation.isPending}
            onClick={() => {
              mutation.mutate()
            }}
          >
            {editing ? 'Save row' : 'Add row'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
