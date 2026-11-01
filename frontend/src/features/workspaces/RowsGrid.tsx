import {
  Add01Icon,
  ArrowLeft01Icon,
  ArrowRight01Icon,
  Delete02Icon,
  Edit02Icon,
  Table02Icon,
} from '@hugeicons/core-free-icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/data-state'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { errorText } from '@/lib/api/error-text'
import { formatNumber } from '@/lib/format'

import {
  deleteRow,
  invalidateWorkspace,
  rowsQuery,
  workspaceLimitsQuery,
  type RowsPage,
  type TableSpec,
} from './api'
import { cellText } from '@/lib/cell'
import { RowDialog } from './RowDialog'

const ROW_ID = '_row_id'

function Page({
  workspaceId,
  table,
  page,
  offset,
  size,
  setOffset,
}: {
  workspaceId: number
  table: TableSpec
  page: RowsPage
  offset: number
  size: number
  setOffset: (offset: number) => void
}) {
  const queryClient = useQueryClient()
  const remove = useMutation({
    mutationFn: (rowId: number) => deleteRow(workspaceId, table.name, rowId),
    onSuccess: () => invalidateWorkspace(queryClient, workspaceId),
  })
  const idIndex = page.columns.findIndex((column) => column.name === ROW_ID)
  const shown = page.columns.filter((column) => column.name !== ROW_ID)

  return (
    <div className="flex flex-col gap-3">
      {page.rows.length === 0 ? (
        <EmptyState
          icon={Table02Icon}
          title="No rows"
          description="Add a row, or insert some with the SQL console."
        />
      ) : (
        <Table>
          <caption className="sr-only">Rows of {table.name}</caption>
          <TableHeader>
            <TableRow>
              {shown.map((column) => (
                <TableHead key={column.name}>{column.name}</TableHead>
              ))}
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {page.rows.map((row) => {
              const rowId = Number(row[idIndex])
              return (
                <TableRow key={rowId}>
                  {page.columns.map((column, position) =>
                    column.name === ROW_ID ? null : (
                      <TableCell key={column.name} className="font-mono">
                        {cellText(row[position])}
                      </TableCell>
                    ),
                  )}
                  <TableCell>
                    <div className="flex gap-1">
                      <RowDialog
                        workspaceId={workspaceId}
                        table={table}
                        row={Object.fromEntries(
                          page.columns.map((column, position) => [column.name, row[position]]),
                        )}
                        rowId={rowId}
                        trigger={
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            icon={Edit02Icon}
                            aria-label={`Edit row ${rowId}`}
                          />
                        }
                      />
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        icon={Delete02Icon}
                        aria-label={`Delete row ${rowId}`}
                        disabled={remove.isPending}
                        onClick={() => {
                          remove.mutate(rowId)
                        }}
                      />
                    </div>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      )}
      {remove.isError && (
        <p role="alert" className="text-small text-danger-foreground">
          {errorText(remove.error).message} {errorText(remove.error).hint}
        </p>
      )}
      <nav aria-label="Row pages" className="flex items-center justify-between gap-3">
        <span className="text-small text-muted-foreground">
          {page.total === 0
            ? '0 rows'
            : `${formatNumber(offset + 1)} to ${formatNumber(Math.min(offset + size, page.total))} of ${formatNumber(page.total)}`}
        </span>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            icon={ArrowLeft01Icon}
            disabled={offset === 0}
            onClick={() => {
              setOffset(Math.max(0, offset - size))
            }}
          >
            Previous
          </Button>
          <Button
            variant="secondary"
            size="sm"
            icon={ArrowRight01Icon}
            iconPosition="end"
            disabled={offset + size >= page.total}
            onClick={() => {
              setOffset(offset + size)
            }}
          >
            Next
          </Button>
        </div>
      </nav>
    </div>
  )
}

function Loaded({ workspaceId, table, size }: { workspaceId: number; table: TableSpec; size: number }) {
  const [offset, setOffset] = useState(0)
  const query = useQuery(rowsQuery(workspaceId, table.name, { limit: size, offset }))
  return (
    <div className="flex flex-col gap-3 pt-4">
      <div>
        <RowDialog
          workspaceId={workspaceId}
          table={table}
          trigger={
            <Button size="sm" icon={Add01Icon}>
              Add row
            </Button>
          }
        />
      </div>
      <QueryBoundary
        query={query}
        errorTitle="Couldn't load the rows."
        loading={
          <div className="flex flex-col gap-2">
            {Array.from({ length: 5 }, (_, index) => (
              <Skeleton key={index} className="h-9 w-full" />
            ))}
          </div>
        }
      >
        {(page) => (
          <Page
            workspaceId={workspaceId}
            table={table}
            page={page}
            offset={offset}
            size={size}
            setOffset={setOffset}
          />
        )}
      </QueryBoundary>
    </div>
  )
}

/** The rows of one table, paged. The page size is the server's per-edit cap, so the numbers come from the API. */
export function RowsGrid({ workspaceId, table }: { workspaceId: number; table: TableSpec }) {
  const limits = useQuery(workspaceLimitsQuery)
  return (
    <QueryBoundary
      query={limits}
      errorTitle="Couldn't load the limits."
      loading={<Skeleton className="mt-4 h-40 w-full" />}
    >
      {(data) => <Loaded workspaceId={workspaceId} table={table} size={data.max_rows_per_edit} />}
    </QueryBoundary>
  )
}
