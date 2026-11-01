import { queryOptions } from '@tanstack/react-query'

import { api } from '@/lib/api'
import { withWorkspace } from '@/lib/api/query'
import type { Schema } from '@/lib/api/types'

export type AgentLimits = Schema<'AgentLimitsOut'>

/** GET /api/agent/limits: what is left before the shared key's daily limit, and open runs and streams. */
export const limitsQuery = (workspace?: number) =>
  queryOptions({
    queryKey: ['agent-limits', workspace ?? null],
    queryFn: ({ signal }) => api.get<AgentLimits>(withWorkspace('/api/agent/limits', workspace), { signal }),
  })
