import { Delete02Icon, FloppyDiskIcon } from '@hugeicons/core-free-icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Heading } from '@/components/typography/Heading'
import { Button } from '@/components/ui/button'
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { errorText } from '@/lib/api/error-text'

import { dropTable, invalidateWorkspace, patchTable, tablesQuery, type TableSpec } from './api'
import { ColumnsPanel } from './ColumnsPanel'
import { RowsGrid } from './RowsGrid'

type Props = {
  workspaceId: number
  name: string
  onGone: () => void
  onRenamed: (name: string) => void
}

function Header({ workspaceId, table, onGone, onRenamed }: Omit<Props, 'name'> & { table: TableSpec }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState(table.name)
  const [description, setDescription] = useState(table.description)
  const save = useMutation({
    mutationFn: () => patchTable(workspaceId, table.name, { name, description }),
    onSuccess: async (updated) => {
      await invalidateWorkspace(queryClient, workspaceId)
      if (updated.name !== table.name) onRenamed(updated.name)
    },
  })
  const drop = useMutation({
    mutationFn: () => dropTable(workspaceId, table.name),
    onSuccess: async () => {
      await invalidateWorkspace(queryClient, workspaceId)
      onGone()
    },
  })
  const failure = save.isError ? save.error : drop.isError ? drop.error : null
  const dirty = name !== table.name || description !== table.description

  return (
    <div className="flex flex-col gap-3">
      <Heading level={3}>{table.name}</Heading>
      <div className="grid gap-2 sm:grid-cols-2">
        <Input
          aria-label="Table name"
          value={name}
          onChange={(event) => {
            setName(event.target.value)
          }}
        />
        <Input
          aria-label="Table description"
          placeholder="Description"
          value={description}
          onChange={(event) => {
            setDescription(event.target.value)
          }}
        />
      </div>
      {failure && (
        <p role="alert" className="text-small text-danger-foreground">
          {errorText(failure).message} {errorText(failure).hint}
        </p>
      )}
      <div className="flex gap-2">
        <Button
          size="sm"
          icon={FloppyDiskIcon}
          loading={save.isPending}
          disabled={!dirty || !name.trim()}
          onClick={() => {
            save.mutate()
          }}
        >
          Save changes
        </Button>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button size="sm" variant="ghost" icon={Delete02Icon}>
              Drop table
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Drop {table.name}?</AlertDialogTitle>
              <AlertDialogDescription>
                The table and all its rows are removed for good. Relations that use it are removed too.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel />
              <Button
                variant="destructive"
                icon={Delete02Icon}
                loading={drop.isPending}
                onClick={() => {
                  drop.mutate()
                }}
              >
                Drop table
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  )
}

/** One table: its name and description, columns and primary key, and its rows. */
export function TableEditor({ workspaceId, name, onGone, onRenamed }: Props) {
  const query = useQuery(tablesQuery(workspaceId))
  return (
    <QueryBoundary
      query={query}
      errorTitle="Couldn't load this table."
      loading={<Skeleton className="h-48 w-full" />}
    >
      {(tables) => {
        const table = tables.find((item) => item.name === name)
        if (!table) return <p className="text-body text-muted-foreground">That table no longer exists.</p>
        return (
          <div className="flex flex-col gap-4">
            <Header
              key={`${table.name}:${table.description}`}
              workspaceId={workspaceId}
              table={table}
              onGone={onGone}
              onRenamed={onRenamed}
            />
            <Tabs defaultValue="columns">
              <TabsList>
                <TabsTrigger value="columns">Columns</TabsTrigger>
                <TabsTrigger value="rows">Rows</TabsTrigger>
              </TabsList>
              <TabsContent value="columns">
                <ColumnsPanel workspaceId={workspaceId} table={table} />
              </TabsContent>
              <TabsContent value="rows">
                <RowsGrid workspaceId={workspaceId} table={table} />
              </TabsContent>
            </Tabs>
          </div>
        )
      }}
    </QueryBoundary>
  )
}
