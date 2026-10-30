import { QueryClient } from '@tanstack/react-query'

/*
 * Server state lives here (TanStack Query). Rules from design-system.md
 * section 13: nothing retries automatically, whatever the status code, and
 * nothing refetches on window focus or reconnect. The user retries a
 * component's data with its Try again button, or reloads the page.
 */
export function createQueryClient(staleTimeMs: number): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
        staleTime: staleTimeMs,
      },
      mutations: { retry: false },
    },
  })
}
