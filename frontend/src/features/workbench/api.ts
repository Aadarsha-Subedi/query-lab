import { queryOptions } from '@tanstack/react-query'
import { z } from 'zod'

import { api } from '@/lib/api'
import type { Schema } from '@/lib/api/types'

export type TraceRun = Schema<'RunOut'>
export type TraceDetail = Schema<'TraceDetailOut'>
export type Cluster = Schema<'ClusterOut'>
export type Case = Schema<'CaseOut'>
export type CaseDetail = Schema<'CaseDetailOut'>
export type EvalRun = Schema<'EvalRunOut'>
export type EvalRunDetail = Schema<'EvalRunDetailOut'>
export type Comparison = Schema<'ComparisonOut'>

const base = '/api/workbench'

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

// ── Filters live in the URL, so each has a schema the routes validate with ──

export const TRACE_STATUSES = [
  'running',
  'awaiting_approval',
  'succeeded',
  'failed',
  'cancelled',
  'expired',
] as const
export const traceFiltersSchema = z.object({
  status: z.enum(TRACE_STATUSES).optional(),
  q: z.string().optional(),
  feedback: z.enum(['up', 'down']).optional(),
  edited: z.boolean().optional(),
  offset: z.number().int().nonnegative().optional(),
})
export type TraceFilters = z.infer<typeof traceFiltersSchema>

export const CASE_STATUSES = ['candidate', 'drafted', 'approved', 'rejected'] as const
export const casesFiltersSchema = z.object({
  status: z.enum(CASE_STATUSES).optional(),
  cluster: z.string().optional(),
  offset: z.number().int().nonnegative().optional(),
})
export type CasesFilters = z.infer<typeof casesFiltersSchema>

export const evalFiltersSchema = z.object({
  target: z.string().optional(),
  runner: z.string().optional(),
  model: z.string().optional(),
  prompt_version: z.string().optional(),
  offset: z.number().int().nonnegative().optional(),
})
export type EvalFilters = z.infer<typeof evalFiltersSchema>

// ── Queries ──

export const traceRunsQuery = (filters: TraceFilters) =>
  queryOptions({
    queryKey: ['workbench', 'runs', filters],
    queryFn: ({ signal }) =>
      api.getPage<TraceRun>(
        `${base}/runs${query({
          status: filters.status,
          q: filters.q,
          feedback: filters.feedback,
          edited: filters.edited === undefined ? undefined : String(filters.edited),
          offset: filters.offset,
        })}`,
        { signal },
      ),
  })

export const traceDetailQuery = (id: number) =>
  queryOptions({
    queryKey: ['workbench', 'run', id],
    queryFn: ({ signal }) => api.get<TraceDetail>(`${base}/runs/${id}`, { signal }),
  })

export const clustersQuery = queryOptions({
  queryKey: ['workbench', 'clusters'],
  queryFn: ({ signal }) => api.get<Cluster[]>(`${base}/clusters`, { signal }),
})

export const casesQuery = (filters: CasesFilters) =>
  queryOptions({
    queryKey: ['workbench', 'cases', filters],
    queryFn: ({ signal }) =>
      api.getPage<Case>(
        `${base}/cases${query({ status: filters.status, cluster: filters.cluster, offset: filters.offset })}`,
        { signal },
      ),
  })

export const caseDetailQuery = (id: number) =>
  queryOptions({
    queryKey: ['workbench', 'case', id],
    queryFn: ({ signal }) => api.get<CaseDetail>(`${base}/cases/${id}`, { signal }),
  })

export const evalRunsQuery = (filters: EvalFilters) =>
  queryOptions({
    queryKey: ['workbench', 'eval-runs', filters],
    queryFn: ({ signal }) =>
      api.getPage<EvalRun>(
        `${base}/eval/runs${query({
          target: filters.target,
          runner: filters.runner,
          model: filters.model,
          prompt_version: filters.prompt_version,
          offset: filters.offset,
        })}`,
        { signal },
      ),
  })

export const evalRunDetailQuery = (id: number) =>
  queryOptions({
    queryKey: ['workbench', 'eval-run', id],
    queryFn: ({ signal }) => api.get<EvalRunDetail>(`${base}/eval/runs/${id}`, { signal }),
  })

export const compareQuery = (baseId: number, otherId: number) =>
  queryOptions({
    queryKey: ['workbench', 'compare', baseId, otherId],
    queryFn: ({ signal }) =>
      api.get<Comparison>(`${base}/eval/compare?base=${baseId}&other=${otherId}`, { signal }),
  })

// ── Review actions ──

export const draftCases = () => api.post<{ queued: boolean }>(`${base}/cases/draft`)
export const approveCase = (id: number, edits: { question?: string; sql?: string }) =>
  api.post<Case>(`${base}/cases/${id}/approve`, edits)
export const rejectCase = (id: number, reason: string) =>
  api.post<Case>(`${base}/cases/${id}/reject`, { reason })
export const markUnanswerable = (id: number, note: string) =>
  api.post<Case>(`${base}/cases/${id}/mark-unanswerable`, { note })
