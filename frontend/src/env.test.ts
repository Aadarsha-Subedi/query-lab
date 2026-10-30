import { parseEnv } from './env'

describe('env', () => {
  it('accepts a complete env', () => {
    const result = parseEnv({
      VITE_API_BASE_URL: 'http://localhost:5173',
      VITE_APP_NAME: 'Querylab',
      VITE_QUERY_STALE_TIME_MS: '30000',
    })
    expect(result).toEqual({
      ok: true,
      env: {
        VITE_API_BASE_URL: 'http://localhost:5173',
        VITE_APP_NAME: 'Querylab',
        VITE_QUERY_STALE_TIME_MS: 30000,
      },
    })
  })

  it('reports every missing or invalid key', () => {
    const result = parseEnv({ VITE_API_BASE_URL: 'not a url' })
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.problems.some((problem) => problem.startsWith('VITE_API_BASE_URL'))).toBe(true)
      expect(result.problems.some((problem) => problem.startsWith('VITE_APP_NAME'))).toBe(true)
    }
  })
})
