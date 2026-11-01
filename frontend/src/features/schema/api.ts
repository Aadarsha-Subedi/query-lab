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

/** GET /api/schema/tables/{name}; an unknown name answers 404 table_not_found. */
export const tableQuery = (name: string, workspace?: number) =>
  queryOptions({
    queryKey: ['schema', workspace ?? null, 'table', name],
    queryFn: ({ signal }) =>
      api.get<TableInfo>(withWorkspace(`/api/schema/tables/${encodeURIComponent(name)}`, workspace), {
        signal,
      }),
  })
