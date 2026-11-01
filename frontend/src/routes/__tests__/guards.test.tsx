import { QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { render, screen } from '@testing-library/react'

import { initApi } from '@/lib/api'
import { createQueryClient } from '@/lib/query-client'
import { createAppRouter } from '@/router'
import { mockFetch, signedIn, signedOut, TEST_BASE_URL } from '@/test/http'

const STALE_TIME_MS = 0

async function openAt(path: string) {
  initApi(TEST_BASE_URL)
  const queryClient = createQueryClient(STALE_TIME_MS)
  const router = createAppRouter(queryClient, createMemoryHistory({ initialEntries: [path] }))
  await router.load()
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('route guards', () => {
  it('sends a signed-in user from a public page to /app', async () => {
    mockFetch({ '/api/me': signedIn, '/api/health': () => ({ status: 200, body: {} }) })
    const router = await openAt('/login')
    expect(router.state.location.pathname).toBe('/app')
    expect(await screen.findByRole('heading', { name: 'Ask your data' })).toBeInTheDocument()
  })

  it('sends a signed-out visitor from the app to the landing page', async () => {
    mockFetch({ '/api/me': signedOut })
    const router = await openAt('/app')
    expect(router.state.location.pathname).toBe('/')
  })

  it('lets a signed-out visitor see public pages', async () => {
    mockFetch({ '/api/me': signedOut })
    const router = await openAt('/login')
    expect(router.state.location.pathname).toBe('/login')
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })
})
