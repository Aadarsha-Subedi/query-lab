import type { FieldValues, Path, UseFormReturn } from 'react-hook-form'

import { ApiError } from './client'
import { describeError } from './errors'

/**
 * Puts an API validation error next to the form field it names. Returns the text to
 * show above the form when no field matched (a code like `workspace_full`, or a field
 * the form does not have).
 */
export function applyApiErrors<T extends FieldValues>(
  form: UseFormReturn<T>,
  error: unknown,
  fields: readonly Path<T>[],
): string | null {
  if (!(error instanceof ApiError)) return 'Something went wrong. Try again.'
  let placed = false
  for (const item of error.errors) {
    const field = fields.find((name) => name === item.field)
    if (field) {
      form.setError(field, { type: 'server', message: item.message })
      placed = true
    }
  }
  if (placed) return null
  const info = describeError(error.code, error.message)
  const detail = error.errors[0]?.message
  return [detail ?? info.message, info.hint].filter(Boolean).join(' ')
}
