import { createFileRoute, Link, Outlet } from '@tanstack/react-router'

import { Heading } from '@/components/typography/Heading'
import { HealthPanel } from '@/features/health/HealthPanel'
import { ApiError } from '@/lib/api'

/**
 * Staff only. The API enforces it (403 staff_only); this guard also keeps everyone else
 * from seeing a screen that could only show errors.
 */
export const Route = createFileRoute('/_app/workbench')({
  beforeLoad: ({ context }) => {
    if (!context.me.is_staff) {
      throw new ApiError({ status: 403, code: 'staff_only', message: 'Staff only.' })
    }
  },
  component: WorkbenchLayout,
})

const LINKS = [
  { to: '/workbench/runs', label: 'Traces' },
  { to: '/workbench/cases', label: 'Cases' },
  { to: '/workbench/evals', label: 'Evals' },
] as const

function WorkbenchLayout() {
  return (
    <main id="main" tabIndex={-1} className="flex flex-col gap-4 px-4 py-6">
      <Heading level={1}>Workbench</Heading>
      <nav aria-label="Workbench" className="flex gap-1 border-b">
        {LINKS.map((link) => (
          <Link
            key={link.to}
            to={link.to}
            className="-mb-px border-b-2 border-transparent px-3 py-2 text-body font-medium text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
            activeProps={{ className: 'border-primary text-foreground' }}
          >
            {link.label}
          </Link>
        ))}
      </nav>
      <Outlet />
      <HealthPanel />
    </main>
  )
}
