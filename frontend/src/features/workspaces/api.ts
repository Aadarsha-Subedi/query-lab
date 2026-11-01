import { queryOptions, type QueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { Schema } from '@/lib/api/types'

export type WorkspaceInfo = Schema<'WorkspaceOut'>
export type WorkspaceLimits = Schema<'LimitsOut'>
export type TableSpec = Schema<'WorkspaceTableOut'>
export type ColumnSpec = Schema<'WorkspaceColumnOut'>
export type NewTable = Schema<'TableIn'>
export type NewColumn = Schema<'ColumnIn'>
export type Relation = Schema<'RelationOut'>
export type NewRelation = Schema<'RelationIn'>
export type RowsPage = Schema<'RowsPageOut'>
export type SqlResult = Schema<'SqlOut'>

export { COLUMN_TYPES, ON_DELETE } from './contract'

const base = '/api/workspaces'
const table = (id: number, name: string) => `${base}/${id}/tables/${encodeURIComponent(name)}`

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

export const tablesQuery = (id: number) =>
  queryOptions({
    queryKey: ['workspace', id, 'tables'],
    queryFn: ({ signal }) => api.get<TableSpec[]>(`${base}/${id}/tables`, { signal }),
  })

export const relationsQuery = (id: number) =>
  queryOptions({
    queryKey: ['workspace', id, 'relations'],
    queryFn: ({ signal }) => api.get<Relation[]>(`${base}/${id}/relations`, { signal }),
  })

export type RowsParams = {
  limit?: number
  offset?: number
  orderBy?: string
  descending?: boolean
  filters?: string[]
}

export const rowsQuery = (id: number, name: string, params: RowsParams) =>
  queryOptions({
    queryKey: ['workspace', id, 'rows', name, params],
    queryFn: ({ signal }) => {
      const search = new URLSearchParams()
      if (params.limit !== undefined) search.set('limit', String(params.limit))
      if (params.offset) search.set('offset', String(params.offset))
      if (params.orderBy) search.set('order_by', params.orderBy)
      if (params.descending) search.set('descending', 'true')
      for (const filter of params.filters ?? []) search.append('filter', filter)
      const query = search.toString()
      return api.get<RowsPage>(`${table(id, name)}/rows${query ? `?${query}` : ''}`, { signal })
    },
  })

export const createWorkspace = (name: string) => api.post<WorkspaceInfo>(base, { name })
export const renameWorkspace = (id: number, name: string) =>
  api.patch<WorkspaceInfo>(`${base}/${id}`, { name })
export const deleteWorkspace = (id: number) => api.delete<null>(`${base}/${id}`)

export const createTable = (id: number, spec: NewTable) => api.post<TableSpec>(`${base}/${id}/tables`, spec)
export const patchTable = (id: number, name: string, patch: { name?: string; description?: string }) =>
  api.patch<TableSpec>(table(id, name), patch)
export const dropTable = (id: number, name: string) => api.delete<null>(table(id, name))

export const addColumn = (id: number, name: string, column: NewColumn) =>
  api.post<TableSpec>(`${table(id, name)}/columns`, column)
export const patchColumn = (
  id: number,
  name: string,
  column: string,
  patch: { name?: string; description?: string; nullable?: boolean; type?: string },
) => api.patch<TableSpec>(`${table(id, name)}/columns/${encodeURIComponent(column)}`, patch)
export const dropColumn = (id: number, name: string, column: string) =>
  api.delete<TableSpec>(`${table(id, name)}/columns/${encodeURIComponent(column)}`)
export const setPrimaryKey = (id: number, name: string, columns: string[]) =>
  api.put<TableSpec>(`${table(id, name)}/primary-key`, { columns })

export const addRelation = (id: number, relation: NewRelation) =>
  api.post<Relation>(`${base}/${id}/relations`, relation)
export const dropRelation = (id: number, name: string) =>
  api.delete<null>(`${base}/${id}/relations/${encodeURIComponent(name)}`)

export const insertRows = (id: number, name: string, rows: Record<string, unknown>[]) =>
  api.post<{ inserted: number; ids: number[] }>(`${table(id, name)}/rows`, { rows })
export const patchRow = (id: number, name: string, rowId: number, values: Record<string, unknown>) =>
  api.patch<{ row: Record<string, unknown> }>(`${table(id, name)}/rows/${rowId}`, { values })
export const deleteRow = (id: number, name: string, rowId: number) =>
  api.delete<{ deleted: number; cascaded: number }>(`${table(id, name)}/rows/${rowId}`)

export const runSql = (id: number, sql: string) => api.post<SqlResult>(`${base}/${id}/sql`, { sql })

/** After any change to a workspace: its tables, rows and schema panel, and the list (sizes) are stale. */
export function invalidateWorkspace(queryClient: QueryClient, id: number): Promise<unknown> {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: ['workspace', id] }),
    queryClient.invalidateQueries({ queryKey: ['schema', id] }),
    queryClient.invalidateQueries({ queryKey: ['workspaces'] }),
  ])
}
