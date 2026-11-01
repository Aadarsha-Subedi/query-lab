import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { initApi } from '@/lib/api'
import { createQueryClient } from '@/lib/query-client'
import { mockFetch, TEST_BASE_URL } from '@/test/http'

import { LimitsIndicator } from './LimitsIndicator'

const limits = (over: Record<string, unknown> = {}) => ({
  status: 200,
  body: {
    success: true,
    status_code: 200,
    message: '',
    meta: {},
    data: {
      default_key: { used: 3, allowed: 20, remaining: 17, resets_at: '2026-11-02T00:00:00Z' },
      has_own_key: false,
      streams: { open: 0, allowed: 5 },
      unfinished_runs: { count: 1, allowed: 3 },
      workspace_id: null,
      ...over,
    },
  },
})

function show() {
  initApi(TEST_BASE_URL)
  render(
    <QueryClientProvider client={createQueryClient(0)}>
      <LimitsIndicator />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('LimitsIndicator', () => {
  it('shows what is left and the detail on press', async () => {
    mockFetch({ '/api/agent/limits': () => limits() })
    show()
    const chip = await screen.findByRole('button', { name: 'Usage limits: 17 left today' })
    await userEvent.click(chip)
    expect(await screen.findByText('3 of 20')).toBeVisible()
    expect(screen.getByText('1 of 3')).toBeVisible()
  })

  it('warns when the daily limit is used up', async () => {
    mockFetch({
      '/api/agent/limits': () =>
        limits({ default_key: { used: 20, allowed: 20, remaining: 0, resets_at: '2026-11-02T00:00:00Z' } }),
    })
    show()
    expect(await screen.findByText('Daily limit reached')).toBeVisible()
  })

  it('says it has its own key', async () => {
    mockFetch({ '/api/agent/limits': () => limits({ has_own_key: true }) })
    show()
    expect(await screen.findByRole('button', { name: 'Usage limits: Own key' })).toBeVisible()
  })

  it('has an error state that refetches only itself, once, on press', async () => {
    let calls = 0
    const fetchMock = mockFetch({
      '/api/agent/limits': () => {
        calls += 1
        return calls === 1
          ? { status: 500, body: { success: false, message: 'x', code: 'internal_error' } }
          : limits()
      },
    })
    show()
    await userEvent.click(await screen.findByRole('button', { name: 'Limits unavailable' }))
    expect(await screen.findByRole('button', { name: /Usage limits/ })).toBeVisible()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
