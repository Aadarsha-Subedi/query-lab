// Dev-server settings, read from frontend/.env by vite.config.ts. Every key is
// required: a missing or invalid one stops the dev server.
import { z } from 'zod'

export const devServerEnvSchema = z.object({
  // Port Vite listens on inside the container (compose maps FRONTEND_PORT to it).
  DEV_SERVER_PORT: z.coerce.number().int().positive(),
  // Django on querylab-network, e.g. http://backend:8000.
  API_PROXY_TARGET: z.url(),
})

export type DevServerEnv = z.infer<typeof devServerEnvSchema>

// Paths the dev server forwards to Django, so cookies stay same-origin.
export const PROXIED_PATHS = ['/api', '/_allauth', '/accounts'] as const
