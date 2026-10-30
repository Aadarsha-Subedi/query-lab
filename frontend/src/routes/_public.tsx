import { createFileRoute, Outlet, redirect } from '@tanstack/react-router'

import { meQuery } from '@/features/auth/api'

/** Public pages (landing, login, signup, ...). Signed-in users go to the app. */
export const Route = createFileRoute('/_public')({
  beforeLoad: async ({ context }) => {
    const me = await context.queryClient.query({ ...meQuery, staleTime: 'static' })
    if (me) throw redirect({ to: '/app' })
  },
  component: Outlet,
})
