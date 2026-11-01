import { ArrowLeft01Icon, ArrowRight01Icon, Clock01Icon, Search01Icon } from '@hugeicons/core-free-icons'
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
import { formatDuration, formatNumber, formatRelative } from '@/lib/format'

import { RunStatusBadge } from '@/features/ask/RunStatusBadge'
import { runStatusLabel } from '@/features/ask/run-status'

import { historyQuery, ORDERINGS, STATUSES, type HistoryFilters } from './api'

const ALL = 'all'
const ORDER_LABEL: Record<(typeof ORDERINGS)[number], string> = {
  '-created_at': 'Newest first',
  created_at: 'Oldest first',
  '-latency_ms': 'Slowest first',
  latency_ms: 'Fastest first',
}

function Filters({
  filters,
  onChange,
}: {
  filters: HistoryFilters
  onChange: (next: HistoryFilters) => void
}) {
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
          placeholder="Search your questions"
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
          value={filters.status ?? ALL}
          onValueChange={(value) => {
            onChange({
              ...filters,
              status: value === ALL ? undefined : (value as (typeof STATUSES)[number]),
              offset: undefined,
            })
          }}
        >
          <SelectTrigger aria-label="Status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All statuses</SelectItem>
            {STATUSES.map((status) => (
              <SelectItem key={status} value={status}>
                {runStatusLabel(status)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="w-44">
        <Select
          value={filters.ordering ?? '-created_at'}
          onValueChange={(value) => {
            onChange({ ...filters, ordering: value as (typeof ORDERINGS)[number], offset: undefined })
          }}
        >
          <SelectTrigger aria-label="Order">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ORDERINGS.map((order) => (
              <SelectItem key={order} value={order}>
                {ORDER_LABEL[order]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}

/** Your past runs: filter, sort, page. Everything is in the URL. */
export function HistoryTable({ filters }: { filters: HistoryFilters }) {
  const navigate = useNavigate({ from: '/history' })
  const query = useQuery(historyQuery(filters))
  const change = (next: HistoryFilters) => {
    void navigate({ search: next })
  }

  return (
    <div className="flex flex-col gap-4">
      <Filters key={filters.q ?? ''} filters={filters} onChange={change} />
      <QueryBoundary
        query={query}
        errorTitle="Couldn't load your history."
        isEmpty={(page) => page.data.length === 0}
        empty={
          <EmptyState
            icon={Clock01Icon}
            title="No runs found"
            description="Nothing matches these filters, or you have not asked anything yet."
          />
        }
        loading={
          <div className="flex flex-col gap-2">
            {Array.from({ length: 8 }, (_, index) => (
              <Skeleton key={index} className="h-10 w-full" />
            ))}
          </div>
        }
      >
        {(page) => {
          const { count, limit, offset } = page.meta
          return (
            <div className="flex flex-col gap-3">
              <Table>
                <caption className="sr-only">Your runs</caption>
                <TableHeader>
                  <TableRow>
                    <TableHead>Question</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Time</TableHead>
                    <TableHead>When</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {page.data.map((run) => {
                    return (
                      <TableRow key={run.id}>
                        <TableCell className="max-w-md">
                          <Link
                            to="/ask"
                            search={{ run: run.id }}
                            className="line-clamp-2 underline-offset-4 hover:underline"
                          >
                            {run.question}
                          </Link>
                          {run.edited && <Badge className="ml-2">edited</Badge>}
                        </TableCell>
                        <TableCell>
                          <RunStatusBadge status={run.status} />
                        </TableCell>
                        <TableCell>{formatDuration(run.latency_ms / 1000)}</TableCell>
                        <TableCell>{formatRelative(run.created_at)}</TableCell>
                        <TableCell>
                          <div className="flex gap-4">
                            <Link
                              to="/runs/$runId/replay"
                              params={{ runId: String(run.id) }}
                              className="underline-offset-4 hover:underline"
                            >
                              Replay
                            </Link>
                            <Link
                              to="/ask"
                              search={{ question: run.question }}
                              className="underline-offset-4 hover:underline"
                            >
                              Ask again
                            </Link>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
              <nav aria-label="Pages" className="flex items-center justify-between gap-3">
                <span className="text-small text-muted-foreground">
                  {formatNumber(offset + 1)} to {formatNumber(Math.min(offset + limit, count))} of{' '}
                  {formatNumber(count)}
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={ArrowLeft01Icon}
                    disabled={offset === 0}
                    onClick={() => {
                      change({ ...filters, offset: Math.max(0, offset - limit) || undefined })
                    }}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={ArrowRight01Icon}
                    iconPosition="end"
                    disabled={offset + limit >= count}
                    onClick={() => {
                      change({ ...filters, offset: offset + limit })
                    }}
                  >
                    Next
                  </Button>
                </div>
              </nav>
            </div>
          )
        }}
      </QueryBoundary>
    </div>
  )
}
