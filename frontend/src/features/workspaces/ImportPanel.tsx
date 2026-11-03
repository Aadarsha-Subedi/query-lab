import { File02Icon, RefreshIcon, Upload04Icon } from '@hugeicons/core-free-icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Heading } from '@/components/typography/Heading'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Progress, ProgressLabel, ProgressValue } from '@/components/ui/progress'
import { errorText } from '@/lib/api/error-text'
import { formatBytes, formatNumber } from '@/lib/format'

import {
  createImport,
  importsQuery,
  importStatus,
  invalidateWorkspace,
  startImport,
  uploadFile,
  workspaceLimitsQuery,
  workspaceQuery,
  type ImportJob,
} from './api'

const DUMP_COMMAND = 'pg_dump mydb | gzip > dump.sql.gz'

function isDone(job: ImportJob | undefined): boolean {
  return job?.status === 'succeeded' || job?.status === 'failed'
}

/** Where in the dump a failure happened, when the server knows. */
function wherePhrase(job: ImportJob): string {
  const error = job.error
  if (!error?.statement) return ''
  return error.line ? `Statement ${error.statement}, line ${error.line}. ` : `Statement ${error.statement}. `
}

function JobResult({ job }: { job: ImportJob }) {
  if (job.status === 'succeeded') {
    return (
      <p role="status" className="text-body">
        Imported {formatNumber(job.tables_created)} {job.tables_created === 1 ? 'table' : 'tables'} (
        {formatNumber(job.statements_run)} statements). Ask a question or open the Schema tab to look around.
      </p>
    )
  }
  if (job.status === 'failed' && job.error) {
    return (
      <div role="alert" className="flex flex-col gap-1 rounded-md bg-danger-subtle p-4">
        <p className="text-body font-medium text-danger-foreground">The import did not go through.</p>
        <p className="font-mono text-small whitespace-pre-wrap">
          {wherePhrase(job)}
          {job.error.message}
        </p>
        <p className="text-small text-muted-foreground">
          Nothing was changed. Fix the dump and upload it again.
        </p>
      </div>
    )
  }
  return null
}

const STATUS_LABEL: Record<ImportJob['status'], string> = {
  awaiting_upload: 'Waiting for the upload',
  queued: 'Queued',
  running: 'Importing',
  succeeded: 'Done',
  failed: 'Failed',
}

/**
 * The only way to add or change tables: upload a plain-SQL pg_dump (.sql or .sql.gz). The file goes
 * straight to the bucket, then a background job loads it; a failed import changes nothing.
 */
