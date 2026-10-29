import { StrictMode, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from '@/App'
import { ThemeController } from '@/components/ThemeController'
import { EnvErrorScreen } from '@/EnvErrorScreen'
import { parseEnv } from '@/env'
import '@/index.css'

const DESIGN_PATH = '/design'

const container = document.getElementById('root')
if (!container) throw new Error('index.html has no #root element')
const root = createRoot(container)

function render(page: ReactNode) {
  root.render(
    <StrictMode>
      <ThemeController />
      {page}
    </StrictMode>,
  )
}

const env = parseEnv(import.meta.env)

if (!env.ok) {
  render(<EnvErrorScreen problems={env.problems} />)
} else if (import.meta.env.DEV && window.location.pathname === DESIGN_PATH) {
  // Dev-only showcase. import.meta.env.DEV is false in production builds, so
  // this branch and the page's chunk are dropped from them.
  void import('@/features/design/DesignPage').then(({ DesignPage }) => {
    render(<DesignPage />)
  })
} else {
  render(<App env={env.env} />)
}
