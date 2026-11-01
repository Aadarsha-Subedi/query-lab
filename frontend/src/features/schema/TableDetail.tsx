import { useQuery } from '@tanstack/react-query'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatNumber } from '@/lib/format'

import { tableQuery, type TableInfo } from './api'

function Detail({ table }: { table: TableInfo }) {
  return (
    <div className="flex flex-col gap-4">
      {table.comment && <p className="text-body text-muted-foreground">{table.comment}</p>}
      {table.row_estimate !== null && (
        <p className="text-small text-muted-foreground">About {formatNumber(table.row_estimate)} rows</p>
      )}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Column</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Notes</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {table.columns.map((column) => {
            const reference = table.foreign_keys.find((fk) => fk.columns.includes(column.name))
            return (
              <TableRow key={column.name}>
                <TableCell className="font-mono">{column.name}</TableCell>
                <TableCell className="font-mono text-muted-foreground">{column.type}</TableCell>
                <TableCell className="whitespace-normal">
                  <div className="flex flex-wrap items-center gap-1">
                    {table.primary_key.includes(column.name) && <Badge variant="primary">PK</Badge>}
                    {reference && <Badge variant="info">FK to {reference.ref_table}</Badge>}
                    {!column.nullable && <Badge>required</Badge>}
                    {column.comment && (
                      <span className="text-small text-muted-foreground">{column.comment}</span>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}

/** One table's columns, keys and comments, in its own loading / error box. */
export function TableDetail({ name, workspace }: { name: string; workspace?: number }) {
  const query = useQuery(tableQuery(name, workspace))
  return (
    <QueryBoundary
      query={query}
      errorTitle={`Couldn't load ${name}.`}
      loading={
        <div className="flex flex-col gap-2">
          {Array.from({ length: 6 }, (_, index) => (
            <Skeleton key={index} className="h-8 w-full" />
          ))}
        </div>
      }
    >
      {(table) => <Detail table={table} />}
    </QueryBoundary>
  )
}
