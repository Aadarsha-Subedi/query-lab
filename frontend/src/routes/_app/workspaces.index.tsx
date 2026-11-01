import { createFileRoute } from '@tanstack/react-router'

import { Heading } from '@/components/typography/Heading'
import { WorkspaceList } from '@/features/workspaces/WorkspaceList'

export const Route = createFileRoute('/_app/workspaces/')({
  component: WorkspacesPage,
})

function WorkspacesPage() {
  return (
    <main className="flex flex-col gap-6 px-4 py-6">
      <Heading level={1}>Workspaces</Heading>
      <WorkspaceList />
    </main>
  )
}
