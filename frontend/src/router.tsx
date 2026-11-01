import type { QueryClient } from '@tanstack/react-query'
import { createRouter } from '@tanstack/react-router'

import { NotFoundPage, RouteErrorPage } from '@/components/RouteStatus'
import { routeTree } from '@/routeTree.gen'

export type RouterContext = { queryClient: QueryClient }

export function createAppRouter(
  queryClient: QueryClient,
  history?: Parameters<typeof createRouter>[0]['history'],
) {
  return createRouter({
    routeTree,
    context: { queryClient },
    history,
    defaultPreload: false,
    defaultNotFoundComponent: NotFoundPage,
    defaultErrorComponent: RouteErrorPage,
  })
}

declare module '@tanstack/react-router' {
  interface Register {
    router: ReturnType<typeof createAppRouter>
  }
}
