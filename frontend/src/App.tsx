import type { ClientEnv } from '@/env'

/** Placeholder until the design system is approved and routing lands (0.10c). */
export function App({ env }: { env: ClientEnv }) {
  return (
    <main className="p-8">
      <h1 className="text-2xl font-semibold">{env.VITE_APP_NAME}</h1>
    </main>
  )
}
