// The column types and on-delete choices the UI offers must be the ones the backend accepts.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

import { COLUMN_TYPES, ON_DELETE } from './src/features/workspaces/contract.ts'

const backend = (file: string) =>
  readFileSync(resolve(import.meta.dirname, '../backend/workspaces', file), 'utf8')

describe('workspace contract constants', () => {
  it('COLUMN_TYPES equals naming.COLUMN_TYPES', () => {
    const block = /COLUMN_TYPES: dict\[str, str\] = \{([^}]*)\}/.exec(backend('naming.py'))?.[1] ?? ''
    const keys = [...block.matchAll(/"([a-z]+)":/g)].map((match) => match[1])
    expect([...COLUMN_TYPES]).toEqual(keys)
  })

  it('ON_DELETE equals relations.ON_DELETE', () => {
    const block = /^ON_DELETE = \{([^}]*)\}/m.exec(backend('relations.py'))?.[1] ?? ''
    const keys = [...block.matchAll(/"([A-Z ]+)":/g)].map((match) => match[1])
    expect([...ON_DELETE]).toEqual(keys)
  })
})
