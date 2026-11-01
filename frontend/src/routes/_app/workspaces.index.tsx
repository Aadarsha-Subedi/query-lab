import { createFileRoute } from '@tanstack/react-router'

import { Heading } from '@/components/typography/Heading'
import { WorkspaceList } from '@/features/workspaces/WorkspaceList'

export const Route = createFileRoute('/_app/workspaces/')({
  component: WorkspacesPage,
})

function WorkspacesPage() {
  return (
    <main id="main" tabIndex={-1} className="flex flex-col gap-6 px-4 py-6">
      {/* The nav item names the page; the heading stays for screen readers and the tab title. */}
      <Heading level={1} className="sr-only">
        Workspaces
      </Heading>
      <WorkspaceList />
    </main>
  )
}
