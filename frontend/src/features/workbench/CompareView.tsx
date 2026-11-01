import { useQuery } from '@tanstack/react-query'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Heading } from '@/components/typography/Heading'
import { Badge } from '@/components/ui/badge'
import { formatPercent } from '@/lib/format'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ApiError } from '@/lib/api'
import { describeError } from '@/lib/api/errors'

import { compareQuery, type Comparison } from './api'

function signed(points: number): string {
  return `${points > 0 ? '+' : ''}${points.toFixed(1)} points`
}

function Detail({ comparison }: { comparison: Comparison }) {
  const worse = comparison.flips.filter((flip) => flip.direction === 'to_wrong')
  const better = comparison.flips.filter((flip) => flip.direction !== 'to_wrong')
  return (
    <div className="flex flex-col gap-5">
      <Heading level={2}>
        Run #{comparison.base.id} to #{comparison.other.id}: {signed(comparison.diff_points)}
      </Heading>
      <p className="text-body text-muted-foreground">
        {formatPercent(comparison.base_accuracy)} to {formatPercent(comparison.other_accuracy)} on{' '}
        {comparison.shared} shared cases
        {comparison.only_in_base + comparison.only_in_other > 0 &&
          ` (${comparison.only_in_base} only in the first, ${comparison.only_in_other} only in the second)`}
        .
      </p>
      {(
        [
          ['Got worse', worse, 'danger'],
          ['Got better', better, 'success'],
        ] as const
      ).map(([title, flips, variant]) => (
        <section key={title} aria-label={title} className="flex flex-col gap-2">
          <Heading level={3}>
            {title} ({flips.length})
          </Heading>
          {flips.length === 0 ? (
            <p className="text-body text-muted-foreground">None.</p>
          ) : (
            <Table>
              <caption className="sr-only">{title}</caption>
              <TableHeader>
                <TableRow>
                  <TableHead>Question</TableHead>
                  <TableHead>Before</TableHead>
                  <TableHead>After</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {flips.map((flip) => (
                  <TableRow key={flip.question_id}>
                    <TableCell className="max-w-md">{flip.question}</TableCell>
                    <TableCell>
                      <Badge>{flip.base_outcome}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={variant}>{flip.other_outcome}</Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </section>
      ))}
      <section aria-label="By cluster" className="flex flex-col gap-2">
        <Heading level={3}>By cluster</Heading>
        <Table>
          <caption className="sr-only">Difference by cluster</caption>
          <TableHeader>
            <TableRow>
              <TableHead>Cluster</TableHead>
              <TableHead>Before</TableHead>
              <TableHead>After</TableHead>
              <TableHead>Difference</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {comparison.clusters.map((cluster) => (
              <TableRow key={cluster.cluster_key}>
                <TableCell className="font-mono">{cluster.cluster_key}</TableCell>
                <TableCell>
                  {cluster.base_correct}/{cluster.shared}
                </TableCell>
                <TableCell>
                  {cluster.other_correct}/{cluster.shared}
                </TableCell>
                <TableCell>{signed(cluster.diff_points)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </section>
    </div>
  )
}

export function CompareView({ base, other }: { base: number; other: number }) {
  const query = useQuery(compareQuery(base, other))
  const notComparable = query.error instanceof ApiError && query.error.code === 'eval_runs_not_comparable'
  return (
    <QueryBoundary
      query={query}
      errorTitle={
        notComparable ? describeError('eval_runs_not_comparable', '').message : "Couldn't compare these runs."
      }
      loading={<Skeleton className="h-64 w-full" />}
    >
      {(comparison) => <Detail comparison={comparison} />}
    </QueryBoundary>
  )
}
