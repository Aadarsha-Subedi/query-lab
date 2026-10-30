import { createFileRoute, lazyRouteComponent, notFound } from '@tanstack/react-router'

/*
 * DEV-ONLY design system showcase. In production import.meta.env.DEV is
 * false, so the dynamic import below is dropped from the bundle and the route
 * answers "not found" (build.test.ts checks the page never ships).
 */
export const Route = createFileRoute('/design')({
  beforeLoad: () => {
    if (!import.meta.env.DEV) throw notFound()
  },
  component: import.meta.env.DEV
    ? lazyRouteComponent(() => import('@/features/design/DesignPage'), 'DesignPage')
    : () => null,
})
