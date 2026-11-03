import { createFileRoute, redirect } from '@tanstack/react-router'
import { z } from 'zod'

const searchSchema = z.object({
  tab: z.enum(['tables', 'relations', 'sql']).optional(), // old links
  table: z.string().optional(),
})

/**
 * The editor used to live here. It is now part of the Ask page (Schema, Import and Query tabs), so an old link lands on the same workspace there.
 */
export const Route = createFileRoute('/_app/workspaces/$id')({
  validateSearch: searchSchema,
  beforeLoad: ({ params, search }) => {
    const workspace = Number(params.id)
    if (!Number.isInteger(workspace) || workspace <= 0) throw redirect({ to: '/ask' })
    throw redirect({
      to: '/ask',
      search: { workspace, tab: search.tab === 'sql' ? 'sql' : 'schema', table: search.table },
    })
  },
})
