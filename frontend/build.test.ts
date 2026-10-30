// @vitest-environment node
// The /design showcase must not ship: a production build may not contain it.
import { mkdtempSync, readdirSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { build } from 'vite'
import { afterAll, describe, expect, it } from 'vitest'

const outDir = mkdtempSync(join(tmpdir(), 'querylab-build-'))

afterAll(() => {
  rmSync(outDir, { recursive: true, force: true })
})

function allText(dir: string): string {
  return readdirSync(dir, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => readFileSync(join(entry.parentPath, entry.name), 'utf8'))
    .join('\n')
}

describe('production build', () => {
  it('leaves out the dev-only design page', async () => {
    // Vitest runs with NODE_ENV=test, which would make import.meta.env.DEV true.
    const nodeEnv = process.env.NODE_ENV
    process.env.NODE_ENV = 'production'
    try {
      await build({
        root: import.meta.dirname,
        mode: 'production',
        logLevel: 'silent',
        build: { outDir, emptyOutDir: true },
      })
    } finally {
      process.env.NODE_ENV = nodeEnv
    }
    const text = allText(outDir)
    expect(text).toContain('Querylab') // the app itself is there
    expect(text).not.toContain('Querylab design system')
    expect(text).not.toContain('Every token and base component')
  }, 60_000)
})
