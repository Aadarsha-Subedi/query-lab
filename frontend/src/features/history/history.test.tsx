import { QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { initApi } from '@/lib/api'
import { createQueryClient } from '@/lib/query-client'
import { createAppRouter } from '@/router'
import { jsonResponse, signedIn, TEST_BASE_URL } from '@/test/http'

const page = (data: unknown[], meta: Record<string, number>) => ({
  status: 200,
  body: { success: true, status_code: 200, message: '', data, meta },
})
const runRow = (id: number, over: Record<string, unknown> = {}) => ({
  id,
  question: `Question ${id}`,
  status: 'succeeded',
  latency_ms: 4200,
  created_at: '2026-11-01T00:00:00Z',
  edited: false,
  ...over,
})
const stepRow = (index: number, kind: string) => ({
  index,
  kind,
  tool_name: '',
  input: index === 1 ? { sql: 'select 1' } : {},
  output: `output ${index}`,
  status: 'ok',
  error_code: '',
  input_tokens: 0,
  output_tokens: 0,
  latency_ms: 100,
  actor: 'agent',
  created_at: '2026-11-01T00:00:00Z',
})

function serve(handler: (url: URL) => { status: number; body?: unknown }) {
  const urls: URL[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn<typeof fetch>((input) => {
      const url = new URL(input instanceof Request ? input.url : input.toString())
      urls.push(url)
      if (url.pathname === '/api/me') return Promise.resolve(jsonResponse(signedIn()))
      if (url.pathname === '/api/agent/limits')
        return Promise.resolve(
          jsonResponse({ status: 500, body: { success: false, message: 'x', code: 'internal_error' } }),
        )
      return Promise.resolve(jsonResponse(handler(url)))
    }),
  )
  return urls
}

async function openAt(path: string) {
  initApi(TEST_BASE_URL)
  const queryClient = createQueryClient(0)
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

describe('history', () => {
  it('lists runs with links to the run and its replay', async () => {
    serve(() =>
      page([runRow(1), runRow(2, { status: 'failed', edited: true })], { count: 2, limit: 20, offset: 0 }),
    )
    await openAt('/history')
    const table = await screen.findByRole('table', { name: 'Your runs' })
    expect(within(table).getByRole('link', { name: 'Question 1' })).toHaveAttribute('href', '/ask?run=1')
    expect(within(table).getAllByRole('link', { name: 'Replay' })[0]).toHaveAttribute(
      'href',
      '/runs/1/replay',
    )
    expect(within(table).getByText('Failed')).toBeVisible()
    expect(within(table).getByText('edited')).toBeVisible()
  })

  it('reads its filters from the URL and sends them to the API', async () => {
    const urls = serve(() => page([runRow(3)], { count: 1, limit: 20, offset: 0 }))
    await openAt('/history?status=failed&q=orders&ordering=-latency_ms')
    await screen.findByRole('table', { name: 'Your runs' })
    const call = urls.find((url) => url.pathname === '/api/agent/runs')
    expect(call?.searchParams.get('status')).toBe('failed')
    expect(call?.searchParams.get('q')).toBe('orders')
    expect(call?.searchParams.get('ordering')).toBe('-latency_ms')
  })

  it('searching writes the term to the URL and pages with offset', async () => {
    const urls = serve((url) =>
      page([runRow(Number(url.searchParams.get('offset') ?? 0) + 1)], {
        count: 40,
        limit: 20,
        offset: Number(url.searchParams.get('offset') ?? 0),
      }),
    )
    const router = await openAt('/history')
    await screen.findByRole('table', { name: 'Your runs' })
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search questions' }), 'revenue')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => {
      expect(router.state.location.search).toMatchObject({ q: 'revenue' })
    })
    await userEvent.click(await screen.findByRole('button', { name: 'Next' }))
    await waitFor(() => {
      expect(urls.some((url) => url.searchParams.get('offset') === '20')).toBe(true)
    })
    expect(await screen.findByRole('link', { name: 'Question 21' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
  })

  it('shows the empty state', async () => {
    serve(() => page([], { count: 0, limit: 20, offset: 0 }))
    await openAt('/history')
    expect(await screen.findByText('No runs found')).toBeVisible()
  })

  it('shows its own error with Try again', async () => {
    let calls = 0
    serve(() => {
      calls += 1
      return calls === 1
        ? { status: 500, body: { success: false, message: 'Boom.', code: 'internal_error' } }
        : page([runRow(1)], { count: 1, limit: 20, offset: 0 })
    })
    await openAt('/history')
    expect(await screen.findByText("Couldn't load your history.")).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(await screen.findByRole('link', { name: 'Question 1' })).toBeVisible()
  })
})

describe('replay', () => {
  it('steps through the stored trace', async () => {
    serve(() => ({
      status: 200,
      body: {
        success: true,
        status_code: 200,
        message: '',
        meta: {},
        data: {
          id: 4,
          question: 'How many?',
          status: 'succeeded',
          created_at: '2026-11-01T00:00:00Z',
          final_sql: 'select 1',
          steps: [stepRow(0, 'plan'), stepRow(1, 'execute')],
        },
      },
    }))
    await openAt('/runs/4/replay')
    expect(await screen.findByText('Step 1 of 2')).toBeVisible()
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: 'Next step' }))
    expect(screen.getByText('Step 2 of 2')).toBeVisible()
    expect(screen.getByRole('region', { name: 'Final SQL' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Next step' })).toBeDisabled()
  })

  it('says so when the run is not yours', async () => {
    serve(() => ({
      status: 404,
      body: { success: false, status_code: 404, message: 'No such run.', code: 'run_not_found', errors: [] },
    }))
    await openAt('/runs/99/replay')
    expect(await screen.findByText("Couldn't load this replay.")).toBeVisible()
  })
})
