import { PlayIcon } from '@hugeicons/core-free-icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { ApiError } from '@/lib/api'
import { errorText } from '@/lib/api/error-text'
import { formatNumber } from '@/lib/format'

import { invalidateWorkspace, runSql, type SqlResult } from './api'
import { cellText } from './cell'

function Statement({ statement }: { statement: SqlResult['statements'][number] }) {
  return (
    <section aria-label={`Statement ${statement.index + 1}`} className="flex flex-col gap-2">
      <div className="flex items-center gap-2 text-small">
        <Badge variant={statement.kind === 'query' ? 'info' : 'neutral'}>{statement.kind}</Badge>
        <span className="font-mono">{statement.command}</span>
        <span className="text-muted-foreground">{formatNumber(statement.row_count)} rows</span>
      </div>
      {statement.columns.length > 0 && (
        <>
          {statement.truncated && (
            <p role="status" className="text-small text-warning-foreground">
              Showing the first {formatNumber(statement.rows.length)} rows.
            </p>
          )}
          <Table>
            <TableHeader>
              <TableRow>
                {statement.columns.map((column) => (
                  <TableHead key={column}>{column}</TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {statement.rows.map((row, index) => (
                <TableRow key={index}>
                  {statement.columns.map((column, position) => (
                    <TableCell key={column} className="font-mono">
                      {cellText(row[position])}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </>
      )}
    </section>
  )
}

/** Your own SQL, run as the workspace's own role in one transaction. Any failure rolls the whole request back. */
export function SqlConsole({ workspaceId }: { workspaceId: number }) {
  const [sql, setSql] = useState('')
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: () => runSql(workspaceId, sql),
    onSuccess: () => invalidateWorkspace(queryClient, workspaceId),
  })
  const failure = mutation.isError ? mutation.error : null
  const detail = failure instanceof ApiError ? failure.errors[0]?.message : undefined

  return (
    <div className="flex flex-col gap-3 pt-4">
      <p className="text-small text-muted-foreground">
        Runs as this workspace&apos;s own database role, all in one transaction. If a statement fails, nothing
        is saved.
      </p>
      <Textarea
        aria-label="SQL"
        className="min-h-40 font-mono text-code"
        spellCheck={false}
        value={sql}
        onChange={(event) => {
          setSql(event.target.value)
        }}
        aria-invalid={failure ? true : undefined}
      />
      {failure && (
        <p role="alert" className="font-mono text-small whitespace-pre-wrap text-danger-foreground">
          {detail ?? `${errorText(failure).message} ${errorText(failure).hint}`}
        </p>
      )}
      <div>
        <Button
          icon={PlayIcon}
          loading={mutation.isPending}
          disabled={!sql.trim()}
          onClick={() => {
            mutation.mutate()
          }}
        >
          Run
        </Button>
      </div>
      {mutation.data && (
        <div className="flex flex-col gap-4">
          <p className="text-small text-muted-foreground">
            {mutation.data.counts.ddl} schema changes, {mutation.data.counts.data} data changes,{' '}
            {mutation.data.counts.query} queries in {formatNumber(mutation.data.elapsed_ms)} ms.
          </p>
          {mutation.data.statements.map((statement) => (
            <Statement key={statement.index} statement={statement} />
          ))}
        </div>
      )}
    </div>
  )
}
