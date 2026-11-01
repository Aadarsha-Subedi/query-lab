import { Table02Icon } from '@hugeicons/core-free-icons'
import { useQuery } from '@tanstack/react-query'

import { QueryBoundary } from '@/components/QueryBoundary'
import { EmptyState } from '@/components/ui/data-state'
import { Skeleton } from '@/components/ui/skeleton'
import { formatNumber } from '@/lib/format'
import { cn } from '@/lib/utils'

import { tablesQuery } from './api'
import { CreateTableDialog } from './CreateTableDialog'
import { TableEditor } from './TableEditor'

type Props = { workspaceId: number; selected?: string; onSelect: (name: string | undefined) => void }

export function TablesTab({ workspaceId, selected, onSelect }: Props) {
  const query = useQuery(tablesQuery(workspaceId))
  return (
    <div className="grid gap-6 pt-4 lg:grid-cols-[16rem_1fr]">
      <div className="flex flex-col gap-3">
        <CreateTableDialog workspaceId={workspaceId} onCreated={onSelect} />
        <QueryBoundary
          query={query}
          errorTitle="Couldn't load the tables."
          isEmpty={(tables) => tables.length === 0}
          empty={
            <EmptyState
              icon={Table02Icon}
              title="No tables yet"
              description="Create your first table, then add rows to it."
            />
          }
          loading={
            <div className="flex flex-col gap-2">
              {Array.from({ length: 4 }, (_, index) => (
                <Skeleton key={index} className="h-9 w-full" />
              ))}
            </div>
          }
        >
          {(tables) => (
            <ul aria-label="Tables" className="flex flex-col gap-1">
              {tables.map((table) => (
                <li key={table.name}>
                  <button
                    type="button"
                    aria-current={table.name === selected ? 'true' : undefined}
                    onClick={() => {
                      onSelect(table.name)
                    }}
                    className={cn(
                      'flex h-9 w-full items-center gap-2 rounded-md px-2 text-left text-body outline-none hover:bg-surface-muted focus-visible:ring-2 focus-visible:ring-ring',
                      table.name === selected && 'bg-surface-muted font-medium',
                    )}
                  >
                    <span className="truncate font-mono">{table.name}</span>
                    {table.row_estimate !== null && (
                      <span className="ml-auto text-small text-muted-foreground">
                        {formatNumber(table.row_estimate)}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </QueryBoundary>
      </div>
      <div className="min-w-0">
        {selected ? (
          <TableEditor
            key={selected}
            workspaceId={workspaceId}
            name={selected}
            onGone={() => {
              onSelect(undefined)
            }}
            onRenamed={onSelect}
          />
        ) : (
          <p className="text-body text-muted-foreground">Pick a table to edit its columns and rows.</p>
        )}
      </div>
    </div>
  )
}
