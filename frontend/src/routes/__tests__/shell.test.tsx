import { QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { initApi } from '@/lib/api'
import { createQueryClient } from '@/lib/query-client'
import { createAppRouter } from '@/router'
import { jsonResponse, mockFetch, signedIn, signedOut, TEST_BASE_URL } from '@/test/http'

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
  document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
})

describe('sign-in page', () => {
  it('has a real form per provider that posts to allauth with the CSRF token', async () => {
    document.cookie = 'csrftoken=tok123'
    mockFetch({ '/api/me': signedOut })
    await openAt('/login')
    for (const [label, provider] of [
      ['Continue with Google', 'google'],
      ['Continue with GitHub', 'github'],
    ] as const) {
      const form = screen.getByRole('button', { name: label }).closest('form')
      expect(form).toHaveAttribute('method', 'post')
      expect(form).toHaveAttribute('action', `${TEST_BASE_URL}/_allauth/browser/v1/auth/provider/redirect`)
      const field = (name: string) => form?.querySelector<HTMLInputElement>(`input[name="${name}"]`)?.value
      expect(field('provider')).toBe(provider)
      expect(field('process')).toBe('login')
      expect(field('csrfmiddlewaretoken')).toBe('tok123')
      expect(field('callback_url')).toMatch(/\/auth\/callback$/)
    }
  })

  it('says so when a sign-in did not finish', async () => {
    mockFetch({ '/api/me': signedOut })
    await openAt('/auth/callback')
    expect(await screen.findByRole('heading', { name: 'Sign-in did not finish' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Try signing in again' })).toHaveAttribute('href', '/login')
  })
})

describe('landing page', () => {
  it('explains the product and links to sign-in', async () => {
    mockFetch({ '/api/me': signedOut })
    await openAt('/')
    expect(await screen.findByRole('heading', { name: 'How it works' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sign in to start' })).toHaveAttribute('href', '/login')
    expect(screen.getByRole('link', { name: 'CC BY-NC-SA 4.0' })).toBeInTheDocument()
  })
})

describe('app shell', () => {
  it('shows the nav and account menu, and signs out to the landing page', async () => {
    const fetchMock = vi.fn<typeof fetch>((input, init) => {
      const url = new URL(input instanceof Request ? input.url : input.toString())
      if (url.pathname === '/api/me') return Promise.resolve(jsonResponse(signedIn()))
      if (url.pathname === '/api/health') return Promise.resolve(jsonResponse({ status: 200, body: {} }))
      if (url.pathname === '/api/agent/limits')
        return Promise.resolve(
          jsonResponse({ status: 500, body: { success: false, message: 'x', code: 'internal_error' } }),
        )
      if (url.pathname === '/_allauth/browser/v1/auth/session' && init?.method === 'DELETE')
        return Promise.resolve(jsonResponse({ status: 401, body: { status: 401, data: { flows: [] } } }))
      return Promise.reject(new TypeError(`No mock for ${url.pathname}`))
    })
    vi.stubGlobal('fetch', fetchMock)
    const router = await openAt('/app')
    expect(await screen.findByRole('navigation', { name: 'Main' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Account menu' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Sign out' }))
    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/')
    })
  })

  it('cycles the theme from the header', async () => {
    mockFetch({
      '/api/me': signedIn,
      '/api/health': () => ({ status: 200, body: {} }),
      '/api/agent/limits': () => ({
        status: 500,
        body: { success: false, message: 'x', code: 'internal_error' },
      }),
    })
    await openAt('/app')
    const toggle = await screen.findByRole('button', { name: /^Theme:/ })
    const before = toggle.getAttribute('aria-label')
    await userEvent.click(toggle)
    expect(screen.getByRole('button', { name: /^Theme:/ }).getAttribute('aria-label')).not.toBe(before)
  })
})

describe('route status pages', () => {
  it('shows a not-found page for an unknown address', async () => {
    mockFetch({ '/api/me': signedOut })
    await openAt('/nothing-here')
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
  })
})
