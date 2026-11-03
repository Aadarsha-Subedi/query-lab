import { DatabaseIcon } from '@hugeicons/core-free-icons'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Heading } from '@/components/typography/Heading'
import { EmptyState } from '@/components/ui/data-state'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { WorkspaceMenu } from '@/features/workspaces/WorkspaceMenu'
import { formatNumber } from '@/lib/format'
import { cn } from '@/lib/utils'

import { schemaQuery, type DatabaseSchema, type TableInfo } from './api'
import { TableData } from './TableData'

/** What the table is. The columns, keys and sizes are in the table below. */
function TableMeta({ table }: { table: TableInfo }) {
  return (
    <div className="flex flex-col gap-2">
      <Heading level={2} className="font-mono">
        {table.name}
      </Heading>
      {table.comment && (
        <p className="max-w-[var(--reading-max)] text-body text-muted-foreground">{table.comment}</p>
      )}
    </div>
  )
}

function Tables({
  schema,
  workspace,
  table,
  onSelect,
}: {
  schema: DatabaseSchema
  workspace?: number
  table?: string
  onSelect: (name: string) => void
}) {
  const [filter, setFilter] = useState('')
  const needle = filter.trim().toLowerCase()
  const shown = schema.tables.filter(
    (candidate) =>
      !needle ||
      candidate.name.toLowerCase().includes(needle) ||
      candidate.columns.some((c) => c.name.toLowerCase().includes(needle)),
  )
  const selected = schema.tables.find((candidate) => candidate.name === table) ?? schema.tables[0]

  return (
    <div className="grid min-w-0 gap-6 lg:grid-cols-[16rem_minmax(0,1fr)]">
      <div className="flex flex-col gap-3">
        <Input
          type="search"
          aria-label="Filter tables and columns"
          placeholder="Filter tables and columns"
          value={filter}
          onChange={(event) => {
            setFilter(event.target.value)
          }}
        />
        {shown.length === 0 ? (
          <EmptyState icon={DatabaseIcon} title="No match" description="No table or column has that name." />
        ) : (
          <>
            {/* On a phone a list this long would push the data away: a dropdown instead. */}
            <div className="lg:hidden">
              <Select value={selected?.name} onValueChange={onSelect}>
                <SelectTrigger aria-label="Table" className="w-full font-mono">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {shown.map((candidate) => (
                    <SelectItem key={candidate.name} value={candidate.name} className="font-mono">
                      {candidate.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <ul aria-label="Tables" className="hidden flex-col gap-0.5 lg:flex">
              {shown.map((candidate) => {
                const active = candidate.name === selected?.name
                return (
                  <li key={candidate.name}>
                    <button
                      type="button"
                      aria-current={active ? 'true' : undefined}
                      onClick={() => {
                        onSelect(candidate.name)
                      }}
                      className={cn(
                        'flex h-9 w-full min-w-0 items-center gap-2 rounded-md px-2 text-left text-body outline-none hover:bg-surface-muted focus-visible:ring-2 focus-visible:ring-ring',
                        active && 'bg-surface-muted font-medium',
                      )}
                    >
                      <span className="truncate font-mono">{candidate.name}</span>
                      {candidate.row_estimate !== null && (
                        <span className="ml-auto shrink-0 text-small text-muted-foreground">
                          {formatNumber(candidate.row_estimate)}
                        </span>
                      )}
                    </button>
                  </li>
                )
              })}
            </ul>
          </>
        )}
      </div>
      {selected && (
        <section aria-label={`Table ${selected.name}`} className="flex min-w-0 flex-col gap-4">
          <TableMeta table={selected} />
          {/* Remounted per table so paging starts at the first rows. */}
          <TableData key={`${workspace ?? 'demo'}-${selected.name}`} table={selected} workspace={workspace} />
        </section>
      )}
    </div>
  )
}

/** The schema browser: pick a table, see its metadata, its columns and its rows. */
export function SchemaPanel({
  workspace,
  table,
  onSelect,
}: {
  workspace?: number
  table?: string
  onSelect: (name: string) => void
}) {
  const query = useQuery(schemaQuery(workspace))
  return (
    <section aria-label="Schema" className="flex flex-col gap-6">
      {/* A private workspace: storage, import a dump, run a query. The demo is fixed. */}
      {workspace !== undefined && (
        <div className="flex justify-end">
          <WorkspaceMenu workspaceId={workspace} />
        </div>
      )}
      <QueryBoundary
        query={query}
        errorTitle="Couldn't load the schema."
        isEmpty={(schema) => schema.tables.length === 0}
        empty={
          <EmptyState
            icon={DatabaseIcon}
            title="No tables yet"
            description="This workspace has no tables yet. Open the menu at the top right and choose Import dump."
          />
        }
        loading={
          <div className="grid gap-6 lg:grid-cols-[16rem_minmax(0,1fr)]">
            <div className="flex flex-col gap-2">
              {Array.from({ length: 8 }, (_, index) => (
                <Skeleton key={index} className="h-9 w-full" />
              ))}
            </div>
            <Skeleton className="h-96 w-full" />
          </div>
        }
      >
        {(schema) => <Tables schema={schema} workspace={workspace} table={table} onSelect={onSelect} />}
      </QueryBoundary>
    </section>
  )
}
