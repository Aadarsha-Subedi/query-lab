// Kept free of imports so a root-level test can check it against the backend source.
/** The providers a user can bring a key for (backend/common/llm/constants.py PROVIDERS). */
export const PROVIDERS = ['gemini', 'openai'] as const
export type ProviderName = (typeof PROVIDERS)[number]

export const PROVIDER_LABEL: Record<ProviderName, string> = {
  gemini: 'Google Gemini',
  openai: 'OpenAI',
}

/** The order the keys page lists them in. */
export const PROVIDER_ORDER: readonly ProviderName[] = ['openai', 'gemini']
