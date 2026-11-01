import type { Step } from './types'

/** Live steps plus the stored ones, by index, so each step shows once. */
export function mergeSteps(stored: Step[] | undefined, live: Step[]): Step[] {
  const byIndex = new Map<number, Step>()
  for (const step of stored ?? []) byIndex.set(step.index, step)
  for (const step of live) byIndex.set(step.index, step)
  return [...byIndex.values()].sort((a, b) => a.index - b.index)
}
