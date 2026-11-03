import { PlayIcon } from '@hugeicons/core-free-icons'
import { useMutation } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { ApiError } from '@/lib/api'
import { errorText } from '@/lib/api/error-text'
import { formatNumber } from '@/lib/format'

import { runSql, type SqlResult } from './api'
import { cellText } from '@/lib/cell'
import { useQueryDraftStore } from '@/stores/query-draft'

function Statement({ statement }: { statement: SqlResult['statements'][number] }) {
  return (
    <section aria-label={`Statement ${statement.index}`} className="flex flex-col gap-2">
      <div className="flex items-center gap-2 text-small">
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

/** Read-only SQL on your own workspace (SELECT, WITH, EXPLAIN, SHOW). To change the data, import a dump. */
export function SqlConsole({ workspaceId }: { workspaceId: number }) {
  const sql = useQueryDraftStore((state) => state.drafts[workspaceId] ?? '')
  const setDraft = useQueryDraftStore((state) => state.setDraft)
  const mutation = useMutation({
    mutationFn: () => runSql(workspaceId, sql),
  })
  const failure = mutation.isError ? mutation.error : null
  const detail = failure instanceof ApiError ? failure.errors[0]?.message : undefined

  return (
    <div className="flex flex-col gap-3 pt-4">
      <p className="text-small text-muted-foreground">
        Read-only: SELECT, WITH, EXPLAIN and SHOW. Your data changes only when you import a dump.
      </p>
      <Textarea
        aria-label="SQL"
        className="min-h-40 font-mono text-code"
        spellCheck={false}
        value={sql}
        onChange={(event) => {
          setDraft(workspaceId, event.target.value)
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
            {mutation.data.statements.length} {mutation.data.statements.length === 1 ? 'query' : 'queries'} in{' '}
            {formatNumber(mutation.data.elapsed_ms)} ms.
          </p>
          {mutation.data.statements.map((statement) => (
            <Statement key={statement.index} statement={statement} />
          ))}
        </div>
      )}
    </div>
  )
}
