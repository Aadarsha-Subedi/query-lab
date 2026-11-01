import { queryOptions } from '@tanstack/react-query'

import { api } from '@/lib/api'
import { withWorkspace } from '@/lib/api/query'
import type { Schema } from '@/lib/api/types'

export type DatabaseSchema = Schema<'SchemaOut'>
export type TableInfo = Schema<'TableOut'>
export type ColumnInfo = Schema<'ColumnOut'>

/** GET /api/schema. The browser's HTTP cache handles ETag / If-None-Match. */
export const schemaQuery = (workspace?: number) =>
  queryOptions({
    queryKey: ['schema', workspace ?? null],
    queryFn: ({ signal }) => api.get<DatabaseSchema>(withWorkspace('/api/schema', workspace), { signal }),
  })

export type TableRows = Schema<'TableRowsOut'>

/** GET /api/schema/tables/{name}/rows: one read-only page of a table's data. */
export const tableRowsQuery = (name: string, workspace: number | undefined, offset: number) =>
  queryOptions({
    queryKey: ['schema', workspace ?? null, 'rows', name, offset],
    queryFn: ({ signal }) =>
      api.get<TableRows>(
        withWorkspace(`/api/schema/tables/${encodeURIComponent(name)}/rows?offset=${offset}`, workspace),
        { signal },
      ),
  })
