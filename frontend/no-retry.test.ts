// The owner's rule: nothing retries or polls by itself. A failed request shows its error
// and the user reloads or presses the component's own Try again. This keeps it that way.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

const SRC = join(import.meta.dirname, 'src')

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return sourceFiles(path)
    return /\.(ts|tsx)$/.test(name) && !/\.test\.tsx?$/.test(name) && !name.endsWith('.gen.ts') ? [path] : []
  })
}

/** The boot screen's minimum display time is not a retry. Nothing else may use a timer. */
const TIMER_ALLOWED = new Set(['boot.ts'])

const FORBIDDEN: { name: string; pattern: RegExp }[] = [
  { name: 'a retry setting other than false', pattern: /\bretry\s*:\s*(?!false\b)\S/ },
  { name: 'retryDelay', pattern: /\bretryDelay\b/ },
  { name: 'refetchInterval', pattern: /\brefetchInterval\b/ },
  {
    name: 'refetch on focus or reconnect',
    pattern: /\brefetchOn(WindowFocus|Reconnect|Mount)\s*:\s*(?!false\b)\S/,
  },
  { name: 'setInterval', pattern: /\bsetInterval\s*\(/ },
  { name: 'EventSource (it reconnects by itself)', pattern: /\bnew EventSource\b/ },
  { name: 'a timer', pattern: /\bsetTimeout\s*\(/ },
]

describe('no automatic retries or polling', () => {
  for (const { name, pattern } of FORBIDDEN) {
    it(`src has no ${name}`, () => {
      const offenders = sourceFiles(SRC).filter(
        (file) =>
          !(name === 'a timer' && TIMER_ALLOWED.has(relative(SRC, file))) &&
          pattern.test(readFileSync(file, 'utf8')),
      )
      expect(offenders.map((file) => relative(SRC, file))).toEqual([])
    })
  }
})
