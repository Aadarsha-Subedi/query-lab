import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { failBoot, finishBoot } from '@/boot'
import { EnvErrorScreen } from '@/EnvErrorScreen'
import { parseEnv } from '@/env'
import { meQuery } from '@/features/auth/api'
import { initApi } from '@/lib/api'
import { createQueryClient } from '@/lib/query-client'
import { createAppRouter } from '@/router'
import '@/index.css'

/** The dev-only showcase needs no backend, so boot skips the sign-in check. */
const DESIGN_PATH = '/design'

async function start() {
  const container = document.getElementById('root')
  if (!container) throw new Error('index.html has no #root element')
  const root = createRoot(container)

  // 1. Environment.
  const env = parseEnv(import.meta.env)
  if (!env.ok) {
    void finishBoot()
    root.render(<EnvErrorScreen problems={env.problems} />)
    return
  }

  initApi(env.env.VITE_API_BASE_URL)
  const queryClient = createQueryClient(env.env.VITE_QUERY_STALE_TIME_MS)
  const router = createAppRouter(queryClient)

  // 2. Who is signed in. A 401 is an answer (signed out); anything else means
  //    the app cannot start, and the boot screen says so.
  const designOnly = import.meta.env.DEV && window.location.pathname === DESIGN_PATH
  if (!designOnly) {
    try {
      await queryClient.query(meQuery)
    } catch {
      failBoot()
      return
    }
  }

  // 3. The first route (guards reuse the cached /api/me answer).
  await router.load()
  root.render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </StrictMode>,
  )
  void finishBoot()
}

void start()
