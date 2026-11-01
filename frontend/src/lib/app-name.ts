import { clientEnvSchema } from '@/env'

/** The product name from the validated env (main.tsx has already checked it at boot). */
export function appName(): string {
  return clientEnvSchema.shape.VITE_APP_NAME.parse(import.meta.env.VITE_APP_NAME)
}
