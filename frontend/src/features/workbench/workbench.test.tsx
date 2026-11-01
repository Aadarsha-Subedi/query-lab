import { QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { initApi } from '@/lib/api'
import { createQueryClient } from '@/lib/query-client'
import { createAppRouter } from '@/router'
import { fail, jsonResponse, ok, serveApi, STAFF, TEST_BASE_URL, type ApiRequest } from '@/test/http'

import { diffLines } from './diff'

const me = (staff: boolean) => () =>
  jsonResponse({
    status: 200,
    body: {
      success: true,
      status_code: 200,
      message: '',
      meta: {},
      data: staff ? STAFF : { ...STAFF, is_staff: false },
    },
  })

const traceRun = (id: number, over: Record<string, unknown> = {}) => ({
  id,
  question: `Trace question ${id}`,
  status: 'succeeded',
  latency_ms: 3000,
  created_at: '2026-11-01T00:00:00Z',
  edited: false,
  feedback: null,
  check: 'checked',
  revisions: 0,
  ...over,
})
const caseRow = (id: number, over: Record<string, unknown> = {}) => ({
  id,
  question: `Case question ${id}`,
  status: 'drafted',
  reasons: ['edited_sql'],
  created_at: '2026-11-01T00:00:00Z',
  draft_error: '',
  draft_model: 'm1',
  draft_sql: 'select 1',
  gold_sql: '',
  source_sql: 'select 2',
  answerable: true,
  run_id: 9,
  note: '',
  preview: { columns: ['n'], rows: [[1]], row_count: 1, truncated: false, error: '' },
  ...over,
})
const evalRun = (id: number, over: Record<string, unknown> = {}) => ({
  id,
  target: 'traces',
  runner: 'agent',
  model: 'gem',
  split: 'all',
  provider: 'gemini',
  prompt_version: 'v1',
  status: 'done',
  accuracy: 0.8,
  correct_count: 8,
  question_count: 10,
  cost_per_question_usd: 0.001,
  started_at: '2026-11-01T00:00:00Z',
  finished_at: '2026-11-01T01:00:00Z',
  ...over,
})

function serve(staff: boolean, extra: Record<string, (request: ApiRequest) => Response> = {}) {
  return serveApi({
    'GET /api/me': me(staff),
    'GET /api/agent/limits': () => fail(500, 'internal_error', 'x'),
    ...extra,
  })
}

async function openAt(path: string) {
  initApi(TEST_BASE_URL)
  const queryClient = createQueryClient(0)
  const router = createAppRouter(queryClient, createMemoryHistory({ initialEntries: [path] }))
  await router.load()
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('diffLines', () => {
  it('marks removed and added lines and keeps shared ones', () => {
    expect(diffLines('select a\nfrom t', 'select a\nfrom t\nlimit 5')).toEqual([
      { kind: 'same', text: 'select a' },
      { kind: 'same', text: 'from t' },
      { kind: 'added', text: 'limit 5' },
    ])
    expect(diffLines('a\nb', 'a\nc')).toEqual([
      { kind: 'same', text: 'a' },
      { kind: 'removed', text: 'b' },
      { kind: 'added', text: 'c' },
    ])
  })
})

describe('staff guard', () => {
  it('shows a non-staff user a plain "not available", never the screens', async () => {
    const calls = serve(false)
    await openAt('/workbench/runs')
    expect(await screen.findByRole('heading', { name: 'Not available' })).toBeVisible()
    expect(calls.some((call) => call.includes('/api/workbench'))).toBe(false)
    expect(screen.queryByRole('link', { name: 'Workbench' })).not.toBeInTheDocument()
  })

  it('shows staff the nav entry and the screens', async () => {
    serve(true, { 'GET /api/workbench/runs': () => ok([traceRun(1)], { count: 1, limit: 20, offset: 0 }) })
    await openAt('/workbench/runs')
    expect(await screen.findByRole('link', { name: 'Trace question 1' })).toBeVisible()
    expect(screen.getAllByRole('link', { name: 'Workbench' }).length).toBeGreaterThan(0)
  })
})

describe('traces', () => {
  it('filters from the URL and shows the signals', async () => {
    const urls: URLSearchParams[] = []
    serve(true, {
      'GET /api/workbench/runs': (request) => {
        urls.push(request.search)
        return ok([traceRun(1, { feedback: 'down', edited: true, check: 'needs_look' })], {
          count: 1,
          limit: 20,
          offset: 0,
        })
      },
    })
    await openAt('/workbench/runs?feedback=down&edited=true')
    expect(await screen.findByText('thumbs down')).toBeVisible()
    expect(screen.getByText('needs a look')).toBeVisible()
    expect(urls[0]?.get('feedback')).toBe('down')
    expect(urls[0]?.get('edited')).toBe('true')
  })

  it('shows proposed against approved SQL for an edited run', async () => {
    serve(true, {
      'GET /api/workbench/runs/4': () =>
        ok({
          ...traceRun(4),
          provider: 'gemini',
          model: 'gem',
          prompt_version: 'v1',
          llm_calls: 2,
          input_tokens: 10,
          output_tokens: 5,
          error_code: '',
          diff: true,
          proposed_sql: 'select a\nfrom t',
          approved_sql: 'select a\nfrom t\nlimit 5',
          final_sql: 'select a from t limit 5',
          steps: [],
        }),
    })
    await openAt('/workbench/runs/4')
    const diff = await screen.findByLabelText('SQL changes')
    expect(within(diff).getByText('limit 5')).toBeVisible()
    expect(within(diff).getByText('Added:')).toBeInTheDocument()
  })
})

describe('case review', () => {
  const detail = (over: Record<string, unknown> = {}, approve?: (request: ApiRequest) => Response) =>
    serve(true, {
      'GET /api/workbench/cases/3': () => ok(caseRow(3, over)),
      'GET /api/workbench/cases': () => ok([caseRow(3)], { count: 1, limit: 20, offset: 0 }),
      'GET /api/workbench/clusters': () => ok([]),
      ...(approve ? { 'POST /api/workbench/cases/3/approve': approve } : {}),
    })

  it('shows the draft, the rows preview and the trace link, and approves with the edited SQL', async () => {
    let sent: unknown
    detail({}, (request) => {
      sent = request.body
      return ok(caseRow(3, { status: 'approved' }))
    })
    await openAt('/workbench/cases/3')
    expect(await screen.findByText(/Run just now, not stored/)).toBeVisible()
    expect(screen.getByRole('link', { name: 'Source trace' })).toHaveAttribute('href', '/workbench/runs/9')
    const sql = screen.getByRole('textbox', { name: 'Expected SQL' })
    await userEvent.clear(sql)
    await userEvent.type(sql, 'select 3')
    await userEvent.click(screen.getByRole('button', { name: 'Approve as gold' }))
    await waitFor(() => {
      expect(sent).toEqual({ sql: 'select 3' })
    })
  })

  it('will not approve a failed draft until the reviewer writes SQL', async () => {
    detail({ draft_error: 'model refused', draft_sql: '', preview: null })
    await openAt('/workbench/cases/3')
    expect(await screen.findByText(/The draft failed: model refused/)).toBeVisible()
    const approve = screen.getByRole('button', { name: 'Approve as gold' })
    expect(approve).toBeDisabled()
    await userEvent.type(screen.getByRole('textbox', { name: 'Expected SQL' }), 'select 1')
    expect(approve).toBeEnabled()
  })

  it('shows the guard refusal under the SQL field', async () => {
    detail({}, () =>
      fail(400, 'guard_rejected', 'Refused.', [{ field: 'sql', message: 'Only SELECT is allowed.' }]),
    )
    await openAt('/workbench/cases/3')
    const sql = await screen.findByRole('textbox', { name: 'Expected SQL' })
    await userEvent.type(sql, ' -- x')
    await userEvent.click(screen.getByRole('button', { name: 'Approve as gold' }))
    expect(await screen.findByText('Only SELECT is allowed.')).toBeVisible()
  })

  it('locks a case that is already approved', async () => {
    detail({ status: 'approved', preview: null })
    await openAt('/workbench/cases/3')
    expect(await screen.findByText(/can no longer be reviewed/)).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Approve as gold' })).not.toBeInTheDocument()
  })

  it('rejects with a reason and marks unanswerable with a note', async () => {
    const bodies: Record<string, unknown> = {}
    serve(true, {
      'GET /api/workbench/cases/3': () => ok(caseRow(3)),
      'POST /api/workbench/cases/3/reject': (request) => {
        bodies.reject = request.body
        return ok(caseRow(3, { status: 'rejected' }))
      },
      'POST /api/workbench/cases/3/mark-unanswerable': (request) => {
        bodies.unanswerable = request.body
        return ok(caseRow(3, { status: 'approved', answerable: false }))
      },
    })
    await openAt('/workbench/cases/3')
    await userEvent.type(await screen.findByLabelText('Reason for rejecting'), 'duplicate')
    await userEvent.click(screen.getByRole('button', { name: 'Reject' }))
    await waitFor(() => {
      expect(bodies.reject).toEqual({ reason: 'duplicate' })
    })
  })

  it('lists cases with their clusters and queues a draft batch', async () => {
    const calls = serve(true, {
      'GET /api/workbench/cases': () =>
        ok([caseRow(3, { draft_error: 'x' })], { count: 1, limit: 20, offset: 0 }),
      'GET /api/workbench/clusters': () =>
        ok([
          {
            key: 'k1',
            label: 'Late deliveries',
            size: 4,
            member_ids: [1],
            representative_id: 1,
            status_counts: { drafted: 2 },
          },
        ]),
      'POST /api/workbench/cases/draft': () => ok({ queued: true }, {}, 202),
    })
    await openAt('/workbench/cases')
    expect(await screen.findByText('Late deliveries')).toBeVisible()
    expect(screen.getByText('draft failed')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Draft a batch' }))
    await waitFor(() => {
      expect(calls).toContain('POST /api/workbench/cases/draft')
    })
  })
})

describe('eval dashboard', () => {
  it('lists runs and compares two picked ones', async () => {
    serve(true, {
      'GET /api/workbench/eval/runs': () =>
        ok([evalRun(1), evalRun(2, { accuracy: 0.9 })], { count: 2, limit: 20, offset: 0 }),
    })
    await openAt('/workbench/evals')
    expect(await screen.findByText('80.0% (8/10)')).toBeVisible()
    await userEvent.click(screen.getByRole('checkbox', { name: 'Pick run 1 to compare' }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'Pick run 2 to compare' }))
    expect(screen.getByRole('link', { name: 'Compare the two picked runs' })).toHaveAttribute(
      'href',
      '/workbench/evals/compare?base=1&other=2',
    )
  })

  it('shows a run with accuracy by cluster and filters its cases by outcome', async () => {
    serve(true, {
      'GET /api/workbench/eval/runs/1': () =>
        ok({
          ...evalRun(1),
          by_cluster: [{ cluster_key: 'late', accuracy: 0.5, correct: 1, total: 2 }],
          results: [
            {
              question_id: 'a',
              question: 'Q right',
              gold_sql: '',
              predicted_sql: '',
              outcome: 'correct',
              reason: '',
              cluster_key: 'late',
              trace_case_id: 5,
              trace_path: null,
            },
            {
              question_id: 'b',
              question: 'Q wrong',
              gold_sql: '',
              predicted_sql: '',
              outcome: 'wrong',
              reason: 'bad join',
              cluster_key: 'late',
              trace_case_id: null,
              trace_path: null,
            },
          ],
        }),
    })
    await openAt('/workbench/evals/1')
    expect(await screen.findByText('50.0%')).toBeVisible()
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Outcome' }), 'wrong')
    expect(screen.queryByText('Q right')).not.toBeInTheDocument()
    expect(screen.getByText('bad join')).toBeVisible()
  })

  it('compares two runs with the flips in both directions', async () => {
    serve(true, {
      'GET /api/workbench/eval/compare': () =>
        ok({
          base: evalRun(1),
          other: evalRun(2),
          base_accuracy: 0.8,
          other_accuracy: 0.7,
          diff_points: -10,
          shared: 10,
          only_in_base: 0,
          only_in_other: 0,
          clusters: [{ cluster_key: 'late', base_correct: 4, other_correct: 3, shared: 5, diff_points: -20 }],
          flips: [
            {
              question_id: 'a',
              question: 'Got worse Q',
              direction: 'to_wrong',
              base_outcome: 'correct',
              other_outcome: 'wrong',
              cluster_key: 'late',
              trace_case_id: null,
            },
            {
              question_id: 'b',
              question: 'Got better Q',
              direction: 'to_correct',
              base_outcome: 'wrong',
              other_outcome: 'correct',
              cluster_key: 'late',
              trace_case_id: null,
            },
          ],
        }),
    })
    await openAt('/workbench/evals/compare?base=1&other=2')
    expect(await screen.findByText('Run #1 to #2: -10.0 points')).toBeVisible()
    expect(within(screen.getByRole('region', { name: 'Got worse' })).getByText('Got worse Q')).toBeVisible()
    expect(within(screen.getByRole('region', { name: 'Got better' })).getByText('Got better Q')).toBeVisible()
  })

  it('explains runs that cannot be compared', async () => {
    serve(true, {
      'GET /api/workbench/eval/compare': () => fail(422, 'eval_runs_not_comparable', 'No.'),
    })
    await openAt('/workbench/evals/compare?base=1&other=2')
    expect(await screen.findByText('The two runs scored different targets.')).toBeVisible()
  })
})
