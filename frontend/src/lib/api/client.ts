/*
 * The one HTTP client for the Querylab API.
 *
 * - Sends cookies (session) and, on writes, the X-CSRFToken header from the
 *   csrftoken cookie (GET /api/me sets it on every load).
 * - Unwraps the API envelope: {success: true, data} -> data, and
 *   {success: false, ...} -> a typed ApiError.
 * - Never retries (design-system.md section 13). A 429 also shows a toast
 *   with the wait from Retry-After; the caller still gets the error.
 */
import { toast } from '@/components/ui/toast-api'

const CSRF_COOKIE = 'csrftoken'
const CSRF_HEADER = 'X-CSRFToken'
const REQUEST_ID_HEADER = 'X-Request-ID'
const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])
const TOO_MANY_REQUESTS = 429
/** status 0: the request never got an HTTP answer (offline, DNS, CORS, server down). */
const NO_RESPONSE = 0

export type FieldError = { field: string | null; message: string }

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly errors: FieldError[]
  /** X-Request-ID of the failed call, shown in ErrorState for bug reports. */
  readonly requestId: string | null

  constructor(init: {
    status: number
    code: string
    message: string
    errors?: FieldError[]
    requestId?: string | null
  }) {
    super(init.message)
    this.name = 'ApiError'
    this.status = init.status
    this.code = init.code
    this.errors = init.errors ?? []
    this.requestId = init.requestId ?? null
  }
}

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

export type RequestOptions = {
  method?: Method
  body?: unknown
  signal?: AbortSignal
  /**
   * 'envelope' (default): our {success, data} shape. 'raw': return the parsed
   * JSON as is (for /api/health, which is not enveloped).
   */
  shape?: 'envelope' | 'raw'
  /** Extra statuses that still count as an answer (e.g. 503 for /api/health). */
  acceptStatuses?: number[]
}

function readCookie(name: string): string | null {
  const prefix = `${name}=`
  const entry = document.cookie.split('; ').find((part) => part.startsWith(prefix))
  return entry ? decodeURIComponent(entry.slice(prefix.length)) : null
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function errorFromBody(status: number, body: unknown, requestId: string | null): ApiError {
  if (isRecord(body) && body.success === false) {
    return new ApiError({
      status,
      code: typeof body.code === 'string' ? body.code : 'error',
      message: typeof body.message === 'string' ? body.message : 'The request failed.',
      errors: Array.isArray(body.errors) ? (body.errors as FieldError[]) : [],
      requestId,
    })
  }
  return new ApiError({
    status,
    code: 'bad_response',
    message: 'The server sent an unexpected answer.',
    requestId,
  })
}

function notifyThrottled(response: Response) {
  const seconds = Number(response.headers.get('Retry-After'))
  toast.error('Too many requests', {
    description:
      Number.isFinite(seconds) && seconds > 0 ? `Try again in ${seconds} seconds.` : 'Try again shortly.',
  })
}

export type ApiClient = ReturnType<typeof createApiClient>

export function createApiClient(baseUrl: string) {
  async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const method = options.method ?? 'GET'
    const headers: Record<string, string> = { Accept: 'application/json' }
    if (options.body !== undefined) headers['Content-Type'] = 'application/json'
    if (UNSAFE_METHODS.has(method)) {
      const token = readCookie(CSRF_COOKIE)
      if (token) headers[CSRF_HEADER] = token
    }

    let response: Response
    try {
      response = await fetch(new URL(path, baseUrl), {
        method,
        headers,
        credentials: 'include',
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        signal: options.signal,
      })
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === 'AbortError') throw cause
      throw new ApiError({
        status: NO_RESPONSE,
        code: 'network_error',
        message: "The server didn't answer. Check your connection.",
      })
    }

    const requestId = response.headers.get(REQUEST_ID_HEADER)
    let body: unknown = null
    const text = await response.text()
    if (text) {
      try {
        body = JSON.parse(text)
      } catch {
        throw new ApiError({
          status: response.status,
          code: 'bad_response',
          message: 'The server sent an unexpected answer.',
          requestId,
        })
      }
    }

    if (response.status === TOO_MANY_REQUESTS) notifyThrottled(response)
    const answered = response.ok || (options.acceptStatuses ?? []).includes(response.status)
    if (!answered) throw errorFromBody(response.status, body, requestId)
    if (options.shape === 'raw') return body as T
    if (isRecord(body) && body.success === true) return body.data as T
    throw errorFromBody(response.status, body, requestId)
  }

  return {
    request,
    get: <T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>) =>
      request<T>(path, { ...options, method: 'GET' }),
    post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
      request<T>(path, { ...options, method: 'POST', body }),
    delete: <T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>) =>
      request<T>(path, { ...options, method: 'DELETE' }),
  }
}
