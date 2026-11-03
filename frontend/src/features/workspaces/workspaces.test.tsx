import { QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { initApi } from '@/lib/api'
import { useQueryDraftStore } from '@/stores/query-draft'
import { createQueryClient } from '@/lib/query-client'
import { createAppRouter } from '@/router'
import { fail, jsonResponse, ok, serveApi, signedIn, TEST_BASE_URL, type ApiRequest } from '@/test/http'

const DEMO = {
  id: null,
  kind: 'demo',
  name: 'Olist demo',
  status: 'ready',
  read_only: true,
  tables: 8,
  bytes_used: 0,
  bytes_allowed: null,
  created_at: null,
}
const MINE = {
  id: 7,
  kind: 'user',
  name: 'Shop',
  status: 'ready',
  read_only: false,
  tables: 1,
  bytes_used: 1024,
  bytes_allowed: 10240,
  created_at: '2026-11-01T00:00:00Z',
}
const LIMITS = {
  workspaces: { used: 1, allowed: 3 },
  bytes: { used: 1024, allowed: 30720, per_workspace: 10240 },
  max_dump_bytes: 1048576,
}
function base(extra: Record<string, (request: ApiRequest) => Response> = {}) {
  return serveApi({
    'GET /api/me': () => jsonResponse(signedIn()),
    'GET /api/agent/limits': () => fail(500, 'internal_error', 'x'),
    'GET /api/workspaces': () => ok([DEMO, MINE]),
    'GET /api/workspaces/limits': () => ok(LIMITS),
    'GET /api/workspaces/7': () => ok(MINE),
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
  useQueryDraftStore.setState({ drafts: {} })
})

describe('workspace list', () => {
  it('shows the demo as read only and your workspace with its storage', async () => {
    base()
    await openAt('/workspaces')
    expect(await screen.findByText('Shared · read only')).toBeVisible()
    expect(screen.getByRole('meter', { name: 'Storage used in Shop' })).toHaveAttribute(
      'aria-valuenow',
      '1024',
    )
    expect(screen.getByText('1 of 3 private workspaces used.')).toBeVisible()
    // The card itself opens the workspace: its schema for yours, the schema for the shared demo.
    expect(screen.getByRole('link', { name: 'Shop' })).toHaveAttribute('href', '/ask?tab=schema&workspace=7')
    expect(screen.getByRole('link', { name: /Olist demo/ })).toHaveAttribute('href', '/ask?tab=schema')
    // Ask, Import a dump and Delete live in one menu per card (the demo only offers Ask).
    expect(screen.getAllByRole('button', { name: /^Actions for/ })).toHaveLength(2)
    expect(screen.queryByRole('button', { name: /^Delete/ })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Actions for Shop' }))
    expect(await screen.findByRole('menuitem', { name: 'Ask' })).toHaveAttribute('href', '/ask?workspace=7')
    expect(screen.getByRole('menuitem', { name: 'Import a dump' })).toBeVisible()
    expect(screen.getByRole('menuitem', { name: 'Delete workspace' })).toBeVisible()
  })

  it('creates a workspace and shows the server message under the field when the name is taken', async () => {
    let attempt = 0
    base({
      'POST /api/workspaces': () => {
        attempt += 1
        return attempt === 1
          ? fail(409, 'workspace_name_taken', 'Taken.', [
              { field: 'name', message: 'You already have a workspace named Shop.' },
            ])
          : ok({ ...MINE, id: 8, name: 'Shop 2' }, {}, 201)
      },
    })
    await openAt('/workspaces')
    await userEvent.click(await screen.findByRole('button', { name: 'New workspace' }))
    await userEvent.type(screen.getByRole('textbox', { name: 'Name' }), 'Shop')
    await userEvent.click(screen.getByRole('button', { name: 'Create' }))
    expect(await screen.findByText('You already have a workspace named Shop.')).toBeVisible()
    await userEvent.clear(screen.getByRole('textbox', { name: 'Name' }))
    await userEvent.type(screen.getByRole('textbox', { name: 'Name' }), 'Shop 2')
    await userEvent.click(screen.getByRole('button', { name: 'Create' }))
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  it('disables creating at the cap', async () => {
    base({ 'GET /api/workspaces/limits': () => ok({ ...LIMITS, workspaces: { used: 3, allowed: 3 } }) })
    await openAt('/workspaces')
    expect(await screen.findByText(/at the limit/)).toBeVisible()
    expect(screen.getByRole('button', { name: 'New workspace' })).toBeDisabled()
  })

  it('needs the typed name before it deletes', async () => {
    const calls = base({ 'DELETE /api/workspaces/7': () => ok(null) })
    await openAt('/workspaces')
    await userEvent.click(await screen.findByRole('button', { name: 'Actions for Shop' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Delete workspace' }))
    const confirm = await screen.findByRole('button', { name: 'Delete workspace' })
    expect(confirm).toBeDisabled()
    await userEvent.type(screen.getByRole('textbox', { name: 'Type the workspace name' }), 'Shop')
    await userEvent.click(confirm)
    await waitFor(() => {
      expect(calls).toContain('DELETE /api/workspaces/7')
    })
  })
})

describe('tabs inside the Ask page', () => {
  it('gives a private workspace Ask and Schema, with a three-dots menu of storage, import and query', async () => {
    base({ 'GET /api/schema': () => ok({ name: 'ws_7', tables: [] }) })
    await openAt('/ask?workspace=7&tab=schema')
    const tabs = await screen.findAllByRole('tab')
    expect(tabs.map((tab) => tab.textContent)).toEqual(['Ask', 'Schema'])
    await userEvent.click(await screen.findByRole('button', { name: 'Workspace actions' }))
    expect((await screen.findAllByRole('menuitem')).map((item) => item.textContent)).toEqual([
      'View storage capacity',
      'Import dump',
      'Run query',
    ])
  })

  it('opens Schema for an old Import or Query link', async () => {
    base({ 'GET /api/schema': () => ok({ name: 'ws_7', tables: [] }) })
    await openAt('/ask?workspace=7&tab=import')
    expect(await screen.findByRole('tab', { name: 'Schema' })).toHaveAttribute('aria-selected', 'true')
  })

  it('gives the shared demo Ask and Schema with no import or query', async () => {
    base({ 'GET /api/schema': () => ok({ name: 'demo', tables: [] }) })
    const router = await openAt('/ask?tab=import')
    const tabs = await screen.findAllByRole('tab')
    expect(tabs.map((tab) => tab.textContent)).toEqual(['Ask', 'Schema'])
    expect(screen.getByRole('tab', { name: 'Schema' })).toHaveAttribute('aria-selected', 'true')
    expect(router.state.location.pathname).toBe('/ask')
    expect(screen.queryByRole('button', { name: 'Workspace actions' })).not.toBeInTheDocument()
  })

  it('sends an old edit link to the same workspace on Schema', async () => {
    base({ 'GET /api/schema': () => ok({ name: 'ws_7', tables: [] }) })
    const router = await openAt('/workspaces/7?tab=relations')
    await screen.findByRole('tab', { name: 'Schema' })
    expect(router.state.location.pathname).toBe('/ask')
    expect(router.state.location.search).toMatchObject({ workspace: 7, tab: 'schema' })
  })
})

class FakeUpload {
  static puts: { url: string; size: number }[] = []
  upload: {
    onprogress: ((event: { lengthComputable: boolean; loaded: number; total: number }) => void) | null
  } = {
    onprogress: null,
  }
  status = 200
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  private url = ''
  open(_method: string, url: string) {
    this.url = url
  }
  send(file: File) {
    FakeUpload.puts.push({ url: this.url, size: file.size })
    this.upload.onprogress?.({ lengthComputable: true, loaded: file.size, total: file.size })
    this.onload?.()
  }
}

const JOB = {
  id: 5,
  workspace_id: 7,
  status: 'queued',
  replace: false,
  size_bytes: 20,
  statements_run: 0,
  tables_created: 0,
  error: null,
  created_at: '2026-11-02T00:00:00Z',
  updated_at: '2026-11-02T00:00:00Z',
}

async function choosePanel(item: string) {
  await userEvent.click(await screen.findByRole('button', { name: 'Workspace actions' }))
  await userEvent.click(await screen.findByRole('menuitem', { name: item }))
}

describe('dump import', () => {
  beforeEach(() => {
    FakeUpload.puts = []
    vi.stubGlobal('XMLHttpRequest', FakeUpload)
  })

  async function choose(name: string, content = 'CREATE TABLE t (a int);') {
    if (!screen.queryByLabelText('SQL dump file')) await choosePanel('Import dump')
    const input = await screen.findByLabelText('SQL dump file')
    await userEvent.upload(input, new File([content], name, { type: 'application/sql' }))
  }

  it('uploads straight to the bucket, starts the job and shows what was imported', async () => {
    base({
      'GET /api/workspaces/7/imports': () => ok([]),
      'POST /api/workspaces/7/imports': (request) => {
        expect(request.body).toEqual({ filename: 'shop.sql', size: 23, replace: false })
        return ok({
          ...JOB,
          status: 'awaiting_upload',
          upload_url: 'https://r2.test/put',
          upload_expires_in: 900,
          max_bytes: 1048576,
        })
      },
      'POST /api/workspaces/7/imports/5/start': () => ok(JOB),
      'GET /api/workspaces/7/imports/5': () =>
        ok({ ...JOB, status: 'succeeded', statements_run: 4, tables_created: 2 }),
    })
    await openAt('/ask?workspace=7&tab=schema')
    await choose('shop.sql')
    await userEvent.click(screen.getByRole('button', { name: 'Import' }))
    expect(await screen.findByText(/Imported 2 tables/)).toBeVisible()
    expect(FakeUpload.puts).toEqual([{ url: 'https://r2.test/put', size: 23 }])
  })

  it('shows the failing statement and line, and says nothing was changed', async () => {
    base({
      'GET /api/workspaces/7/imports': () => ok([]),
      'POST /api/workspaces/7/imports': () =>
        ok({
          ...JOB,
          status: 'awaiting_upload',
          upload_url: 'https://r2.test/put',
          upload_expires_in: 900,
          max_bytes: 1048576,
        }),
      'POST /api/workspaces/7/imports/5/start': () => ok(JOB),
      'GET /api/workspaces/7/imports/5': () =>
        ok({
          ...JOB,
          status: 'failed',
          error: { code: 'dump_refused', message: 'Extensions are not allowed.', statement: 12, line: 340 },
        }),
    })
    await openAt('/ask?workspace=7&tab=schema')
    await choose('shop.sql')
    await userEvent.click(screen.getByRole('button', { name: 'Import' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Statement 12, line 340.')
    expect(alert).toHaveTextContent('Extensions are not allowed.')
    expect(alert).toHaveTextContent('Nothing was changed')
  })

  it('refuses a file that is not .sql, and one over the limit, before uploading', async () => {
    base({ 'GET /api/workspaces/7/imports': () => ok([]) })
    await openAt('/ask?workspace=7&tab=schema')
    await choose('notes.txt')
    expect(await screen.findByText(/Choose a .sql or .sql.gz file/)).toBeVisible()
    expect(screen.getByRole('button', { name: 'Import' })).toBeDisabled()
    await choose('big.sql', 'x'.repeat(1048577))
    expect(await screen.findByText(/The limit is 1 MB/)).toBeVisible()
    expect(FakeUpload.puts).toEqual([])
  })

  it('offers Replace only when the workspace already has tables', async () => {
    base({ 'GET /api/workspaces/7/imports': () => ok([]) })
    await openAt('/ask?workspace=7&tab=schema')
    await choosePanel('Import dump')
    expect(await screen.findByLabelText(/Replace the tables already here/)).toBeVisible()
  })
})

describe('query runner', () => {
  it('runs read-only SQL and shows each statement, and a failure with its statement text', async () => {
    let attempt = 0
    base({
      'GET /api/schema': () => ok({ name: 'ws_7', tables: [] }),
      'POST /api/workspaces/7/sql': () => {
        attempt += 1
        return attempt === 1
          ? fail(422, 'sql_failed', 'Failed.', [
              { field: null, message: 'Statement 1: 42P01: relation "nope" does not exist' },
            ])
          : ok({
              statements: [
                {
                  index: 1,
                  command: 'SELECT 1',
                  row_count: 1,
                  columns: ['n'],
                  rows: [[1]],
                  truncated: false,
                },
              ],
              elapsed_ms: 12,
            })
      },
    })
    await openAt('/ask?workspace=7&tab=schema')
    await choosePanel('Run query')
    await userEvent.type(await screen.findByRole('textbox', { name: 'SQL' }), 'select 1')
    await userEvent.click(screen.getByRole('button', { name: 'Run' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('42P01')
    await userEvent.click(screen.getByRole('button', { name: 'Run' }))
    expect(await screen.findByRole('region', { name: 'Statement 1' })).toBeVisible()
    expect(screen.getByRole('cell', { name: '1' })).toBeVisible()
  })
})

describe('workspace menu', () => {
  it('shows storage in a modal', async () => {
    base({ 'GET /api/schema': () => ok({ name: 'ws_7', tables: [] }) })
    await openAt('/ask?workspace=7&tab=schema')
    await choosePanel('View storage capacity')
    const dialog = await screen.findByRole('dialog', { name: 'Storage capacity' })
    expect(within(dialog).getByText(/All your workspaces/)).toBeVisible()
    expect(await within(dialog).findByText('1 of 3')).toBeVisible()
  })

  it('keeps the last query when the sheet is closed and opened again', async () => {
    base({ 'GET /api/schema': () => ok({ name: 'ws_7', tables: [] }) })
    await openAt('/ask?workspace=7&tab=schema')
    await choosePanel('Run query')
    await userEvent.type(await screen.findByRole('textbox', { name: 'SQL' }), 'select 42')
    await userEvent.keyboard('{Escape}')
    await waitFor(() => {
      expect(screen.queryByRole('textbox', { name: 'SQL' })).not.toBeInTheDocument()
    })
    await choosePanel('Run query')
    expect(await screen.findByRole('textbox', { name: 'SQL' })).toHaveValue('select 42')
  })
})
