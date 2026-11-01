import { ChartLineData01Icon } from '@hugeicons/core-free-icons'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/data-state'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatDateTime, formatPercent } from '@/lib/format'

import { evalRunsQuery, type EvalFilters } from './api'
import { Pager } from './Pager'

function FilterBox({ filters, onChange }: { filters: EvalFilters; onChange: (next: EvalFilters) => void }) {
  const [model, setModel] = useState(filters.model ?? '')
  const [target, setTarget] = useState(filters.target ?? '')
  return (
    <form
      className="flex flex-wrap items-end gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        onChange({
          ...filters,
          model: model.trim() || undefined,
          target: target.trim() || undefined,
          offset: undefined,
        })
      }}
    >
      <Input
        className="w-44"
        aria-label="Target"
        placeholder="Target (e.g. traces)"
        value={target}
        onChange={(event) => {
          setTarget(event.target.value)
        }}
      />
      <Input
        className="w-56"
        aria-label="Model"
        placeholder="Model"
        value={model}
        onChange={(event) => {
          setModel(event.target.value)
        }}
      />
      <Button type="submit" variant="secondary" icon={ChartLineData01Icon}>
        Apply
      </Button>
    </form>
  )
}

/** Every eval run with its accuracy. Pick two to compare. */
export function Evals({ filters }: { filters: EvalFilters }) {
  const navigate = useNavigate({ from: '/workbench/evals/' })
  const query = useQuery(evalRunsQuery(filters))
  const [picked, setPicked] = useState<number[]>([])
  const change = (next: EvalFilters) => {
    void navigate({ search: next })
  }
  const toggle = (id: number) => {
    setPicked((previous) =>
      previous.includes(id) ? previous.filter((item) => item !== id) : [...previous.slice(-1), id],
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <FilterBox key={`${filters.model ?? ''}|${filters.target ?? ''}`} filters={filters} onChange={change} />
      {picked.length === 2 && (
        <div>
          <Button asChild icon={ChartLineData01Icon} size="sm">
            <Link
              to="/workbench/evals/compare"
              search={{ base: picked[0] as number, other: picked[1] as number }}
            >
              Compare the two picked runs
            </Link>
          </Button>
        </div>
      )}
      <QueryBoundary
        query={query}
        errorTitle="Couldn't load the eval runs."
        isEmpty={(page) => page.data.length === 0}
        empty={
          <EmptyState
            icon={ChartLineData01Icon}
            title="No eval runs"
            description="Run an eval with `make eval` and it shows up here."
          />
        }
        loading={
          <div className="flex flex-col gap-2">
            {Array.from({ length: 6 }, (_, index) => (
              <Skeleton key={index} className="h-10 w-full" />
            ))}
          </div>
        }
      >
        {(page) => (
          <div className="flex flex-col gap-3">
            <Table>
              <caption className="sr-only">Eval runs</caption>
              <TableHeader>
                <TableRow>
                  <TableHead>Pick</TableHead>
                  <TableHead>Run</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead>Accuracy</TableHead>
                  <TableHead>Cost per question</TableHead>
                  <TableHead>Finished</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {page.data.map((run) => (
                  <TableRow key={run.id}>
                    <TableCell>
                      <input
                        type="checkbox"
                        aria-label={`Pick run ${run.id} to compare`}
                        checked={picked.includes(run.id)}
                        onChange={() => {
                          toggle(run.id)
                        }}
                      />
                    </TableCell>
                    <TableCell>
                      <Link
                        to="/workbench/evals/$runId"
                        params={{ runId: String(run.id) }}
                        className="underline-offset-4 hover:underline"
                      >
                        #{run.id}
                      </Link>
                    </TableCell>
                    <TableCell>
                      {run.target} · {run.runner}
                    </TableCell>
                    <TableCell className="font-mono">{run.model}</TableCell>
                    <TableCell>
                      {formatPercent(run.accuracy)} ({run.correct_count}/{run.question_count})
                    </TableCell>
                    <TableCell>
                      {run.cost_per_question_usd === null
                        ? 'n/a'
                        : `$${run.cost_per_question_usd.toFixed(4)}`}
                    </TableCell>
                    <TableCell>{run.finished_at ? formatDateTime(run.finished_at) : run.status}</TableCell>
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
