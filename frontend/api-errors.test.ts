// Every code in backend/API_ERRORS.md must have a user-facing entry, and no others.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { describeError, ERROR_INFO } from './src/lib/api/errors.ts'

const DOC = resolve(import.meta.dirname, '../backend/API_ERRORS.md')

function documentedCodes(): string[] {
  const codes = new Set<string>()
  for (const line of readFileSync(DOC, 'utf8').split('\n')) {
    const match = /^\| `([a-z_]+)` \|/.exec(line)
    if (match?.[1]) codes.add(match[1])
  }
  return [...codes]
}

describe('API error codes', () => {
  it('has an entry for every code in API_ERRORS.md and no others', () => {
    expect(Object.keys(ERROR_INFO).sort()).toEqual(documentedCodes().sort())
  })

  it('never tells the user to expect an automatic retry or polling', () => {
    for (const info of Object.values(ERROR_INFO)) expect(info.hint).not.toMatch(/poll|automatic/i)
  })

  it('falls back to the server message for an unknown code', () => {
    expect(describeError('brand_new_code', 'Server says no')).toEqual({ message: 'Server says no', hint: '' })
  })
})
