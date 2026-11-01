import { queryOptions } from '@tanstack/react-query'

import { api } from '@/lib/api'

import type { Run, RunDetail, RunResult } from './types'

const runs = '/api/agent/runs'

/** GET /api/agent/runs/{id}: the run, its steps so far and (when paused) the `pending` proposal. */
export const runQuery = (id: number) =>
  queryOptions({
    queryKey: ['run', id],
    queryFn: ({ signal }) => api.get<RunDetail>(`${runs}/${id}`, { signal }),
  })

/** GET /api/agent/runs/{id}/result: runs the finished SQL again on the reader. */
export const resultQuery = (id: number) =>
  queryOptions({
    queryKey: ['run', id, 'result'],
    queryFn: ({ signal }) => api.get<RunResult>(`${runs}/${id}/result`, { signal }),
  })

export const createRun = (question: string, workspace?: number) =>
  api.post<Run>(runs, { question, workspace: workspace ?? null })

export const approveRun = (id: number) => api.post<Run>(`${runs}/${id}/approve`, {})
export const editRun = (id: number, sql: string) => api.post<Run>(`${runs}/${id}/edit`, { sql })
export const cancelRun = (id: number) => api.post<Run>(`${runs}/${id}/cancel`)

export type Vote = 'up' | 'down'
export const voteOnRun = (id: number, vote: Vote) => api.put<unknown>(`${runs}/${id}/feedback`, { vote })
export const clearVote = (id: number) => api.delete<unknown>(`${runs}/${id}/feedback`)
