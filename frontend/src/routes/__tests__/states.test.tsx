// design-system.md section 13: every screen that fetches shows a loading box while it waits and
// an error box with its own Try again when it fails, and neither retries by itself.
import { QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { cleanup, render, screen } from '@testing-library/react'

import { initApi } from '@/lib/api'
import { createQueryClient } from '@/lib/query-client'
import { createAppRouter } from '@/router'
import { jsonResponse, STAFF, TEST_BASE_URL } from '@/test/http'

const SCREENS = [
  '/history',
  '/workspaces',
  '/settings',
  '/ask?run=5',
  '/ask?tab=schema',
  '/runs/5/replay',
  '/workspaces/7',
  '/workbench/runs',
  '/workbench/runs/5',
  '/workbench/cases',
  '/workbench/cases/5',
  '/workbench/evals',
  '/workbench/evals/5',
  '/workbench/evals/compare?base=1&other=2',
]

const meAnswer = () =>
  jsonResponse({ status: 200, body: { success: true, status_code: 200, message: '', meta: {}, data: STAFF } })

/** `mode` decides what every call except /api/me gets: no answer yet, or a server error. */
function stubFetch(mode: 'pending' | 'error') {
  const fetchMock = vi.fn<typeof fetch>((input) => {
    const url = new URL(input instanceof Request ? input.url : input.toString())
    if (url.pathname === '/api/me') return Promise.resolve(meAnswer())
    if (mode === 'pending') return new Promise<Response>(() => undefined)
    return Promise.resolve(
      jsonResponse({
        status: 500,
        body: { success: false, message: 'Boom.', code: 'internal_error', errors: [] },
      }),
    )
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function open(path: string) {
  initApi(TEST_BASE_URL)
  const queryClient = createQueryClient(0)
  const router = createAppRouter(queryClient, createMemoryHistory({ initialEntries: [path] }))
  await router.load()
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe.each(SCREENS)('%s', (path) => {
  it('shows a loading box while its data is on the way', async () => {
    stubFetch('pending')
    await open(path)
    expect(
      await screen.findAllByText('', { selector: '[aria-busy="true"], [data-slot="skeleton"]' }),
    ).not.toHaveLength(0)
  })

  it('shows an error with its own Try again, and does not retry by itself', async () => {
    const fetchMock = stubFetch('error')
    await open(path)
    const retry = await screen.findAllByRole('button', { name: /try again/i })
    expect(retry.length).toBeGreaterThan(0)
    const before = fetchMock.mock.calls.length
    await new Promise((resolve) => setTimeout(resolve, 150))
    expect(fetchMock.mock.calls.length).toBe(before)
  })
})
