/*
 * The app-wide API client, created once at boot from the validated env
 * (main.tsx calls initApi). Features import `api` from here.
 */
import { createApiClient, type ApiClient } from './client'

export { ApiError, createApiClient, type ApiClient, type FieldError, type RequestOptions } from './client'

let instance: ApiClient | null = null

export function initApi(baseUrl: string): ApiClient {
  instance = createApiClient(baseUrl)
  return instance
}

export const api: ApiClient = {
  request: (...args) => current().request(...args),
  get: (...args) => current().get(...args),
  post: (...args) => current().post(...args),
  put: (...args) => current().put(...args),
  patch: (...args) => current().patch(...args),
  delete: (...args) => current().delete(...args),
}

function current(): ApiClient {
  if (!instance) throw new Error('initApi() must run before the API is used (see main.tsx).')
  return instance
}
