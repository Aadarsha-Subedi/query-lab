import { createFileRoute, Outlet } from '@tanstack/react-router'

import { SiteChrome } from '@/features/landing/SiteChrome'

/** Pages for everyone (Privacy, Terms). No guard: signed in or out, they stay here. */
export const Route = createFileRoute('/_site')({
  component: () => (
    <SiteChrome>
      <Outlet />
    </SiteChrome>
  ),
})
