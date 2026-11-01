/** A table cell as text. NULL is shown as an empty cell, objects as JSON. */
export function cellText(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint')
    return String(value)
  return JSON.stringify(value)
}
