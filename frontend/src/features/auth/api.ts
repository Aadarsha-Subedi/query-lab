import { queryOptions } from '@tanstack/react-query'

import { api, ApiError } from '@/lib/api'

export type User = {
  id: number
  email: string
  first_name: string
  last_name: string
  /** The provider this user signed in with: 'google' or 'github'. */
  providers: string[]
}

const UNAUTHORIZED = 401

/** The signed-in user, or null when signed out (a 401 is an answer, not an error). */
export const meQuery = queryOptions({
  queryKey: ['me'],
  queryFn: async ({ signal }): Promise<User | null> => {
    try {
      return await api.get<User>('/api/me', { signal })
    } catch (error) {
      if (error instanceof ApiError && error.status === UNAUTHORIZED) return null
      throw error
    }
  },
})

const ALLAUTH_SESSION = '/_allauth/browser/v1/auth/session'
export const ALLAUTH_PROVIDER_REDIRECT = '/_allauth/browser/v1/auth/provider/redirect'
export const AUTH_CALLBACK_PATH = '/auth/callback'

export type Provider = 'google' | 'github'

/**
 * Ends the session. allauth answers a successful logout with 401 (there is no
 * session any more) in its own format, so a 401 here means "done".
 */
export async function signOut(): Promise<void> {
  try {
    await api.delete(ALLAUTH_SESSION)
  } catch (error) {
    if (error instanceof ApiError && error.status === UNAUTHORIZED) return
    throw error
  }
}
