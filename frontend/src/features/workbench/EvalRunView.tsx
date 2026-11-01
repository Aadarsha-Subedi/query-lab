import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Heading } from '@/components/typography/Heading'
import { Badge } from '@/components/ui/badge'
import { formatPercent } from '@/lib/format'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

import { evalRunDetailQuery, type EvalRunDetail } from './api'

const ALL = 'all'

function Detail({ run }: { run: EvalRunDetail }) {
  const [outcome, setOutcome] = useState(ALL)
  const outcomes = [...new Set(run.results.map((result) => result.outcome))]
  const shown = outcome === ALL ? run.results : run.results.filter((result) => result.outcome === outcome)
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-2">
        <Heading level={2}>
          Eval run #{run.id}: {formatPercent(run.accuracy)}
        </Heading>
        <Badge>{run.target}</Badge>
        <Badge>{run.runner}</Badge>
        <span className="font-mono text-small text-muted-foreground">{run.model}</span>
      </div>

      <section aria-label="By cluster" className="flex flex-col gap-2">
        <Heading level={3}>Accuracy by cluster</Heading>
        {run.by_cluster.length === 0 ? (
          <p className="text-body text-muted-foreground">This run has no clusters.</p>
        ) : (
          <Table>
            <caption className="sr-only">Accuracy by cluster</caption>
            <TableHeader>
              <TableRow>
                <TableHead>Cluster</TableHead>
                <TableHead>Correct</TableHead>
                <TableHead>Accuracy</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {run.by_cluster.map((cluster) => (
                <TableRow key={cluster.cluster_key}>
                  <TableCell className="font-mono">{cluster.cluster_key}</TableCell>
                  <TableCell>
                    {cluster.correct}/{cluster.total}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <div
                        className="h-1.5 w-24 overflow-hidden rounded-full bg-surface-muted"
                        aria-hidden="true"
                      >
                        <div className="h-full bg-primary" style={{ width: `${cluster.accuracy * 100}%` }} />
                      </div>
                      {formatPercent(cluster.accuracy)}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      <section aria-label="Cases" className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Heading level={3}>Cases</Heading>
          <label className="flex items-center gap-2 text-small">
            Outcome
            <select
              aria-label="Outcome"
              className="h-8 rounded-md border bg-surface px-2 text-small"
              value={outcome}
              onChange={(event) => {
                setOutcome(event.target.value)
              }}
            >
              <option value={ALL}>All</option>
              {outcomes.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
        </div>
        <Table>
          <caption className="sr-only">Case results</caption>
          <TableHeader>
            <TableRow>
              <TableHead>Question</TableHead>
              <TableHead>Outcome</TableHead>
              <TableHead>Reason</TableHead>
              <TableHead>Source</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {shown.map((result) => (
              <TableRow key={result.question_id}>
                <TableCell className="max-w-md">{result.question}</TableCell>
                <TableCell>
                  <Badge variant={result.outcome === 'correct' ? 'success' : 'danger'}>
                    {result.outcome}
                  </Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">{result.reason}</TableCell>
                <TableCell>
                  {result.trace_case_id !== null && (
                    <Link
                      to="/workbench/cases/$caseId"
                      params={{ caseId: String(result.trace_case_id) }}
                      className="underline-offset-4 hover:underline"
                    >
                      Case {result.trace_case_id}
                    </Link>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </section>
    </div>
  )
}

export function EvalRunView({ runId }: { runId: number }) {
  const query = useQuery(evalRunDetailQuery(runId))
  return (
    <QueryBoundary
      query={query}
      errorTitle="Couldn't load this eval run."
      loading={<Skeleton className="h-64 w-full" />}
    >
      {(run) => <Detail run={run} />}
    </QueryBoundary>
  )
}
