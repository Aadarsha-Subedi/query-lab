import { Table02Icon } from '@hugeicons/core-free-icons'
import { useQuery } from '@tanstack/react-query'

import { QueryBoundary } from '@/components/QueryBoundary'
import { CodeBlock } from '@/components/typography/Code'
import { EmptyState } from '@/components/ui/data-state'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ApiError } from '@/lib/api'
import { describeError } from '@/lib/api/errors'
import { formatNumber } from '@/lib/format'

import { resultQuery } from './api'
import type { RunResult } from './types'

function cell(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint')
    return String(value)
  return JSON.stringify(value)
}

function Rows({ result }: { result: RunResult }) {
  return (
    <div className="flex flex-col gap-3">
      {result.truncated && (
        <p role="status" className="text-small text-warning-foreground">
          Showing the first {formatNumber(result.rows.length)} rows. There are more than this view shows.
        </p>
      )}
      {result.rows.length === 0 ? (
        <EmptyState icon={Table02Icon} title="No rows" description="The query ran and matched nothing." />
      ) : (
        <Table>
          <caption className="sr-only">Query result, {formatNumber(result.row_count)} rows</caption>
          <TableHeader>
            <TableRow>
              {result.columns.map((column) => (
                <TableHead key={column}>{column}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {result.rows.map((row, index) => (
              <TableRow key={index}>
                {result.columns.map((column, position) => (
                  <TableCell key={column} className="font-mono">
                    {cell(row[position])}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <details className="rounded-md border bg-surface p-3">
        <summary className="cursor-pointer text-body font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring">
          The SQL that produced this
        </summary>
        <div className="mt-3">
          <CodeBlock code={result.sql} />
        </div>
      </details>
      <p className="text-small text-muted-foreground">
        {formatNumber(result.row_count)} rows. Results are fetched by running the SQL again, so the numbers
        can differ from the first run if the data changed.
      </p>
    </div>
  )
}

/** The rows of a succeeded run, in its own loading / error / empty / success box. */
export function ResultTable({ runId }: { runId: number }) {
  const query = useQuery(resultQuery(runId))
  const detail = query.error instanceof ApiError ? describeError(query.error.code, query.error.message) : null
  return (
    <section aria-label="Result">
      <QueryBoundary
        query={query}
        errorTitle={detail?.message ?? "Couldn't load the result."}
        loading={
          <div className="flex flex-col gap-2">
            <Skeleton className="h-20 w-full" />
            {Array.from({ length: 5 }, (_, index) => (
              <Skeleton key={index} className="h-8 w-full" />
            ))}
          </div>
        }
      >
        {(result) => <Rows result={result} />}
      </QueryBoundary>
    </section>
  )
}
