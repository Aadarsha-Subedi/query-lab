import { createFileRoute } from '@tanstack/react-router'

import { PlaceholderPage } from '@/components/PlaceholderPage'
import { HealthPanel } from '@/features/health/HealthPanel'

export const Route = createFileRoute('/_app/app')({
  component: AppHome,
})

function AppHome() {
  const { me } = Route.useRouteContext()
  return (
    <PlaceholderPage
      title="Your workspaces"
      note={`Signed in as ${me.email}. The workspace list and the Olist demo arrive in step 0.10d.`}
    >
      <HealthPanel />
    </PlaceholderPage>
  )
}
