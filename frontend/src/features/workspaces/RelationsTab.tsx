import { Add01Icon, ArrowRight01Icon, Delete02Icon, Link01Icon } from '@hugeicons/core-free-icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { EmptyState } from '@/components/ui/data-state'
import { Icon } from '@/components/ui/icon'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiError } from '@/lib/api'
import { errorText } from '@/lib/api/error-text'

import {
  addRelation,
  dropRelation,
  invalidateWorkspace,
  ON_DELETE,
  relationsQuery,
  tablesQuery,
  type TableSpec,
} from './api'

function ColumnPicker({
  legend,
  table,
  picked,
  onChange,
}: {
  legend: string
  table: TableSpec | undefined
  picked: string[]
  onChange: (next: string[]) => void
}) {
  const columns = (table?.columns ?? []).filter((column) => !column.hidden)
  return (
    <fieldset className="grid gap-1.5">
      <legend className="text-small font-medium">{legend}</legend>
      <div className="flex flex-wrap gap-3">
        {columns.map((column) => (
          <div key={column.name} className="flex items-center gap-2">
            <Checkbox
              id={`${legend}-${column.name}`}
              checked={picked.includes(column.name)}
              onCheckedChange={(checked) => {
                onChange(
                  checked === true ? [...picked, column.name] : picked.filter((name) => name !== column.name),
                )
              }}
            />
            <Label htmlFor={`${legend}-${column.name}`} className="font-mono">
              {column.name}
            </Label>
          </div>
        ))}
        {columns.length === 0 && (
          <span className="text-small text-muted-foreground">Pick a table first.</span>
        )}
      </div>
    </fieldset>
  )
}

function AddRelation({ workspaceId, tables }: { workspaceId: number; tables: TableSpec[] }) {
  const queryClient = useQueryClient()
  const [child, setChild] = useState('')
  const [parent, setParent] = useState('')
  const [childColumns, setChildColumns] = useState<string[]>([])
  const [parentColumns, setParentColumns] = useState<string[]>([])
  const [onDelete, setOnDelete] = useState<(typeof ON_DELETE)[number]>('NO ACTION')
  const mutation = useMutation({
    mutationFn: () =>
      addRelation(workspaceId, {
        child_table: child,
        child_columns: childColumns,
        parent_table: parent,
        parent_columns: parentColumns,
        on_delete: onDelete,
      }),
    onSuccess: async () => {
      await invalidateWorkspace(queryClient, workspaceId)
      setChildColumns([])
      setParentColumns([])
    },
  })
  const failure = mutation.isError ? errorText(mutation.error) : null
  const detail = mutation.error instanceof ApiError ? mutation.error.errors[0]?.message : undefined
  const ready = child && parent && childColumns.length > 0 && childColumns.length === parentColumns.length
  const tableNamed = (name: string) => tables.find((table) => table.name === name)

  return (
    <form
      aria-label="Add a relation"
      className="grid gap-4 rounded-md border p-4"
      onSubmit={(event) => {
        event.preventDefault()
        mutation.mutate()
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="grid gap-1.5">
          <Label htmlFor="rel-child">Child table (has the reference)</Label>
          <Select
            value={child}
            onValueChange={(next) => {
              setChild(next)
              setChildColumns([])
            }}
          >
            <SelectTrigger id="rel-child">
              <SelectValue placeholder="Pick a table" />
            </SelectTrigger>
            <SelectContent>
              {tables.map((table) => (
                <SelectItem key={table.name} value={table.name}>
                  {table.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="rel-parent">Parent table (is referenced)</Label>
          <Select
            value={parent}
            onValueChange={(next) => {
              setParent(next)
              setParentColumns([])
            }}
          >
            <SelectTrigger id="rel-parent">
              <SelectValue placeholder="Pick a table" />
            </SelectTrigger>
            <SelectContent>
              {tables.map((table) => (
                <SelectItem key={table.name} value={table.name}>
                  {table.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <ColumnPicker
          legend="Child columns"
          table={tableNamed(child)}
          picked={childColumns}
          onChange={setChildColumns}
        />
        <ColumnPicker
          legend="Parent columns"
          table={tableNamed(parent)}
          picked={parentColumns}
          onChange={setParentColumns}
        />
      </div>
      <div className="grid max-w-xs gap-1.5">
        <Label htmlFor="rel-delete">When a parent row is deleted</Label>
        <Select
          value={onDelete}
          onValueChange={(next) => {
            setOnDelete(next as (typeof ON_DELETE)[number])
          }}
        >
          <SelectTrigger id="rel-delete">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ON_DELETE.map((choice) => (
              <SelectItem key={choice} value={choice}>
                {choice === 'CASCADE' ? 'Delete the child rows too' : 'Refuse the delete'}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {failure && (
        <p role="alert" className="text-small text-danger-foreground">
          {detail ?? failure.message} {failure.hint}
        </p>
      )}
      <div>
        <Button type="submit" icon={Add01Icon} loading={mutation.isPending} disabled={!ready}>
          Add relation
        </Button>
      </div>
    </form>
  )
}

/** Foreign keys between tables. The parent columns must be a primary key or unique. */
export function RelationsTab({ workspaceId }: { workspaceId: number }) {
  const queryClient = useQueryClient()
  const relations = useQuery(relationsQuery(workspaceId))
  const tables = useQuery(tablesQuery(workspaceId))
  const drop = useMutation({
    mutationFn: (name: string) => dropRelation(workspaceId, name),
    onSuccess: () => invalidateWorkspace(queryClient, workspaceId),
  })
  return (
    <div className="flex flex-col gap-5 pt-4">
      <QueryBoundary
        query={relations}
        errorTitle="Couldn't load the relations."
        isEmpty={(items) => items.length === 0}
        empty={
          <EmptyState
            icon={Link01Icon}
            title="No relations"
            description="Relations tell the agent how tables join."
          />
        }
        loading={<Skeleton className="h-24 w-full" />}
      >
        {(items) => (
          <ul aria-label="Relations" className="flex flex-col gap-2">
            {items.map((relation) => (
              <li
                key={relation.name}
                className="flex flex-wrap items-center gap-2 rounded-md border bg-surface p-3"
              >
                <span className="font-mono">
                  {relation.child_table}({relation.child_columns.join(', ')})
                </span>
                <Icon icon={ArrowRight01Icon} size="sm" />
                <span className="font-mono">
                  {relation.parent_table}({relation.parent_columns.join(', ')})
                </span>
                <span className="text-small text-muted-foreground">
                  on delete {relation.on_delete.toLowerCase()}
                </span>
                <Button
                  className="ml-auto"
                  variant="ghost"
                  size="icon-sm"
                  icon={Delete02Icon}
                  aria-label={`Remove relation ${relation.name}`}
                  disabled={drop.isPending}
                  onClick={() => {
                    drop.mutate(relation.name)
                  }}
                />
              </li>
            ))}
          </ul>
        )}
      </QueryBoundary>
      {drop.isError && (
        <p role="alert" className="text-small text-danger-foreground">
          {errorText(drop.error).message} {errorText(drop.error).hint}
        </p>
      )}
      <QueryBoundary
        query={tables}
        errorTitle="Couldn't load the tables."
        loading={<Skeleton className="h-40 w-full" />}
      >
        {(items) => <AddRelation workspaceId={workspaceId} tables={items} />}
      </QueryBoundary>
    </div>
  )
}
