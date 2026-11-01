import { ApiError } from './client'
import { describeError } from './errors'

/** The text to show for a failed call: our wording for the code, else the server's. */
export function errorText(error: unknown): { message: string; hint: string } {
  if (error instanceof ApiError) return describeError(error.code, error.message)
  return { message: 'Something went wrong.', hint: 'Try again.' }
}
