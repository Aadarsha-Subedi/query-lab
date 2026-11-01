import { ArrowLeft01Icon } from '@hugeicons/core-free-icons'
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { z } from 'zod'

import { Heading } from '@/components/typography/Heading'
import { Button } from '@/components/ui/button'
import { WorkspaceDetail } from '@/features/workspaces/WorkspaceDetail'

const searchSchema = z.object({
  tab: z.enum(['tables', 'relations', 'sql']).optional(),
  table: z.string().optional(),
})

export const Route = createFileRoute('/_app/workspaces/$id')({
  validateSearch: searchSchema,
  component: WorkspacePage,
})

function WorkspacePage() {
  const { id } = Route.useParams()
  const search = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const workspaceId = Number(id)
  return (
    <main id="main" tabIndex={-1} className="flex flex-col gap-6 px-4 py-6">
      <div className="flex items-center gap-3">
        <Button asChild variant="ghost" size="sm" icon={ArrowLeft01Icon}>
          <Link to="/workspaces">Workspaces</Link>
        </Button>
        <Heading level={1}>Edit workspace</Heading>
      </div>
      {Number.isInteger(workspaceId) && workspaceId > 0 ? (
        <WorkspaceDetail
          id={workspaceId}
          tab={search.tab ?? 'tables'}
          table={search.table}
          onChange={(next) => {
            void navigate({ search: next })
          }}
        />
      ) : (
        <p>That is not a workspace.</p>
      )}
    </main>
  )
}
