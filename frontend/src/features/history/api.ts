import { queryOptions } from '@tanstack/react-query'
import { z } from 'zod'

import { api } from '@/lib/api'
import type { Run } from '@/features/ask/types'

export const STATUSES = [
  'running',
  'awaiting_approval',
  'succeeded',
  'failed',
  'cancelled',
  'expired',
] as const
export const ORDERINGS = ['-created_at', 'created_at', '-latency_ms', 'latency_ms'] as const

/** The history filters. They live in the URL (validated here), so a reload keeps them. */
export const historySearchSchema = z.object({
  status: z.enum(STATUSES).optional(),
  q: z.string().optional(),
  ordering: z.enum(ORDERINGS).optional(),
  offset: z.number().int().nonnegative().optional(),
  workspace: z.union([z.literal('demo'), z.number().int().positive()]).optional(),
})
export type HistoryFilters = z.infer<typeof historySearchSchema>

export function historyPath(filters: HistoryFilters): string {
  const params = new URLSearchParams()
  if (filters.status) params.set('status', filters.status)
  if (filters.q) params.set('q', filters.q)
  if (filters.ordering) params.set('ordering', filters.ordering)
  if (filters.offset) params.set('offset', String(filters.offset))
  if (filters.workspace !== undefined) params.set('workspace', String(filters.workspace))
  const query = params.toString()
  return query ? `/api/agent/runs?${query}` : '/api/agent/runs'
}

/** GET /api/agent/runs with filters; the page size is the server's (meta.limit). */
export const historyQuery = (filters: HistoryFilters) =>
  queryOptions({
    queryKey: ['history', filters],
    queryFn: ({ signal }) => api.getPage<Run>(historyPath(filters), { signal }),
  })
