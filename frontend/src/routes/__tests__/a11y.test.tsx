// Automated accessibility check (axe) on every screen with data. jsdom has no layout, so the
// colour-contrast rule is off here; contrast is covered by the design tokens test on /design.
import { QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import axe from 'axe-core'
import { cleanup, render, screen } from '@testing-library/react'

import { initApi } from '@/lib/api'
import { createQueryClient } from '@/lib/query-client'
import { createAppRouter } from '@/router'
import { jsonResponse, ok, STAFF, TEST_BASE_URL } from '@/test/http'

const page = (data: unknown[]) => ok(data, { count: data.length, limit: 20, offset: 0 })
const run = {
  id: 5,
  question: 'How many orders?',
  status: 'succeeded',
  latency_ms: 2000,
  created_at: '2026-11-01T00:00:00Z',
  edited: false,
  feedback: null,
  check: 'checked',
  revisions: 0,
  error_code: '',
  has_result: false,
  pending: null,
  steps: [],
}
const col = (name: string) => ({ name, type: 'text', nullable: true, description: '', hidden: false })

const ANSWERS: Record<string, () => Response> = {
  '/api/agent/limits': () =>
    ok({
      default_key: { used: 1, allowed: 20, remaining: 19, resets_at: '2026-11-02T00:00:00Z' },
      has_own_key: false,
      streams: { open: 0, allowed: 5 },
      unfinished_runs: { count: 0, allowed: 3 },
      workspace_id: null,
    }),
  '/api/schema': () =>
    ok({
      name: 'demo',
      tables: [
        {
          name: 'orders',
          comment: '',
          row_estimate: 3,
          primary_key: ['id'],
          foreign_keys: [],
          columns: [{ name: 'id', type: 'text', nullable: false, comment: '', samples: [] }],
        },
      ],
    }),
  '/api/agent/runs': () => page([run]),
  '/api/agent/runs/5': () => ok(run),
  '/api/agent/runs/5/events': () => new Response('', { headers: { 'Content-Type': 'text/event-stream' } }),
  '/api/agent/runs/5/replay': () =>
    ok({
      ...run,
      steps: [
        {
          index: 0,
          kind: 'plan',
          tool_name: '',
          input: {},
          output: 'p',
          status: 'ok',
          error_code: '',
          input_tokens: 0,
          output_tokens: 0,
          latency_ms: 5,
          actor: 'agent',
          created_at: '2026-11-01T00:00:00Z',
        },
      ],
    }),
  '/api/workspaces': () =>
    ok([
      {
        id: null,
        kind: 'demo',
        name: 'Demo',
        status: 'ready',
        read_only: true,
        tables: 1,
        bytes_used: 0,
        bytes_allowed: null,
        created_at: null,
      },
      {
        id: 7,
        kind: 'user',
        name: 'Shop',
        status: 'ready',
        read_only: false,
        tables: 1,
        bytes_used: 10,
        bytes_allowed: 100,
        created_at: null,
      },
    ]),
  '/api/workspaces/limits': () =>
    ok({
      workspaces: { used: 1, allowed: 3 },
      bytes: { used: 10, allowed: 300, per_workspace: 100 },
      max_tables: 5,
      max_columns: 5,
      max_relations: 5,
      max_rows_per_edit: 50,
    }),
  '/api/workspaces/7': () =>
    ok({
      id: 7,
      kind: 'user',
      name: 'Shop',
      status: 'ready',
      read_only: false,
      tables: 1,
      bytes_used: 10,
      bytes_allowed: 100,
      created_at: null,
    }),
  '/api/workspaces/7/tables': () =>
    ok([{ name: 'products', description: '', row_estimate: 1, primary_key: [], columns: [col('sku')] }]),
  '/api/llm-keys': () => ok([]),
  '/api/workbench/runs': () => page([run]),
  '/api/workbench/cases': () => page([]),
  '/api/workbench/clusters': () => ok([]),
  '/api/workbench/eval/runs': () => page([]),
}

const SCREENS: [string, string][] = [
  ['landing', '/'],
  ['sign in', '/login'],
  ['ask', '/ask'],
  ['ask with a run', '/ask?run=5'],
  ['ask schema tab', '/ask?tab=schema'],
  ['history', '/history'],
  ['replay', '/runs/5/replay'],
  ['workspaces', '/workspaces'],
  ['workspace editor', '/workspaces/7?table=products'],
  ['sql console', '/workspaces/7?tab=sql'],
  ['ai settings', '/settings'],
  ['traces', '/workbench/runs'],
  ['cases', '/workbench/cases'],
  ['evals', '/workbench/evals'],
  ['not found', '/nowhere'],
]

function stub(signedIn: boolean) {
  vi.stubGlobal(
    'fetch',
    vi.fn<typeof fetch>((input) => {
      const url = new URL(input instanceof Request ? input.url : input.toString())
      if (url.pathname === '/api/me') {
        return Promise.resolve(
          signedIn
            ? jsonResponse({
                status: 200,
                body: { success: true, status_code: 200, message: '', meta: {}, data: STAFF },
              })
            : jsonResponse({
                status: 401,
                body: {
                  success: false,
                  status_code: 401,
                  message: 'no',
                  code: 'authentication_denied',
                  errors: [],
                },
              }),
        )
      }
      const answer = ANSWERS[url.pathname]
      return Promise.resolve(answer ? answer() : ok({}))
    }),
  )
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe.each(SCREENS)('%s', (_name, path) => {
  it('has no accessibility violations axe can find', async () => {
    const publicScreen = ['/', '/login', '/nowhere'].includes(path)
    stub(!publicScreen)
    initApi(TEST_BASE_URL)
    const queryClient = createQueryClient(0)
    const router = createAppRouter(queryClient, createMemoryHistory({ initialEntries: [path] }))
    await router.load()
    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    )
    await screen.findAllByRole(publicScreen ? 'heading' : 'banner')
    await new Promise((resolve) => setTimeout(resolve, 200))
    const result = await axe.run(container, {
      rules: { 'color-contrast': { enabled: false }, region: { enabled: false } },
    })
    expect(
      result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`),
    ).toEqual([])
  })
})
