import { queryOptions, type QueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { Schema } from '@/lib/api/types'

export type WorkspaceInfo = Schema<'WorkspaceOut'>
export type WorkspaceLimits = Schema<'LimitsOut'>
export type ImportJob = Schema<'ImportOut'>
export type ImportCreated = Schema<'ImportCreatedOut'>
export type SqlResult = Schema<'SqlOut'>

const base = '/api/workspaces'

export const workspacesQuery = queryOptions({
  queryKey: ['workspaces'],
  queryFn: ({ signal }) => api.get<WorkspaceInfo[]>(base, { signal }),
})

export const workspaceLimitsQuery = queryOptions({
  queryKey: ['workspaces', 'limits'],
  queryFn: ({ signal }) => api.get<WorkspaceLimits>(`${base}/limits`, { signal }),
})

export const workspaceQuery = (id: number) =>
  queryOptions({
    queryKey: ['workspace', id],
    queryFn: ({ signal }) => api.get<WorkspaceInfo>(`${base}/${id}`, { signal }),
  })

export const importsQuery = (id: number) =>
  queryOptions({
    queryKey: ['workspace', id, 'imports'],
    queryFn: ({ signal }) => api.get<ImportJob[]>(`${base}/${id}/imports`, { signal }),
  })

export const createWorkspace = (name: string) => api.post<WorkspaceInfo>(base, { name })
export const renameWorkspace = (id: number, name: string) =>
  api.patch<WorkspaceInfo>(`${base}/${id}`, { name })
export const deleteWorkspace = (id: number) => api.delete<null>(`${base}/${id}`)

/** Step 1: ask for an upload URL. `size` is the file's exact byte length. */
export const createImport = (id: number, file: { filename: string; size: number; replace: boolean }) =>
  api.post<ImportCreated>(`${base}/${id}/imports`, file)
/** Step 3: the file is in the bucket; queue the job. */
export const startImport = (id: number, job: number) =>
  api.post<ImportJob>(`${base}/${id}/imports/${job}/start`, {})
export const importStatus = (id: number, job: number) =>
  queryOptions({
    queryKey: ['workspace', id, 'imports', job],
    queryFn: ({ signal }) => api.get<ImportJob>(`${base}/${id}/imports/${job}`, { signal }),
  })

/**
 * Step 2: PUT the file straight to the bucket. XMLHttpRequest, because fetch cannot report upload
 * progress. The signed URL pins the exact length, so the body must be the file itself.
 */
export function uploadFile(url: string, file: File, onProgress: (fraction: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open('PUT', url)
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total)
    }
    request.onload = () => {
      if (request.status >= 200 && request.status < 300) resolve()
      else reject(new Error(`The upload was refused (${request.status}).`))
    }
    request.onerror = () => {
      reject(new Error('The upload failed. Check your connection and try again.'))
    }
    request.send(file)
  })
}

export const runSql = (id: number, sql: string) => api.post<SqlResult>(`${base}/${id}/sql`, { sql })

/** After an import: the workspace's tables, schema panel, sizes and list are stale. */
export function invalidateWorkspace(queryClient: QueryClient, id: number): Promise<unknown> {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: ['workspace', id] }),
    queryClient.invalidateQueries({ queryKey: ['schema', id] }),
    queryClient.invalidateQueries({ queryKey: ['workspaces'] }),
  ])
}
