import { ClipboardIcon, SparklesIcon } from '@hugeicons/core-free-icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/data-state'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { toast } from '@/components/ui/toast-api'
import { errorText } from '@/lib/api/error-text'
import { formatRelative } from '@/lib/format'

import { CASE_STATUSES, casesQuery, clustersQuery, draftCases, type CasesFilters } from './api'
import { Pager } from './Pager'

const ANY = 'any'
const STATUS_VARIANT = {
  candidate: 'neutral',
  drafted: 'warning',
  approved: 'success',
  rejected: 'danger',
} as const

function Clusters({ filters, onPick }: { filters: CasesFilters; onPick: (key: string | undefined) => void }) {
  const query = useQuery(clustersQuery)
  return (
    <QueryBoundary
      query={query}
      errorTitle="Couldn't load the clusters."
      isEmpty={(items) => items.length === 0}
      empty={
        <p className="text-body text-muted-foreground">
          No clusters yet. Build the candidates first (see FLOW.md).
        </p>
      }
      loading={<Skeleton className="h-24 w-full" />}
    >
      {(items) => (
        <ul aria-label="Clusters" className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {items.map((cluster) => (
            <li key={cluster.key}>
              <button
                type="button"
                aria-pressed={filters.cluster === cluster.key}
                onClick={() => {
                  onPick(filters.cluster === cluster.key ? undefined : cluster.key)
                }}
                className="flex h-full w-full flex-col gap-1 rounded-md border bg-surface p-3 text-left outline-none hover:bg-surface-muted focus-visible:ring-2 focus-visible:ring-ring aria-pressed:border-primary"
              >
                <span className="text-body font-medium">{cluster.label}</span>
                <span className="text-small text-muted-foreground">{cluster.size} traces</span>
                <span className="flex flex-wrap gap-1">
                  {Object.entries(cluster.status_counts).map(([status, count]) => (
                    <Badge key={status}>
                      {status} {String(count)}
                    </Badge>
                  ))}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </QueryBoundary>
  )
}

export function Cases({ filters }: { filters: CasesFilters }) {
  const navigate = useNavigate({ from: '/workbench/cases/' })
  const queryClient = useQueryClient()
  const query = useQuery(casesQuery(filters))
  const change = (next: CasesFilters) => {
    void navigate({ search: next })
  }
  const draft = useMutation({
    mutationFn: draftCases,
    onSuccess: async () => {
      toast.success('Drafting started', {
        description: 'It runs in the background. Reload this page in a minute.',
      })
      await queryClient.invalidateQueries({ queryKey: ['workbench', 'cases'] })
    },
  })

  return (
    <div className="flex flex-col gap-5">
      <Clusters
        filters={filters}
        onPick={(cluster) => {
          change({ ...filters, cluster, offset: undefined })
        }}
      />
      <div className="flex flex-wrap items-center gap-3">
        <div className="w-44">
          <Select
            value={filters.status ?? ANY}
            onValueChange={(value) => {
              change({
                ...filters,
                status: value === ANY ? undefined : (value as (typeof CASE_STATUSES)[number]),
                offset: undefined,
              })
            }}
          >
            <SelectTrigger aria-label="Case status" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any status</SelectItem>
              {CASE_STATUSES.map((status) => (
                <SelectItem key={status} value={status}>
                  {status}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button
          icon={SparklesIcon}
          variant="secondary"
          loading={draft.isPending}
          onClick={() => {
            draft.mutate()
          }}
        >
          Draft a batch
        </Button>
        {draft.isError && (
          <span role="alert" className="text-small text-danger-foreground">
            {errorText(draft.error).message} {errorText(draft.error).hint}
          </span>
        )}
      </div>
      <QueryBoundary
        query={query}
        errorTitle="Couldn't load the cases."
        isEmpty={(page) => page.data.length === 0}
        empty={
          <EmptyState icon={ClipboardIcon} title="No cases" description="No case matches these filters." />
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
              <caption className="sr-only">Cases</caption>
              <TableHeader>
                <TableRow>
                  <TableHead>Question</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Why picked</TableHead>
                  <TableHead>When</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {page.data.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="max-w-md">
                      <Link
                        to="/workbench/cases/$caseId"
                        params={{ caseId: String(item.id) }}
                        className="line-clamp-2 underline-offset-4 hover:underline"
                      >
                        {item.question}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge variant={STATUS_VARIANT[item.status as keyof typeof STATUS_VARIANT]}>
                        {item.status}
                      </Badge>
                      {item.draft_error && (
                        <Badge variant="danger" className="ml-1">
                          draft failed
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{item.reasons.join(', ')}</TableCell>
                    <TableCell>{formatRelative(item.created_at)}</TableCell>
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