function ImportBody({ workspaceId }: { workspaceId: number }) {
  const queryClient = useQueryClient()
  const input = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [replace, setReplace] = useState(false)
  const [progress, setProgress] = useState(0)
  const [jobId, setJobId] = useState<number | null>(null)
  const limits = useQuery(workspaceLimitsQuery)
  const workspace = useQuery(workspaceQuery(workspaceId))
  const history = useQuery(importsQuery(workspaceId))
  const maxBytes = limits.data?.max_dump_bytes
  const hasTables = (workspace.data?.tables ?? 0) > 0

  const status = useQuery({
    ...importStatus(workspaceId, jobId ?? 0),
    enabled: jobId !== null,
  })
  const job = status.data

  const upload = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error('Choose a file first.')
      const created = await createImport(workspaceId, { filename: file.name, size: file.size, replace })
      setProgress(0)
      await uploadFile(created.upload_url, file, setProgress)
      return startImport(workspaceId, created.id)
    },
    onSuccess: (started) => {
      setJobId(started.id)
    },
  })

  useEffect(() => {
    if (isDone(job)) {
      void invalidateWorkspace(queryClient, workspaceId)
      void queryClient.invalidateQueries({ queryKey: ['workspace', workspaceId, 'imports'] })
    }
  }, [job, queryClient, workspaceId])

  const tooBig = file !== null && maxBytes !== undefined && file.size > maxBytes
  const badName = file !== null && !/\.sql(\.gz)?$/i.test(file.name)
  const fileProblem = tooBig
    ? `This file is ${formatBytes(file.size)}. The limit is ${formatBytes(maxBytes)}.`
    : badName
      ? 'Choose a .sql or .sql.gz file made with pg_dump.'
      : null
  const working = upload.isPending || (jobId !== null && !isDone(job))
  const failure = upload.isError ? errorText(upload.error) : null

  return (
    <div className="flex min-w-0 flex-col gap-6">
      <div className="flex flex-col gap-2">
        <p className="text-small font-medium">Make the file</p>
        <pre className="overflow-x-auto rounded-md bg-surface-muted p-3 font-mono text-code">
          {DUMP_COMMAND}
        </pre>
        <p className="text-small text-muted-foreground">
          Plain SQL, up to {maxBytes === undefined ? '50 MB' : formatBytes(maxBytes)}. Roles, permissions and
          row security from your server are left out; everything else is copied.
        </p>
      </div>

      <div className="flex flex-col gap-3">
        <input
          ref={input}
          type="file"
          accept=".sql,.gz,application/sql,application/gzip"
          className="sr-only"
          aria-label="SQL dump file"
          onChange={(event) => {
            setFile(event.target.files?.[0] ?? null)
            setJobId(null)
            upload.reset()
          }}
        />
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="secondary"
            icon={File02Icon}
            disabled={working}
            onClick={() => input.current?.click()}
          >
            {file ? 'Choose another file' : 'Choose a file'}
          </Button>
          {file && (
            <span className="min-w-0 truncate font-mono text-small">
              {file.name} · {formatBytes(file.size)}
            </span>
          )}
        </div>
        {fileProblem && (
          <p role="alert" className="text-small text-danger-foreground">
            {fileProblem}
          </p>
        )}
        {hasTables && (
          <div className="flex items-start gap-2">
            <Checkbox
              id="replace-data"
              checked={replace}
              disabled={working}
              onCheckedChange={(checked) => {
                setReplace(checked === true)
              }}
            />
            <Label htmlFor="replace-data" className="flex flex-col items-start gap-0.5">
              <span>Replace the tables already here</span>
              <span className="text-small font-normal text-muted-foreground">
                This workspace has tables. Without this the import is refused. If the new dump fails, the old
                tables stay.
              </span>
            </Label>
          </div>
        )}
        <div>
          <Button
            icon={Upload04Icon}
            loading={working}
            disabled={!file || fileProblem !== null}
            onClick={() => {
              setJobId(null)
              upload.mutate()
            }}
          >
            Import
          </Button>
        </div>
      </div>

      {upload.isPending && (
        <Progress value={Math.round(progress * 100)} max={100} className="gap-1.5">
          <ProgressLabel className="text-small text-muted-foreground">Uploading</ProgressLabel>
          <ProgressValue className="text-small">{() => `${Math.round(progress * 100)}%`}</ProgressValue>
        </Progress>
      )}
      {jobId !== null && job && !isDone(job) && (
        <div className="flex flex-wrap items-center gap-3">
          <p role="status" className="text-body text-muted-foreground">
            {STATUS_LABEL[job.status]}. A big dump can take a minute.
          </p>
          <Button
            variant="secondary"
            size="sm"
            icon={RefreshIcon}
            loading={status.isFetching}
            onClick={() => {
              void status.refetch()
            }}
          >
            Check progress
          </Button>
        </div>
      )}
      {failure && (
        <p role="alert" className="text-small text-danger-foreground">
          {failure.message} {failure.hint}
        </p>
      )}
      {job && <JobResult job={job} />}

      <section aria-label="Past imports" className="flex flex-col gap-2">
        <Heading level={3}>Past imports</Heading>
        <QueryBoundary
          query={history}
          errorTitle="Couldn't load past imports."
          isEmpty={(jobs) => jobs.length === 0}
          empty={<p className="text-small text-muted-foreground">No imports yet.</p>}
          loading={<Skeleton className="h-16 w-full" />}
        >
          {(jobs) => (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Result</TableHead>
                  <TableHead className="text-right">Size</TableHead>
                  <TableHead className="text-right">Tables</TableHead>
                  <TableHead>Problem</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((past) => (
                  <TableRow key={past.id}>
                    <TableCell className="whitespace-nowrap">
                      {new Date(past.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          past.status === 'succeeded'
                            ? 'success'
                            : past.status === 'failed'
                              ? 'danger'
                              : 'neutral'
                        }
                      >
                        {STATUS_LABEL[past.status]}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">{formatBytes(past.size_bytes)}</TableCell>
                    <TableCell className="text-right">
                      {past.status === 'succeeded' ? formatNumber(past.tables_created) : ''}
                    </TableCell>
                    <TableCell
                      className="max-w-64 truncate text-muted-foreground"
                      title={past.error?.message}
                    >
                      {past.error ? `${wherePhrase(past)}${past.error.message}` : ''}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </QueryBoundary>
      </section>
    </div>
  )
}

/**
 * The Import dump popup, opened from the workspace menu on the Schema page: the upload form, then a
 * table of past imports. It is the only way to add or change tables.
 */
export function ImportDialog({
  workspaceId,
  open,
  onOpenChange,
}: {
  workspaceId: number
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Import a SQL dump</DialogTitle>
          <DialogDescription>
            Your tables and data come from a dump of your database. To change them, import a new dump. Queries
            never change your data.
          </DialogDescription>
        </DialogHeader>
        <ImportBody workspaceId={workspaceId} />
      </DialogContent>
    </Dialog>
  )
}
