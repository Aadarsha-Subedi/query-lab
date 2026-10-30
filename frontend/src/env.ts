import { z } from 'zod'

/**
 * Every variable the app reads from `import.meta.env`. All are required: a
 * missing or invalid one shows the startup error screen and the app stops.
 * Keep in sync with `.env.example` (a test checks it).
 */
export const clientEnvSchema = z.object({
  VITE_API_BASE_URL: z.url(),
  VITE_APP_NAME: z.string().min(1),
  // How long fetched data counts as fresh before a remount refetches it.
  VITE_QUERY_STALE_TIME_MS: z.coerce.number().int().nonnegative(),
})

export type ClientEnv = z.infer<typeof clientEnvSchema>

export type EnvResult = { ok: true; env: ClientEnv } | { ok: false; problems: string[] }

export function parseEnv(source: Record<string, unknown>): EnvResult {
  const result = clientEnvSchema.safeParse(source)
  if (result.success) return { ok: true, env: result.data }
  return {
    ok: false,
    problems: result.error.issues.map((issue) => `${issue.path.join('.')}: ${issue.message}`),
  }
}
