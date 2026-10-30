import { queryOptions } from '@tanstack/react-query'

import { api } from '@/lib/api'

export type CheckStatus = 'ok' | 'fail'

export type Health = {
  status: 'ok' | 'degraded'
  app_db: CheckStatus
  data_db: CheckStatus
  data_reader: CheckStatus
  redis: CheckStatus
  worker: CheckStatus
}

const DEGRADED = 503

/** GET /api/health. A 503 still carries the per-check results, so it is data. */
export const healthQuery = queryOptions({
  queryKey: ['health'],
  queryFn: ({ signal }) =>
    api.get<Health>('/api/health', { signal, shape: 'raw', acceptStatuses: [DEGRADED] }),
})
