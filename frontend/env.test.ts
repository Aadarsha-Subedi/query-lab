// The keys the code reads (browser + dev server) must match .env.example exactly.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

import { devServerEnvSchema } from './env.config.ts'
import { clientEnvSchema } from './src/env.ts'

function keysInEnvExample(): string[] {
  return readFileSync(resolve(import.meta.dirname, '.env.example'), 'utf8')
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('#'))
    .map((line) => line.split('=')[0] ?? '')
}

describe('.env.example', () => {
  it('lists exactly the keys the code reads', () => {
    const read = [...Object.keys(clientEnvSchema.shape), ...Object.keys(devServerEnvSchema.shape)]
    expect(keysInEnvExample().sort()).toEqual(read.sort())
  })
})
