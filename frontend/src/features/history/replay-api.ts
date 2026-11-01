import { queryOptions } from '@tanstack/react-query'

import type { RunDetail } from '@/features/ask/types'
import { api } from '@/lib/api'

/** GET /api/agent/runs/{id}/replay: the stored steps in order. */
export const replayQuery = (id: number) =>
  queryOptions({
    queryKey: ['run', id, 'replay'],
    queryFn: ({ signal }) => api.get<RunDetail>(`/api/agent/runs/${id}/replay`, { signal }),
  })
