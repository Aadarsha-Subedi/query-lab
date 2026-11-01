import { queryOptions } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { Schema } from '@/lib/api/types'

import type { ProviderName } from './providers'

export type SavedKey = Schema<'LLMKeyOut'>
export type AiSource = Schema<'AISettingOut'>['source']

/** GET /api/llm-keys: the keys you saved. Only the provider, the last four characters, the model and which is active come back. */
export const keysQuery = queryOptions({
  queryKey: ['llm-keys'],
  queryFn: ({ signal }) => api.get<SavedKey[]>('/api/llm-keys', { signal }),
})

/** GET /api/llm-keys-models: the models you may pick per provider (the first is the default). */
export const modelsQuery = queryOptions({
  queryKey: ['llm-models'],
  queryFn: ({ signal }) => api.get<Schema<'LLMModelsOut'>>('/api/llm-keys-models', { signal }),
})

/** GET /api/llm-settings: whether questions use QueryLab's AI or your own key. */
export const settingsQuery = queryOptions({
  queryKey: ['llm-settings'],
  queryFn: ({ signal }) => api.get<Schema<'AISettingOut'>>('/api/llm-settings', { signal }),
})

export const saveKey = (provider: ProviderName, apiKey: string, model: string) =>
  api.put<SavedKey>(`/api/llm-keys/${provider}`, { api_key: apiKey, model: model.trim() || null })

export const removeKey = (provider: ProviderName) => api.delete<null>(`/api/llm-keys/${provider}`)

export const changeModel = (provider: ProviderName, model: string) =>
  api.put<SavedKey>(`/api/llm-keys/${provider}/model`, { model })

export const activateKey = (provider: ProviderName) =>
  api.put<SavedKey>(`/api/llm-keys/${provider}/activate`, {})

export const setSource = (source: AiSource) =>
  api.put<Schema<'AISettingOut'>>('/api/llm-settings', { source })
