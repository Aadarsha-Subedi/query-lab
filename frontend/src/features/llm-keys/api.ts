import { queryOptions } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { Schema } from '@/lib/api/types'

import type { ProviderName } from './providers'

export type SavedKey = Schema<'LLMKeyOut'>

/** GET /api/llm-keys: the keys you saved. Only the provider, the last four characters and the model come back. */
export const keysQuery = queryOptions({
  queryKey: ['llm-keys'],
  queryFn: ({ signal }) => api.get<SavedKey[]>('/api/llm-keys', { signal }),
})

export const saveKey = (provider: ProviderName, apiKey: string, model: string) =>
  api.put<SavedKey>(`/api/llm-keys/${provider}`, { api_key: apiKey, model: model.trim() || null })

export const removeKey = (provider: ProviderName) => api.delete<null>(`/api/llm-keys/${provider}`)
