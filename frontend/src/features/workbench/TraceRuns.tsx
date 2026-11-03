import { Clock01Icon, Search01Icon } from '@hugeicons/core-free-icons'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { useState, type SyntheticEvent } from 'react'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/data-state'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatDuration, formatRelative } from '@/lib/format'

import { TRACE_STATUSES, traceRunsQuery, type TraceFilters } from './api'
import { Pager } from './Pager'

const ANY = 'any'

function Filters({ filters, onChange }: { filters: TraceFilters; onChange: (next: TraceFilters) => void }) {
  const [text, setText] = useState(filters.q ?? '')
  const submit = (event: SyntheticEvent) => {
    event.preventDefault()
    onChange({ ...filters, q: text.trim() || undefined, offset: undefined })
  }
  return (
    <div className="flex flex-wrap items-end gap-3">
      <form onSubmit={submit} className="flex min-w-60 flex-1 gap-2">
        <Input
          type="search"
          aria-label="Search questions"
          placeholder="Search questions"
          value={text}
          onChange={(event) => {
            setText(event.target.value)
          }}
        />
        <Button type="submit" variant="secondary" icon={Search01Icon}>
          Search
        </Button>
      </form>
      <div className="w-44">
        <Select
          value={filters.status ?? ANY}
          onValueChange={(value) => {
            onChange({
              ...filters,
              status: value === ANY ? undefined : (value as (typeof TRACE_STATUSES)[number]),
              offset: undefined,
            })
          }}
        >
          <SelectTrigger aria-label="Status" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ANY}>Any status</SelectItem>
            {TRACE_STATUSES.map((status) => (
              <SelectItem key={status} value={status}>
                {status.replace('_', ' ')}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="w-40">
        <Select
          value={filters.feedback ?? ANY}
          onValueChange={(value) => {
            onChange({
              ...filters,
              feedback: value === ANY ? undefined : (value as 'up' | 'down'),
              offset: undefined,
            })
          }}
        >
          <SelectTrigger aria-label="Feedback" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ANY}>Any feedback</SelectItem>
            <SelectItem value="up">Thumbs up</SelectItem>
            <SelectItem value="down">Thumbs down</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="w-40">
        <Select
          value={filters.edited === undefined ? ANY : String(filters.edited)}
          onValueChange={(value) => {
            onChange({ ...filters, edited: value === ANY ? undefined : value === 'true', offset: undefined })
          }}
        >
          <SelectTrigger aria-label="Edited" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ANY}>Edited or not</SelectItem>
            <SelectItem value="true">Edited SQL</SelectItem>
            <SelectItem value="false">Not edited</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}

/** Every user's demo-workspace runs, for review. Staff only. */
export function TraceRuns({ filters }: { filters: TraceFilters }) {
  const navigate = useNavigate({ from: '/workbench/runs/' })
  const query = useQuery(traceRunsQuery(filters))
  const change = (next: TraceFilters) => {
    void navigate({ search: next })
  }
  return (
    <div className="flex flex-col gap-4">
      <Filters key={filters.q ?? ''} filters={filters} onChange={change} />
      <QueryBoundary
        query={query}
        errorTitle="Couldn't load the traces."
        isEmpty={(page) => page.data.length === 0}
        empty={
          <EmptyState icon={Clock01Icon} title="No traces" description="No run matches these filters." />
        }
        loading={
          <div className="flex flex-col gap-2">
            {Array.from({ length: 8 }, (_, index) => (
              <Skeleton key={index} className="h-10 w-full" />
            ))}
          </div>
        }
      >
        {(page) => (
          <div className="flex flex-col gap-3">
            <Table>
              <caption className="sr-only">Traces</caption>
              <TableHeader>
                <TableRow>
                  <TableHead>Question</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Signals</TableHead>
                  <TableHead>Time</TableHead>
                  <TableHead>When</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {page.data.map((run) => (
                  <TableRow key={run.id}>
                    <TableCell className="max-w-md">
                      <Link
                        to="/workbench/runs/$runId"
                        params={{ runId: String(run.id) }}
                        className="line-clamp-2 underline-offset-4 hover:underline"
                      >
                        {run.question}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          run.status === 'succeeded'
                            ? 'success'
                            : run.status === 'failed'
                              ? 'danger'
                              : 'neutral'
                        }
                      >
                        {run.status.replace('_', ' ')}
                      </Badge>
                    </TableCell>
                    <TableCell className="flex flex-wrap gap-1">
                      {run.edited && <Badge variant="primary">edited</Badge>}
                      {run.feedback === 'down' && <Badge variant="danger">thumbs down</Badge>}
                      {run.feedback === 'up' && <Badge variant="success">thumbs up</Badge>}
                      {run.check === 'needs_look' && <Badge variant="warning">needs a look</Badge>}
                      {run.revisions > 0 && <Badge>{run.revisions} revisions</Badge>}
                    </TableCell>
                    <TableCell>{formatDuration(run.latency_ms / 1000)}</TableCell>
                    <TableCell>{formatRelative(run.created_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Pager
              meta={page.meta}
              onOffset={(offset) => {
                change({ ...filters, offset })
              }}
            />
          </div>
        )}
      </QueryBoundary>
    </div>
  )
}
