/** Test helpers: a fake fetch that answers by path. */
import { vi } from 'vitest'

export const TEST_BASE_URL = 'http://localhost:5173'

type Answer = { status: number; body?: unknown; headers?: Record<string, string> }

export function jsonResponse({ status, body, headers }: Answer): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  })
}

/** Replace fetch with one that answers each path from `routes` (fresh Response per call). */
export function mockFetch(routes: Record<string, () => Answer>) {
  const fetchMock = vi.fn<typeof fetch>((input) => {
    const url = new URL(input instanceof Request ? input.url : input.toString())
    const answer = routes[url.pathname]
    if (!answer) return Promise.reject(new TypeError(`No mock for ${url.pathname}`))
    return Promise.resolve(jsonResponse(answer()))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export const ME = { id: 1, email: 'ada@example.com', first_name: 'Ada', last_name: '' }
export const signedIn = () => ({
  status: 200,
  body: { success: true, status_code: 200, message: '', data: ME, meta: {} },
})
export const signedOut = () => ({
  status: 401,
  body: {
    success: false,
    status_code: 401,
    message: 'Not signed in.',
    code: 'authentication_denied',
    errors: [],
  },
})
