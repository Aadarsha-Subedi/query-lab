import { QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { cleanup, render, screen } from '@testing-library/react'

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
  it('sends a signed-in user from a public page to Ask', async () => {
    mockFetch({ '/api/me': signedIn, '/api/health': () => ({ status: 200, body: {} }) })
    const router = await openAt('/login')
    expect(router.state.location.pathname).toBe('/ask')
    expect(await screen.findByRole('heading', { name: 'Ask' })).toBeInTheDocument()
  })

  it('sends a signed-out visitor from the app to the landing page', async () => {
    mockFetch({ '/api/me': signedOut })
    const router = await openAt('/ask')
    expect(router.state.location.pathname).toBe('/')
  })

  it('lets a signed-out visitor see public pages', async () => {
    mockFetch({ '/api/me': signedOut })
    const router = await openAt('/login')
    expect(router.state.location.pathname).toBe('/login')
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it.each([
    ['/privacy', 'Privacy Policy'],
    ['/terms', 'Terms'],
  ])('keeps %s open signed in and signed out', async (path, title) => {
    mockFetch({ '/api/me': signedOut })
    const signedOutRouter = await openAt(path)
    expect(signedOutRouter.state.location.pathname).toBe(path)
    expect(await screen.findByRole('heading', { level: 1, name: title })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
    cleanup()

    mockFetch({ '/api/me': signedIn })
    const signedInRouter = await openAt(path)
    expect(signedInRouter.state.location.pathname).toBe(path)
    expect(await screen.findByRole('heading', { level: 1, name: title })).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: 'Open the app' })).toHaveAttribute('href', '/ask')
  })
})
