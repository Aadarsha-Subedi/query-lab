import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { initApi } from '@/lib/api'
import { createQueryClient } from '@/lib/query-client'
import { TEST_BASE_URL } from '@/test/http'

import { AskBox } from './AskBox'
import { useDraftStore } from './draft-store'
import { RunView } from './RunView'

// These render without a router, so a link is just an anchor.
vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
    Link: ({ to, children, className }: { to: string; children: React.ReactNode; className?: string }) => (
      <a href={to} className={className}>
        {children}
      </a>
    ),
  }
})

const envelope = (data: unknown, status = 200) =>
  new Response(JSON.stringify({ success: true, status_code: status, message: '', meta: {}, data }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
const failure = (status: number, code: string, message: string, errors: unknown[] = []) =>
  new Response(JSON.stringify({ success: false, status_code: status, message, code, errors }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
const sse = (text: string) => new Response(text, { headers: { 'Content-Type': 'text/event-stream' } })

const PENDING = {
  sql: 'select count(*) from orders',
  rationale: 'Counting orders.',
  assumptions: ['Orders means all statuses'],
  guard: ['limit_clamped'],
  revision: 0,
  expires_at: '2026-11-01T01:00:00Z',
}
const step = (index: number, kind: string, output: string) => ({
  index,
  kind,
  tool_name: '',
  input: {},
  output,
  status: 'ok',
  error_code: '',
  input_tokens: 0,
  output_tokens: 0,
  latency_ms: 500,
  actor: 'agent',
  created_at: '2026-11-01T00:00:00Z',
})
const run = (over: Record<string, unknown> = {}) => ({
  id: 5,
  question: 'How many orders?',
  status: 'awaiting_approval',
  error_code: '',
  pending: PENDING,
  steps: [step(0, 'plan', 'Count the rows.')],
  has_result: false,
  feedback: null,
  ...over,
})

type Handler = (request: { method: string; body: unknown }) => Response
function serve(handlers: Record<string, Handler>) {
  const calls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn<typeof fetch>((input, init) => {
      const url = new URL(input instanceof Request ? input.url : input.toString())
      const method = init?.method ?? 'GET'
      const key = `${method} ${url.pathname}`
      calls.push(key)
      const handler = handlers[key]
      if (!handler) return Promise.reject(new TypeError(`No mock for ${key}`))
      const body = typeof init?.body === 'string' ? (JSON.parse(init.body) as unknown) : undefined
      return Promise.resolve(handler({ method, body }))
    }),
  )
  return calls
}

function show(ui: React.ReactElement) {
  initApi(TEST_BASE_URL)
  render(<QueryClientProvider client={createQueryClient(0)}>{ui}</QueryClientProvider>)
}

beforeEach(() => {
  useDraftStore.setState({ drafts: {} })
})
afterEach(() => {
  vi.unstubAllGlobals()
})

describe('the approval checkpoint', () => {
  it('shows the proposal, and approving asks the server then reopens the stream', async () => {
    let status = 'awaiting_approval'
    const calls = serve({
      'GET /api/agent/runs/5': () =>
        envelope(
          status === 'awaiting_approval'
            ? run()
            : run({ status: 'succeeded', pending: null, has_result: true }),
        ),
      'GET /api/agent/runs/5/events': () => sse(''),
      'POST /api/agent/runs/5/approve': () => {
        status = 'succeeded'
        return envelope(run({ status: 'running' }))
      },
      'GET /api/agent/runs/5/result': () =>
        envelope({
          run_id: 5,
          sql: 'select count(*) from orders limit 1000',
          columns: ['count'],
          rows: [[99441]],
          row_count: 1,
          truncated: false,
        }),
      'GET /api/agent/limits': () => envelope({}),
    })
    show(<RunView runId={5} />)
    expect(await screen.findByText('Counting orders.')).toBeVisible()
    expect(screen.getByText('Row limit applied')).toBeVisible()
    expect(screen.getByText('Orders means all statuses')).toBeVisible()

    await userEvent.click(screen.getByRole('button', { name: 'Approve and run' }))
    expect(await screen.findByRole('columnheader', { name: 'count' })).toBeVisible()
    expect(screen.getByRole('cell', { name: '99441' })).toBeVisible()
    expect(calls.filter((call) => call === 'GET /api/agent/runs/5/events').length).toBeGreaterThanOrEqual(2)
  })

  it('edits the SQL, keeps the paused run on a guard refusal and shows the reason under the editor', async () => {
    let body: unknown
    serve({
      'GET /api/agent/runs/5': () => envelope(run()),
      'GET /api/agent/runs/5/events': () => sse(''),
      'POST /api/agent/runs/5/edit': (request) => {
        body = request.body
        return failure(400, 'guard_rejected', 'The SQL was refused.', [
          { field: 'sql', message: 'DELETE is not allowed.' },
        ])
      },
    })
    show(<RunView runId={5} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Edit SQL' }))
    const editor = screen.getByRole('textbox', { name: 'SQL' })
    expect(editor).toHaveValue(PENDING.sql)
    await userEvent.clear(editor)
    await userEvent.type(editor, 'delete from orders')
    await userEvent.click(screen.getByRole('button', { name: 'Run my edited SQL' }))
    expect(await screen.findByText('DELETE is not allowed.')).toBeVisible()
    expect(body).toEqual({ sql: 'delete from orders' })
    expect(editor).toHaveValue('delete from orders')
    expect(screen.getByRole('button', { name: 'Run my edited SQL' })).toBeEnabled()
  })

  it('cancels the run', async () => {
    const calls = serve({
      'GET /api/agent/runs/5': () => envelope(run()),
      'GET /api/agent/runs/5/events': () => sse(''),
      'POST /api/agent/runs/5/cancel': () => envelope(run({ status: 'cancelled' })),
      'GET /api/agent/limits': () => envelope({}),
    })
    show(<RunView runId={5} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Cancel run' }))
    await waitFor(() => {
      expect(calls).toContain('POST /api/agent/runs/5/cancel')
    })
  })
})

describe('a dropped live connection', () => {
  it('offers a manual reconnect and does not reconnect on its own', async () => {
    const calls = serve({
      'GET /api/agent/runs/5': () => envelope(run({ status: 'running', pending: null })),
      'GET /api/agent/runs/5/events': () => sse(''),
    })
    show(<RunView runId={5} />)
    const button = await screen.findByRole('button', { name: 'Reconnect' })
    await new Promise((resolve) => setTimeout(resolve, 100))
    expect(calls.filter((call) => call === 'GET /api/agent/runs/5/events')).toHaveLength(1)
    await userEvent.click(button)
    await waitFor(() => {
      expect(calls.filter((call) => call === 'GET /api/agent/runs/5/events')).toHaveLength(2)
    })
  })
})

describe('failed and finished runs', () => {
  it('explains a failure by its code', async () => {
    serve({
      'GET /api/agent/runs/5': () =>
        envelope(run({ status: 'failed', error_code: 'query_timeout', pending: null })),
      'GET /api/agent/runs/5/events': () => sse(''),
    })
    show(<RunView runId={5} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('The query took too long')
  })

  it('records a thumbs-up and then reflects the server answer', async () => {
    let vote: string | null = null
    const calls = serve({
      'GET /api/agent/runs/5': () =>
        envelope(run({ status: 'succeeded', pending: null, has_result: false, feedback: vote })),
      'GET /api/agent/runs/5/events': () => sse(''),
      'PUT /api/agent/runs/5/feedback': (request) => {
        vote = (request.body as { vote: string }).vote
        return envelope({})
      },
    })
    show(<RunView runId={5} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Yes, this was right' }))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Yes, this was right' })).toHaveAttribute(
        'aria-pressed',
        'true',
      )
    })
    expect(calls).toContain('PUT /api/agent/runs/5/feedback')
  })
})

describe('AskBox', () => {
  it('sends the trimmed question with the workspace and reports the new run', async () => {
    let sent: unknown
    serve({
      'POST /api/agent/runs': (request) => {
        sent = request.body
        return envelope({ id: 9 }, 201)
      },
    })
    const onStarted = vi.fn()
    show(<AskBox workspace={3} onStarted={onStarted} />)
    await userEvent.type(screen.getByRole('textbox', { name: 'Your question' }), '  Top products?  ')
    await userEvent.click(screen.getByRole('button', { name: 'Send question' }))
    await waitFor(() => {
      expect(onStarted).toHaveBeenCalledWith(9)
    })
    expect(sent).toEqual({ question: 'Top products?', workspace: 3 })
    expect(screen.getByRole('textbox', { name: 'Your question' })).toHaveValue('')
  })

  it('sends on Enter and makes a new line on Shift+Enter', async () => {
    let sent: unknown
    serve({
      'POST /api/agent/runs': (request) => {
        sent = request.body
        return envelope({ id: 9 }, 201)
      },
    })
    const onStarted = vi.fn()
    show(<AskBox onStarted={onStarted} />)
    const box = screen.getByRole('textbox', { name: 'Your question' })
    await userEvent.type(box, 'Top{Shift>}{Enter}{/Shift}products?')
    expect(box).toHaveValue('Top\nproducts?')
    expect(onStarted).not.toHaveBeenCalled()
    await userEvent.type(box, '{Enter}')
    await waitFor(() => {
      expect(onStarted).toHaveBeenCalledWith(9)
    })
    expect(sent).toEqual({ question: 'Top\nproducts?', workspace: null })
  })

  it('keeps the text and shows the server wording on an error', async () => {
    serve({
      'POST /api/agent/runs': () => failure(429, 'agent_run_limit', 'Too many open runs.'),
    })
    show(<AskBox onStarted={vi.fn()} />)
    await userEvent.type(screen.getByRole('textbox', { name: 'Your question' }), 'Anything')
    await userEvent.click(screen.getByRole('button', { name: 'Send question' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Too many unfinished runs')
    expect(screen.getByRole('textbox', { name: 'Your question' })).toHaveValue('Anything')
  })

  it('is disabled while another run is open', () => {
    serve({})
    show(<AskBox disabled onStarted={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Send question' })).toBeDisabled()
    expect(screen.getByText('Finish or cancel your open run first.')).toBeVisible()
  })

  it('offers the keys page when the shared key is used up', async () => {
    serve({
      'POST /api/agent/runs': () => failure(429, 'default_key_limit', 'Daily limit.'),
    })
    show(<AskBox onStarted={vi.fn()} />)
    await userEvent.type(screen.getByRole('textbox', { name: 'Your question' }), 'Anything')
    await userEvent.click(screen.getByRole('button', { name: 'Send question' }))
    expect(await screen.findByRole('link', { name: 'Add your own key' })).toHaveAttribute('href', '/settings')
  })
})
