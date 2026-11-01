import { ArrowLeft01Icon, ArrowRight01Icon, Table02Icon } from '@hugeicons/core-free-icons'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/data-state'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatNumber } from '@/lib/format'

import { tableRowsQuery, type TableInfo } from './api'

function cell(value: unknown): string {
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

/** The header of one column: its name, its type, and whether it is a key. */
function ColumnHead({ table, name }: { table: TableInfo; name: string }) {
  const column = table.columns.find((candidate) => candidate.name === name)
  const reference = table.foreign_keys.find((fk) => fk.columns.includes(name))
  return (
    <TableHead title={column?.comment || undefined}>
      <div className="flex flex-col gap-1 py-1">
        <span className="flex items-center gap-1.5 font-mono text-foreground">
          {name}
          {table.primary_key.includes(name) && <Badge variant="primary">PK</Badge>}
          {reference && <Badge variant="info">FK</Badge>}
        </span>
        <span className="font-mono text-caption font-normal text-muted-foreground">{column?.type ?? ''}</span>
      </div>
    </TableHead>
  )
}

/** A page of the table's rows, with its own loading / error / empty states and manual paging. */
export function TableData({ table, workspace }: { table: TableInfo; workspace?: number }) {
  const [offset, setOffset] = useState(0)
  const query = useQuery(tableRowsQuery(table.name, workspace, offset))
  return (
    <QueryBoundary
      query={query}
      errorTitle={`Couldn't load the rows of ${table.name}.`}
      isEmpty={(page) => page.rows.length === 0 && page.offset === 0}
      empty={<EmptyState icon={Table02Icon} title="No rows" description="This table has no rows yet." />}
      loading={
        <div className="flex flex-col gap-2">
          {Array.from({ length: 8 }, (_, index) => (
            <Skeleton key={index} className="h-9 w-full" />
          ))}
        </div>
      }
    >
      {(page) => (
        <div className="flex flex-col gap-3">
          <Table>
            <caption className="sr-only">
              Rows {formatNumber(page.offset + 1)} to {formatNumber(page.offset + page.rows.length)} of{' '}
              {table.name}
            </caption>
            <TableHeader>
              <TableRow>
                {page.columns.map((name) => (
                  <ColumnHead key={name} table={table} name={name} />
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {page.rows.map((row, index) => (
                <TableRow key={index}>
                  {row.map((value, position) => (
                    <TableCell
                      key={page.columns[position]}
                      className={
                        value === null
                          ? 'text-muted-foreground italic'
                          : 'max-w-72 truncate font-mono tabular-nums'
                      }
                      title={typeof value === 'string' && value.length > 30 ? value : undefined}
                    >
                      {value === null ? 'null' : cell(value)}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <nav aria-label="Rows pages" className="flex items-center justify-between gap-3">
            <span className="text-small text-muted-foreground">
              Rows {formatNumber(page.offset + 1)} to {formatNumber(page.offset + page.rows.length)}
              {page.row_estimate !== null && <> of about {formatNumber(page.row_estimate)}</>}
            </span>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                icon={ArrowLeft01Icon}
                disabled={page.offset === 0}
                onClick={() => {
                  setOffset(Math.max(0, page.offset - page.limit))
                }}
              >
                Previous
              </Button>
              <Button
                variant="secondary"
                size="sm"
                icon={ArrowRight01Icon}
                iconPosition="end"
                disabled={!page.has_more}
                onClick={() => {
                  setOffset(page.offset + page.limit)
                }}
              >
                Next
              </Button>
            </div>
          </nav>
        </div>
      )}
    </QueryBoundary>
  )
}
