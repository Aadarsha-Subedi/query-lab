import { createFileRoute, redirect } from '@tanstack/react-router'

import { AppShell } from '@/components/AppShell'
import { meQuery } from '@/features/auth/api'

/** The signed-in app. Signed-out visitors go to the landing page. */
export const Route = createFileRoute('/_app')({
  beforeLoad: async ({ context }) => {
    const me = await context.queryClient.query({ ...meQuery, staleTime: 'static' })
    if (!me) throw redirect({ to: '/' })
    return { me }
  },
  component: Shell,
})

function Shell() {
  const { me } = Route.useRouteContext()
  return <AppShell user={me} />
}
