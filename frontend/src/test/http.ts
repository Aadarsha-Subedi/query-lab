/** Test helpers: a fake fetch that answers by path. */
import { vi } from 'vitest'

export const TEST_BASE_URL = 'http://localhost:3000'

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

export const ME = {
  id: 1,
  email: 'ada@example.com',
  first_name: 'Ada',
  last_name: '',
  providers: ['google'],
  avatar_url: null,
  is_staff: false,
}
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

/** An enveloped success answer. */
export const ok = (data: unknown, meta: Record<string, unknown> = {}, status = 200) =>
  new Response(JSON.stringify({ success: true, status_code: status, message: '', meta, data }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

/** An enveloped error answer. */
export const fail = (status: number, code: string, message: string, errors: unknown[] = []) =>
  new Response(JSON.stringify({ success: false, status_code: status, message, code, errors }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

export type ApiRequest = { method: string; body: unknown; search: URLSearchParams }

/**
 * Answers "METHOD /path" from `handlers` (a missing one rejects like a network failure) and
 * returns the list of calls made, in order, as "METHOD /path".
 */
export function serveApi(handlers: Record<string, (request: ApiRequest) => Response>) {
  const calls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn<typeof fetch>((input, init) => {
      const url = new URL(input instanceof Request ? input.url : input.toString())
      const method = init?.method ?? 'GET'
      const key = `${method} ${url.pathname}`
      calls.push(key)
      const handler = handlers[key]
      if (!handler) return Promise.reject(new TypeError(`No mock for ${key}`))
      const body = typeof init?.body === 'string' ? (JSON.parse(init.body) as unknown) : undefined
      return Promise.resolve(handler({ method, body, search: url.searchParams }))
    }),
  )
  return calls
}

export const STAFF = { ...ME, is_staff: true }
