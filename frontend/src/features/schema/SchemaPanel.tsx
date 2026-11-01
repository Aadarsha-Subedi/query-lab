import {
  ArrowDown01Icon,
  ArrowRight01Icon,
  DatabaseIcon,
  InformationCircleIcon,
} from '@hugeicons/core-free-icons'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/data-state'
import { Icon } from '@/components/ui/icon'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { formatNumber } from '@/lib/format'

import { schemaQuery, type DatabaseSchema, type TableInfo } from './api'
import { useSchemaPanelStore } from './store'
import { TableDetail } from './TableDetail'

function SchemaTable({ table, onDetails }: { table: TableInfo; onDetails: (name: string) => void }) {
  const open = useSchemaPanelStore((state) => state.open[table.name] ?? false)
  const toggle = useSchemaPanelStore((state) => state.toggle)
  return (
    <li className="flex flex-col">
      <div className="flex items-center gap-1">
        <button
          type="button"
          aria-expanded={open}
          onClick={() => {
            toggle(table.name)
          }}
          className="flex h-8 min-w-0 flex-1 items-center gap-1.5 rounded-md px-1.5 text-left text-body font-medium outline-none hover:bg-surface-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Icon icon={open ? ArrowDown01Icon : ArrowRight01Icon} size="sm" />
          <span className="truncate font-mono">{table.name}</span>
          {table.row_estimate !== null && (
            <span className="ml-auto shrink-0 text-small text-muted-foreground">
              {formatNumber(table.row_estimate)}
            </span>
          )}
        </button>
        <Button
          variant="ghost"
          size="icon-sm"
          icon={InformationCircleIcon}
          aria-label={`Details of ${table.name}`}
          onClick={() => {
            onDetails(table.name)
          }}
        />
      </div>
      {open && (
        <ul className="ml-6 flex flex-col gap-0.5 border-l pl-2" aria-label={`${table.name} columns`}>
          {table.columns.map((column) => (
            <li
              key={column.name}
              className="flex items-center gap-2 text-small"
              title={column.comment || undefined}
            >
              <span className="truncate font-mono">{column.name}</span>
              <span className="truncate font-mono text-muted-foreground">{column.type}</span>
              {table.primary_key.includes(column.name) && <Badge variant="primary">PK</Badge>}
              {table.foreign_keys.some((fk) => fk.columns.includes(column.name)) && (
                <Badge variant="info">FK</Badge>
              )}
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}

function Tables({ schema, workspace }: { schema: DatabaseSchema; workspace?: number }) {
  const [filter, setFilter] = useState('')
  const [details, setDetails] = useState<string | null>(null)
  const needle = filter.trim().toLowerCase()
  const shown = schema.tables.filter(
    (table) =>
      !needle ||
      table.name.toLowerCase().includes(needle) ||
      table.columns.some((c) => c.name.toLowerCase().includes(needle)),
  )
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
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
        <ScrollArea className="min-h-0 flex-1">
          <ul className="flex flex-col gap-0.5 pr-3">
            {shown.map((table) => (
              <SchemaTable key={table.name} table={table} onDetails={setDetails} />
            ))}
          </ul>
        </ScrollArea>
      )}
      <Sheet
        open={details !== null}
        onOpenChange={(open) => {
          if (!open) setDetails(null)
        }}
      >
        <SheetContent className="overflow-y-auto sm:max-w-xl">
          <SheetHeader>
            <SheetTitle className="font-mono">{details}</SheetTitle>
            <SheetDescription>Columns, keys and comments.</SheetDescription>
          </SheetHeader>
          {details !== null && <TableDetail name={details} workspace={workspace} />}
        </SheetContent>
      </Sheet>
    </div>
  )
}

/** The schema browser: tables, columns, keys. Own loading, error and empty states. */
export function SchemaPanel({ workspace }: { workspace?: number }) {
  const query = useQuery(schemaQuery(workspace))
  return (
    <section aria-label="Schema" className="flex h-full min-h-0 flex-col gap-3">
      <QueryBoundary
        query={query}
        errorTitle="Couldn't load the schema."
        isEmpty={(schema) => schema.tables.length === 0}
        empty={
          <EmptyState
            icon={DatabaseIcon}
            title="No tables yet"
            description="This workspace has no tables. Create one in the workspace editor."
          />
        }
        loading={
          <div className="flex flex-col gap-2">
            {Array.from({ length: 8 }, (_, index) => (
              <Skeleton key={index} className="h-8 w-full" />
            ))}
          </div>
        }
      >
        {(schema) => <Tables schema={schema} workspace={workspace} />}
      </QueryBoundary>
    </section>
  )
}
