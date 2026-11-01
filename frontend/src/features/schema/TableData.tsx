import {
  ArrowLeft01Icon,
  ArrowRight01Icon,
  InformationCircleIcon,
  Table02Icon,
} from '@hugeicons/core-free-icons'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/data-state'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatNumber } from '@/lib/format'

import { tableRowsQuery, type TableInfo } from './api'

function cell(value: unknown): string {
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

/** The info button of one column: its notes, whether it is a key, and what it points to. */
function ColumnInfo({ table, name }: { table: TableInfo; name: string }) {
  const column = table.columns.find((candidate) => candidate.name === name)
  const references = table.foreign_keys.filter((fk) => fk.columns.includes(name))
  const primary = table.primary_key.includes(name)
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          icon={InformationCircleIcon}
          aria-label={`About the ${name} column`}
          className="-my-1.5"
        />
      </PopoverTrigger>
      <PopoverContent
        align="start"
        collisionPadding={16}
        sticky="always"
        className="flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-3"
      >
        <div className="flex flex-col gap-0.5">
          <span className="font-mono text-body font-medium">{name}</span>
          <span className="font-mono text-small text-muted-foreground">
            {column?.type}
            {column && !column.nullable && ', required'}
          </span>
        </div>
        <p className="text-small text-muted-foreground">{column?.comment || 'No notes for this column.'}</p>
        {(primary || references.length > 0) && (
          <dl className="grid grid-cols-[auto_1fr] items-baseline gap-x-3 gap-y-1 text-small">
            {primary && (
              <>
                <dt className="text-muted-foreground">Primary key</dt>
                <dd>{table.primary_key.length > 1 ? `Part of (${table.primary_key.join(', ')})` : 'Yes'}</dd>
              </>
            )}
            {references.map((fk) => (
              <div key={fk.ref_table + fk.columns.join()} className="col-span-2 grid grid-cols-subgrid">
                <dt className="text-muted-foreground">Foreign key</dt>
                <dd className="font-mono">
                  {fk.ref_table}({fk.ref_columns.join(', ')})
                </dd>
              </div>
            ))}
          </dl>
        )}
      </PopoverContent>
    </Popover>
  )
}

/** The header of one column: its name, its type, PK/FK badges and the info button. */
function ColumnHead({ table, name }: { table: TableInfo; name: string }) {
  const column = table.columns.find((candidate) => candidate.name === name)
  const isForeign = table.foreign_keys.some((fk) => fk.columns.includes(name))
  return (
    <TableHead>
      <div className="flex items-start justify-between gap-2 py-1">
        <div className="flex flex-col gap-1">
          <span className="flex items-center gap-1.5 font-mono text-foreground">
            {name}
            {table.primary_key.includes(name) && <Badge variant="primary">PK</Badge>}
            {isForeign && <Badge variant="info">FK</Badge>}
          </span>
          <span className="font-mono text-caption font-normal text-muted-foreground">
            {column?.type ?? ''}
          </span>
        </div>
        <ColumnInfo table={table} name={name} />
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
