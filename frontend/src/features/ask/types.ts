import type { Schema } from '@/lib/api/types'

export type Run = Schema<'RunOut'>
export type RunDetail = Schema<'RunDetailOut'>
export type Step = Schema<'StepOut'>
export type Pending = Schema<'PendingOut'>
export type RunResult = Schema<'RunResultOut'>

export type RunStatus = 'running' | 'awaiting_approval' | 'succeeded' | 'failed' | 'cancelled' | 'expired'

export const FINISHED_STATUSES: readonly string[] = ['succeeded', 'failed', 'cancelled', 'expired']

export function isFinished(status: string): boolean {
  return FINISHED_STATUSES.includes(status)
}
