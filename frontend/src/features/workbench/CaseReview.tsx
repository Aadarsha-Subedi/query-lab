import { Cancel01Icon, CheckmarkCircle02Icon, HelpCircleIcon } from '@hugeicons/core-free-icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'

import { QueryBoundary } from '@/components/QueryBoundary'
import { CodeBlock } from '@/components/typography/Code'
import { Heading } from '@/components/typography/Heading'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { ApiError } from '@/lib/api'
import { cellText } from '@/lib/cell'
import { errorText } from '@/lib/api/error-text'
import { formatNumber } from '@/lib/format'

import { approveCase, caseDetailQuery, markUnanswerable, rejectCase, type CaseDetail } from './api'

function Preview({ preview }: { preview: NonNullable<CaseDetail['preview']> }) {
  if (preview.error) {
    return (
      <p role="alert" className="text-small text-danger-foreground">
        The draft did not run: {preview.error}
      </p>
    )
  }
  return (
    <div className="flex flex-col gap-2">
      <p className="text-small text-muted-foreground">
        Run just now, not stored. {formatNumber(preview.row_count)} rows
        {preview.truncated ? ', first rows shown' : ''}.
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            {preview.columns.map((column) => (
              <TableHead key={column}>{column}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {preview.rows.map((row, index) => (
            <TableRow key={index}>
              {preview.columns.map((column, position) => (
                <TableCell key={column} className="font-mono">
                  {cellText(row[position])}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function Review({ item }: { item: CaseDetail }) {
  const queryClient = useQueryClient()
  const startSql = item.gold_sql || item.draft_sql
  const [question, setQuestion] = useState(item.question)
  const [sql, setSql] = useState(startSql)
  const [reason, setReason] = useState('')
  const [note, setNote] = useState('')
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ['workbench', 'case', item.id] }),
      queryClient.invalidateQueries({ queryKey: ['workbench', 'cases'] }),
      queryClient.invalidateQueries({ queryKey: ['workbench', 'clusters'] }),
    ])
  const approve = useMutation({
    mutationFn: () =>
      approveCase(item.id, {
        question: question !== item.question ? question : undefined,
        sql: sql !== startSql ? sql : undefined,
      }),
    onSuccess: refresh,
  })
  const reject = useMutation({ mutationFn: () => rejectCase(item.id, reason), onSuccess: refresh })
  const unanswerable = useMutation({ mutationFn: () => markUnanswerable(item.id, note), onSuccess: refresh })
  const busy = approve.isPending || reject.isPending || unanswerable.isPending
  const reviewable = item.status === 'drafted'
  const sqlEdited = sql.trim() !== '' && sql !== startSql
  // A failed draft has nothing to approve until the reviewer writes the SQL.
  const canApprove = reviewable && !busy && sql.trim() !== '' && (!item.draft_error || sqlEdited)

  const sqlProblem =
    approve.error instanceof ApiError && approve.error.errors.find((e) => e.field === 'sql')?.message
  const failure = [approve, reject, unanswerable].find((m) => m.isError)?.error

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-2">
        <Heading level={2}>Case {item.id}</Heading>
        <Badge>{item.status}</Badge>
        {!item.answerable && <Badge variant="warning">marked unanswerable</Badge>}
        {item.run_id !== null && (
          <Link
            to="/workbench/runs/$runId"
            params={{ runId: String(item.run_id) }}
            className="text-small underline underline-offset-4"
          >
            Source trace
          </Link>
        )}
      </div>
      <p className="text-small text-muted-foreground">
        Picked because: {item.reasons.join(', ') || 'no reason recorded'}.
      </p>

      <div className="grid gap-1.5">
        <Label htmlFor="case-question">Question (remove anything personal before approving)</Label>
        <Textarea
          id="case-question"
          value={question}
          disabled={!reviewable}
          onChange={(event) => {
            setQuestion(event.target.value)
          }}
        />
      </div>

      {item.source_sql && (
        <section aria-label="SQL the user ran" className="flex flex-col gap-1">
          <p className="text-small font-medium">What the user ended up with</p>
          <CodeBlock code={item.source_sql} />
        </section>
      )}
      {item.draft_error ? (
        <p role="alert" className="text-small text-danger-foreground">
          The draft failed: {item.draft_error}. Write the SQL yourself to approve it.
        </p>
      ) : (
        item.draft_model && <p className="text-small text-muted-foreground">Drafted by {item.draft_model}.</p>
      )}

      <div className="grid gap-1.5">
        <Label htmlFor="case-sql">Expected SQL</Label>
        <Textarea
          id="case-sql"
          className="min-h-40 font-mono text-code"
          spellCheck={false}
          disabled={!reviewable}
          value={sql}
          aria-invalid={sqlProblem ? true : undefined}
          onChange={(event) => {
            setSql(event.target.value)
          }}
        />
        {sqlProblem && (
          <p role="alert" className="text-small text-danger-foreground">
            {sqlProblem}
          </p>
        )}
      </div>

      {item.preview && <Preview preview={item.preview} />}

      {reviewable ? (
        <div className="flex flex-col gap-4 border-t pt-4">
          <div>
            <Button
              icon={CheckmarkCircle02Icon}
              loading={approve.isPending}
              disabled={!canApprove}
              onClick={() => {
                approve.mutate()
              }}
            >
              Approve as gold
            </Button>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <div className="grid gap-1.5">
              <Label htmlFor="case-reason">Reason for rejecting</Label>
              <Input
                id="case-reason"
                value={reason}
                onChange={(event) => {
                  setReason(event.target.value)
                }}
              />
            </div>
            <Button
              variant="secondary"
              icon={Cancel01Icon}
              loading={reject.isPending}
              disabled={busy}
              onClick={() => {
                reject.mutate()
              }}
            >
              Reject
            </Button>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <div className="grid gap-1.5">
              <Label htmlFor="case-note">Note for unanswerable</Label>
              <Input
                id="case-note"
                value={note}
                onChange={(event) => {
                  setNote(event.target.value)
                }}
              />
            </div>
            <Button
              variant="secondary"
              icon={HelpCircleIcon}
              loading={unanswerable.isPending}
              disabled={busy}
              onClick={() => {
                unanswerable.mutate()
              }}
            >
              Mark unanswerable
            </Button>
          </div>
          {failure && !sqlProblem && (
            <p role="alert" className="text-small text-danger-foreground">
              {errorText(failure).message} {errorText(failure).hint}
            </p>
          )}
        </div>
      ) : (
        <p className="text-body text-muted-foreground">
          This case is {item.status}, so it can no longer be reviewed.
          {item.note && ` Note: ${item.note}`}
        </p>
      )}
    </div>
  )
}

export function CaseReview({ caseId }: { caseId: number }) {
  const query = useQuery(caseDetailQuery(caseId))
  return (
    <QueryBoundary
      query={query}
      errorTitle="Couldn't load this case."
      loading={<Skeleton className="h-80 w-full" />}
    >
      {(item) => <Review key={`${item.id}:${item.status}`} item={item} />}
    </QueryBoundary>
  )
}
