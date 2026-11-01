import { Cancel01Icon, CheckmarkCircle02Icon, Edit02Icon } from '@hugeicons/core-free-icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { CodeBlock } from '@/components/typography/Code'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { ApiError } from '@/lib/api'
import { formatDateTime } from '@/lib/format'

import { approveRun, cancelRun, editRun } from './api'
import { errorText } from '@/lib/api/error-text'
import { useDraftStore } from './draft-store'
import type { Pending } from './types'

const GUARD_LABEL: Record<string, string> = {
  limit_clamped: 'Row limit applied',
  qualified_tables: 'Table names qualified',
}

type ApprovalCardProps = {
  runId: number
  pending: Pending
  /** Called after the server accepted the decision, so the page can reopen the stream. */
  onDecided: () => void
}

/** The checkpoint: the SQL the agent wants to run, and what you can do about it. */
export function ApprovalCard({ runId, pending, onDecided }: ApprovalCardProps) {
  const queryClient = useQueryClient()
  const draft = useDraftStore((state) => state.drafts[runId])
  const setDraft = useDraftStore((state) => state.setDraft)
  const clearDraft = useDraftStore((state) => state.clearDraft)
  const [editing, setEditing] = useState(draft !== undefined)
  const text = draft ?? pending.sql

  const decided = () => {
    clearDraft(runId)
    void queryClient.invalidateQueries({ queryKey: ['run', runId] })
    void queryClient.invalidateQueries({ queryKey: ['agent-limits'] })
    onDecided()
  }
  const approve = useMutation({ mutationFn: () => approveRun(runId), onSuccess: decided })
  const cancel = useMutation({ mutationFn: () => cancelRun(runId), onSuccess: decided })
  const edit = useMutation({ mutationFn: () => editRun(runId, text), onSuccess: decided })
  const busy = approve.isPending || cancel.isPending || edit.isPending

  const failure = [approve, cancel, edit].find((mutation) => mutation.isError)?.error
  const sqlError =
    edit.error instanceof ApiError && edit.error.code === 'guard_rejected'
      ? (edit.error.errors.find((e) => e.field === 'sql')?.message ?? edit.error.message)
      : null

  return (
    <Card aria-label="Approve the SQL">
      <CardHeader>
        <CardTitle>Approve this SQL before it runs</CardTitle>
        <CardDescription>{pending.rationale}</CardDescription>
        <div className="flex flex-wrap items-center gap-2">
          {pending.guard.map((code) => (
            <Badge key={code} variant="info">
              {GUARD_LABEL[code] ?? code}
            </Badge>
          ))}
          {pending.revision > 0 && <Badge>Revision {pending.revision}</Badge>}
          <span className="inline-flex items-center gap-1 text-small text-muted-foreground">
            Expires {formatDateTime(pending.expires_at)}
          </span>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {editing ? (
          <>
            <Textarea
              aria-label="SQL"
              className="min-h-40 font-mono text-code"
              value={text}
              onChange={(event) => {
                setDraft(runId, event.target.value)
              }}
              aria-invalid={sqlError ? true : undefined}
              aria-describedby={sqlError ? 'sql-error' : undefined}
              spellCheck={false}
            />
            {sqlError && (
              <p id="sql-error" role="alert" className="text-small text-danger-foreground">
                {sqlError}
              </p>
            )}
          </>
        ) : (
          <CodeBlock code={pending.sql} />
        )}
        {pending.assumptions.length > 0 && (
          <div>
            <p className="text-small font-medium">Assumptions</p>
            <ul className="list-disc pl-5 text-small text-muted-foreground">
              {pending.assumptions.map((assumption) => (
                <li key={assumption}>{assumption}</li>
              ))}
            </ul>
          </div>
        )}
        {failure && !sqlError && (
          <p role="alert" className="text-small text-danger-foreground">
            {errorText(failure).message} {errorText(failure).hint}
          </p>
        )}
      </CardContent>
      <CardFooter className="flex flex-wrap gap-2">
        {editing ? (
          <Button
            icon={CheckmarkCircle02Icon}
            loading={edit.isPending}
            disabled={busy || !text.trim()}
            onClick={() => {
              edit.mutate()
            }}
          >
            Run my edited SQL
          </Button>
        ) : (
          <Button
            icon={CheckmarkCircle02Icon}
            loading={approve.isPending}
            disabled={busy}
            onClick={() => {
              approve.mutate()
            }}
          >
            Approve and run
          </Button>
        )}
        {!editing && (
          <Button
            variant="secondary"
            icon={Edit02Icon}
            disabled={busy}
            onClick={() => {
              setEditing(true)
              setDraft(runId, pending.sql)
            }}
          >
            Edit SQL
          </Button>
        )}
        {editing && (
          <Button
            variant="secondary"
            icon={Cancel01Icon}
            disabled={busy}
            onClick={() => {
              clearDraft(runId)
              setEditing(false)
              edit.reset()
            }}
          >
            Discard my edit
          </Button>
        )}
        <Button
          variant="ghost"
          icon={Cancel01Icon}
          loading={cancel.isPending}
          disabled={busy}
          onClick={() => {
            cancel.mutate()
          }}
        >
          Cancel run
        </Button>
      </CardFooter>
    </Card>
  )
}
