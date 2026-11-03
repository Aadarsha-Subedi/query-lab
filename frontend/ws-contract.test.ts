// Constants the UI shares with the backend must be the ones the backend accepts.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

import { PROVIDERS } from './src/features/llm-keys/providers.ts'

describe('shared contract constants', () => {
  it('PROVIDERS equals common.llm.constants.PROVIDERS', () => {
    const text = readFileSync(resolve(import.meta.dirname, '../backend/common/llm/constants.py'), 'utf8')
    const names = Object.fromEntries(
      [...text.matchAll(/^(PROVIDER_[A-Z]+) = "([a-z]+)"/gm)].map((m) => [m[1], m[2]]),
    )
    const listed = /^PROVIDERS = \(([^)]*)\)/m.exec(text)?.[1] ?? ''
    const expected = listed
      .split(',')
      .map((item) => names[item.trim()])
      .filter(Boolean)
    expect([...PROVIDERS]).toEqual(expected)
  })
})
