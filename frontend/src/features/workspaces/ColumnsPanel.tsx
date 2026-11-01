import { Add01Icon, Delete02Icon, Edit02Icon, FloppyDiskIcon, KeyIcon } from '@hugeicons/core-free-icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ApiError } from '@/lib/api'
import { errorText } from '@/lib/api/error-text'

import {
  addColumn,
  COLUMN_TYPES,
  dropColumn,
  invalidateWorkspace,
  patchColumn,
  setPrimaryKey,
  type ColumnSpec,
  type TableSpec,
} from './api'

type Props = { workspaceId: number; table: TableSpec }

/** Add or edit one column. A type change converts every row; if a value does not fit, nothing changes. */
function ColumnDialog({
  workspaceId,
  table,
  column,
  trigger,
}: Props & { column?: ColumnSpec; trigger: React.ReactNode }) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState(column?.name ?? '')
  const [type, setType] = useState(column?.type ?? 'text')
  const [description, setDescription] = useState(column?.description ?? '')
  const [required, setRequired] = useState(column ? !column.nullable : false)
  const mutation = useMutation({
    mutationFn: () =>
      column
        ? patchColumn(workspaceId, table.name, column.name, {
            name: name !== column.name ? name : undefined,
            type: type !== column.type ? type : undefined,
            description: description !== column.description ? description : undefined,
            nullable: required !== !column.nullable ? !required : undefined,
          })
        : addColumn(workspaceId, table.name, { name, type, description, nullable: !required }),
    onSuccess: async () => {
      await invalidateWorkspace(queryClient, workspaceId)
      setOpen(false)
    },
  })
  const failure = mutation.isError ? errorText(mutation.error) : null
  const detail = mutation.error instanceof ApiError ? mutation.error.errors[0]?.message : undefined

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        mutation.reset()
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{column ? `Edit ${column.name}` : `Add a column to ${table.name}`}</DialogTitle>
          <DialogDescription>
            {column
              ? 'Changing the type converts every row. If a value does not fit, nothing changes.'
              : 'New rows get NULL unless you say otherwise.'}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor="col-name">Column name</Label>
            <Input
              id="col-name"
              autoComplete="off"
              value={name}
              onChange={(event) => {
                setName(event.target.value)
              }}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="col-type">Type</Label>
            <Select value={type} onValueChange={setType}>
              <SelectTrigger id="col-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {COLUMN_TYPES.map((item) => (
                  <SelectItem key={item} value={item}>
                    {item}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="col-desc">Description</Label>
            <Input
              id="col-desc"
              autoComplete="off"
              value={description}
              onChange={(event) => {
                setDescription(event.target.value)
              }}
            />
          </div>
          <div className="flex items-center gap-2">
            <Checkbox
              id="col-required"
              checked={required}
              onCheckedChange={(checked) => {
                setRequired(checked === true)
              }}
            />
            <Label htmlFor="col-required">Required (cannot be empty)</Label>
          </div>
          {failure && (
            <p role="alert" className="text-small text-danger-foreground">
              {detail ?? failure.message} {failure.hint}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button
            icon={FloppyDiskIcon}
            loading={mutation.isPending}
            disabled={!name.trim()}
            onClick={() => {
              mutation.mutate()
            }}
          >
            {column ? 'Save column' : 'Add column'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function PrimaryKey({ workspaceId, table }: Props) {
  const queryClient = useQueryClient()
  const [picked, setPicked] = useState<string[]>(table.primary_key)
  const visible = table.columns.filter((column) => !column.hidden)
  const mutation = useMutation({
    mutationFn: () => setPrimaryKey(workspaceId, table.name, picked),
    onSuccess: () => invalidateWorkspace(queryClient, workspaceId),
  })
  const failure = mutation.isError ? errorText(mutation.error) : null
  const same =
    picked.length === table.primary_key.length && picked.every((name) => table.primary_key.includes(name))
  return (
    <fieldset className="grid gap-2">
      <legend className="text-body font-medium">Primary key</legend>
      <p className="text-small text-muted-foreground">
        Optional. Existing rows are checked first; if two rows share the key, nothing changes.
      </p>
      <div className="flex flex-wrap gap-4">
        {visible.map((column) => (
          <div key={column.name} className="flex items-center gap-2">
            <Checkbox
              id={`pk-${column.name}`}
              checked={picked.includes(column.name)}
              onCheckedChange={(checked) => {
                setPicked((previous) =>
                  checked === true
                    ? [...previous, column.name]
                    : previous.filter((name) => name !== column.name),
                )
              }}
            />
            <Label htmlFor={`pk-${column.name}`} className="font-mono">
              {column.name}
            </Label>
          </div>
        ))}
      </div>
      {failure && (
        <p role="alert" className="text-small text-danger-foreground">
          {failure.message} {failure.hint}
        </p>
      )}
      <div>
        <Button
          size="sm"
          variant="secondary"
          icon={KeyIcon}
          loading={mutation.isPending}
          disabled={same}
          onClick={() => {
            mutation.mutate()
          }}
        >
          Save primary key
        </Button>
      </div>
    </fieldset>
  )
}

export function ColumnsPanel({ workspaceId, table }: Props) {
  const queryClient = useQueryClient()
  const drop = useMutation({
    mutationFn: (column: string) => dropColumn(workspaceId, table.name, column),
    onSuccess: () => invalidateWorkspace(queryClient, workspaceId),
  })
  const visible = table.columns.filter((column) => !column.hidden)
  return (
    <div className="flex flex-col gap-5 pt-4">
      <Table>
        <caption className="sr-only">Columns of {table.name}</caption>
        <TableHeader>
          <TableRow>
            <TableHead>Column</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Notes</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {visible.map((column) => (
            <TableRow key={column.name}>
              <TableCell className="font-mono">{column.name}</TableCell>
              <TableCell className="font-mono text-muted-foreground">{column.type}</TableCell>
              <TableCell className="flex flex-wrap items-center gap-1">
                {table.primary_key.includes(column.name) && <Badge variant="primary">PK</Badge>}
                {!column.nullable && <Badge>required</Badge>}
                <span className="text-muted-foreground">{column.description}</span>
              </TableCell>
              <TableCell>
                <div className="flex gap-1">
                  <ColumnDialog
                    workspaceId={workspaceId}
                    table={table}
                    column={column}
                    trigger={
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        icon={Edit02Icon}
                        aria-label={`Edit ${column.name}`}
                      />
                    }
                  />
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    icon={Delete02Icon}
                    aria-label={`Drop ${column.name}`}
                    disabled={drop.isPending || visible.length === 1}
                    onClick={() => {
                      drop.mutate(column.name)
                    }}
                  />
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {drop.isError && (
        <p role="alert" className="text-small text-danger-foreground">
          {errorText(drop.error).message} {errorText(drop.error).hint}
        </p>
      )}
      <div>
        <ColumnDialog
          workspaceId={workspaceId}
          table={table}
          trigger={
            <Button size="sm" variant="secondary" icon={Add01Icon}>
              Add column
            </Button>
          }
        />
      </div>
      <PrimaryKey key={table.primary_key.join(',')} workspaceId={workspaceId} table={table} />
    </div>
  )
}
