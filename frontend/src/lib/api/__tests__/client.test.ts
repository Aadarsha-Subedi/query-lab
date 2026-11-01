import { toast } from 'sonner'

import { ApiError, createApiClient } from '@/lib/api'
import { mockFetch, TEST_BASE_URL } from '@/test/http'

vi.mock('sonner', async (importOriginal) => {
  const actual = await importOriginal<typeof import('sonner')>()
  return { ...actual, toast: Object.assign(vi.fn(), { error: vi.fn(), success: vi.fn() }) }
})

const client = () => createApiClient(TEST_BASE_URL)

afterEach(() => {
  vi.unstubAllGlobals()
  document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
})

describe('api client', () => {
  it('unwraps the envelope and sends cookies', async () => {
    const fetchMock = mockFetch({
      '/api/thing': () => ({ status: 200, body: { success: true, data: { n: 1 } } }),
    })
    await expect(client().get('/api/thing')).resolves.toEqual({ n: 1 })
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ credentials: 'include', method: 'GET' })
  })

  it('sends the CSRF token on writes only', async () => {
    document.cookie = 'csrftoken=abc123'
    const fetchMock = mockFetch({
      '/api/thing': () => ({ status: 200, body: { success: true, data: null } }),
    })
    await client().post('/api/thing', { a: 1 })
    await client().get('/api/thing')
    const headers = (call: number) =>
      (fetchMock.mock.calls[call]?.[1] as RequestInit).headers as Record<string, string>
    expect(headers(0)['X-CSRFToken']).toBe('abc123')
    expect(headers(1)['X-CSRFToken']).toBeUndefined()
  })

  it('turns an error envelope into a typed ApiError with the request id', async () => {
    mockFetch({
      '/api/thing': () => ({
        status: 422,
        body: {
          success: false,
          message: 'Validation failed.',
          code: 'validation_error',
          errors: [{ field: 'email', message: 'Bad.' }],
        },
        headers: { 'X-Request-ID': 'req-42' },
      }),
    })
    const error = await client()
      .get('/api/thing')
      .catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 422, code: 'validation_error', requestId: 'req-42' })
    expect((error as ApiError).errors).toEqual([{ field: 'email', message: 'Bad.' }])
  })

  it('never retries a failed request', async () => {
    const fetchMock = mockFetch({
      '/api/thing': () => ({
        status: 500,
        body: { success: false, message: 'Boom.', code: 'internal_error' },
      }),
    })
    await expect(client().get('/api/thing')).rejects.toBeInstanceOf(ApiError)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('reports a network failure as status 0', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )
    await expect(client().get('/api/thing')).rejects.toMatchObject({ status: 0, code: 'network_error' })
  })

  it('shows a toast with the wait on 429', async () => {
    mockFetch({
      '/api/thing': () => ({
        status: 429,
        body: { success: false, message: 'Too many requests.', code: 'throttled' },
        headers: { 'Retry-After': '30' },
      }),
    })
    await expect(client().get('/api/thing')).rejects.toMatchObject({ status: 429 })
    expect(toast.error).toHaveBeenCalledWith('Too many requests', { description: 'Try again in 30 seconds.' })
  })

  it('returns raw bodies and accepts listed statuses (health)', async () => {
    mockFetch({ '/api/health': () => ({ status: 503, body: { status: 'degraded' } }) })
    await expect(client().get('/api/health', { shape: 'raw', acceptStatuses: [503] })).resolves.toEqual({
      status: 'degraded',
    })
  })

  it('sends PUT and PATCH with a body and the CSRF token', async () => {
    document.cookie = 'csrftoken=abc123'
    const fetchMock = mockFetch({
      '/api/thing': () => ({ status: 200, body: { success: true, data: { ok: true } } }),
    })
    await client().put('/api/thing', { a: 1 })
    await client().patch('/api/thing', { b: 2 })
    const init = (call: number) => fetchMock.mock.calls[call]?.[1] as RequestInit
    expect(init(0)).toMatchObject({ method: 'PUT', body: JSON.stringify({ a: 1 }) })
    expect(init(1)).toMatchObject({ method: 'PATCH', body: JSON.stringify({ b: 2 }) })
    expect((init(0).headers as Record<string, string>)['X-CSRFToken']).toBe('abc123')
    expect((init(1).headers as Record<string, string>)['X-CSRFToken']).toBe('abc123')
  })

  it('keeps retry_after_seconds on the error, null when waiting does not help', async () => {
    mockFetch({
      '/api/wait': () => ({
        status: 429,
        body: { success: false, message: 'Slow.', code: 'throttled', retry_after_seconds: 12 },
      }),
      '/api/never': () => ({
        status: 429,
        body: { success: false, message: 'Full.', code: 'agent_run_limit', retry_after_seconds: null },
      }),
    })
    await expect(client().get('/api/wait')).rejects.toMatchObject({ retryAfterSeconds: 12 })
    await expect(client().get('/api/never')).rejects.toMatchObject({ retryAfterSeconds: null })
  })
})
