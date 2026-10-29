import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'

import { devServerEnvSchema, PROXIED_PATHS } from './env.config.ts'

// https://vite.dev/config/
export default defineConfig(({ command, mode }) => {
  // Only the dev server needs these; a production build is static files.
  const server =
    command === 'serve'
      ? (() => {
          const env = devServerEnvSchema.parse(loadEnv(mode, process.cwd(), ''))
          return {
            host: '0.0.0.0',
            port: env.DEV_SERVER_PORT,
            strictPort: true,
            // Keep the browser's Host header: allauth builds OAuth callback URLs from it.
            proxy: Object.fromEntries(
              PROXIED_PATHS.map((path) => [path, { target: env.API_PROXY_TARGET, changeOrigin: false }]),
            ),
          }
        })()
      : undefined

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    server,
  }
})
