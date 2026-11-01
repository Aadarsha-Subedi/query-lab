import { QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { initApi } from '@/lib/api'
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
  max_tables: 20,
  max_columns: 30,
  max_relations: 20,
  max_rows_per_edit: 50,
}
const col = (name: string, type = 'text', over: Record<string, unknown> = {}) => ({
  name,
  type,
  nullable: true,
  description: '',
  hidden: false,
  ...over,
})
const PRODUCTS = {
  name: 'products',
  description: 'What we sell',
  row_estimate: 2,
  primary_key: ['sku'],
  columns: [
    col('_row_id', 'bigint', { hidden: true, nullable: false }),
    col('sku', 'text', { nullable: false }),
    col('price', 'numeric'),
  ],
}

function base(extra: Record<string, (request: ApiRequest) => Response> = {}) {
  return serveApi({
    'GET /api/me': () => jsonResponse(signedIn()),
    'GET /api/agent/limits': () => fail(500, 'internal_error', 'x'),
    'GET /api/workspaces': () => ok([DEMO, MINE]),
    'GET /api/workspaces/limits': () => ok(LIMITS),
    'GET /api/workspaces/7': () => ok(MINE),
    'GET /api/workspaces/7/tables': () => ok([PRODUCTS]),
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
    // Ask, Edit tables and Delete live in one menu per card (the demo only offers Ask).
    expect(screen.getAllByRole('button', { name: /^Actions for/ })).toHaveLength(2)
    expect(screen.queryByRole('button', { name: /^Delete/ })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Actions for Shop' }))
    expect(await screen.findByRole('menuitem', { name: 'Ask' })).toHaveAttribute('href', '/ask?workspace=7')
    expect(screen.getByRole('menuitem', { name: 'Edit tables' })).toBeVisible()
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

describe('table editor', () => {
  it('lists columns with the key, and shows the server reason when a type change does not fit', async () => {
    base({
      'PATCH /api/workspaces/7/tables/products/columns/price': () =>
        fail(422, 'cast_failed', 'Cannot convert.', [
          { field: null, message: 'Row 2 has "abc", which is not an integer.' },
        ]),
    })
    await openAt('/workspaces/7?table=products')
    const columns = await screen.findByRole('table', { name: 'Columns of products' })
    expect(within(columns).getByText('PK')).toBeVisible()
    expect(within(columns).queryByText('_row_id')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Edit price' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Save column' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Row 2 has "abc"')
  })

  it('creates a table from the dialog and sends the columns', async () => {
    let sent: unknown
    base({
      'POST /api/workspaces/7/tables': (request) => {
        sent = request.body
        return ok({ ...PRODUCTS, name: 'orders' }, {}, 201)
      },
    })
    await openAt('/workspaces/7')
    await userEvent.click(await screen.findByRole('button', { name: 'New table' }))
    await userEvent.type(screen.getByRole('textbox', { name: 'Table name' }), 'orders')
    await userEvent.type(screen.getByRole('textbox', { name: 'Column 1 name' }), 'id')
    await userEvent.click(screen.getByRole('button', { name: 'Create table' }))
    await waitFor(() => {
      expect(sent).toMatchObject({ name: 'orders', columns: [{ name: 'id', type: 'text', nullable: true }] })
    })
  })

  it('validates a missing table name before calling the API', async () => {
    const calls = base()
    await openAt('/workspaces/7')
    await userEvent.click(await screen.findByRole('button', { name: 'New table' }))
    await userEvent.click(screen.getByRole('button', { name: 'Create table' }))
    expect(await screen.findByText('Name the table.')).toBeVisible()
    expect(calls).not.toContain('POST /api/workspaces/7/tables')
  })

  it('shows rows without the hidden id, and marks the cell the server rejects', async () => {
    let patched: unknown
    base({
      'GET /api/workspaces/7/tables/products/rows': () =>
        ok({
          columns: [
            { name: '_row_id', type: 'bigint' },
            { name: 'sku', type: 'text' },
            { name: 'price', type: 'numeric' },
          ],
          rows: [
            [1, 'A1', '9.5'],
            [2, 'B2', '3'],
          ],
          total: 2,
        }),
      'PATCH /api/workspaces/7/tables/products/rows/1': (request) => {
        patched = request.body
        return fail(422, 'row_invalid', 'Bad value.', [{ field: 'price', message: '"abc" is not a number.' }])
      },
    })
    await openAt('/workspaces/7?table=products')
    await userEvent.click(await screen.findByRole('tab', { name: 'Rows' }))
    const grid = await screen.findByRole('table', { name: 'Rows of products' })
    expect(within(grid).queryByRole('columnheader', { name: '_row_id' })).not.toBeInTheDocument()
    expect(within(grid).getByText('A1')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Edit row 1' }))
    const price = await screen.findByLabelText(/price/)
    await userEvent.clear(price)
    await userEvent.type(price, 'abc')
    await userEvent.click(screen.getByRole('button', { name: 'Save row' }))
    expect(await screen.findByText('"abc" is not a number.')).toBeVisible()
    expect(patched).toEqual({ values: { sku: 'A1', price: 'abc' } })
  })
})

describe('relations and SQL console', () => {
  it('lists relations and reports a refused one', async () => {
    base({
      'GET /api/workspaces/7/relations': () =>
        ok([
          {
            name: 'fk_1',
            child_table: 'orders',
            child_columns: ['sku'],
            parent_table: 'products',
            parent_columns: ['sku'],
            on_delete: 'CASCADE',
          },
        ]),
      'POST /api/workspaces/7/relations': () =>
        fail(422, 'relation_invalid', 'No.', [
          { field: null, message: 'The parent columns are not a primary key.' },
        ]),
    })
    await openAt('/workspaces/7?tab=relations')
    expect(await screen.findByText('orders(sku)')).toBeVisible()
    expect(screen.getByText('on delete cascade')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Add relation' })).toBeDisabled()
  })

  it('runs SQL and shows each statement, and a failure with its statement text', async () => {
    let attempt = 0
    base({
      'POST /api/workspaces/7/sql': () => {
        attempt += 1
        return attempt === 1
          ? fail(422, 'sql_failed', 'Failed.', [
              { field: null, message: 'Statement 1: 42P01: relation "nope" does not exist' },
            ])
          : ok({
              statements: [
                {
                  index: 0,
                  command: 'SELECT 1',
                  kind: 'query',
                  row_count: 1,
                  columns: ['n'],
                  rows: [[1]],
                  truncated: false,
                },
              ],
              counts: { ddl: 0, data: 0, query: 1 },
              elapsed_ms: 12,
            })
      },
    })
    await openAt('/workspaces/7?tab=sql')
    await userEvent.type(await screen.findByRole('textbox', { name: 'SQL' }), 'select 1')
    await userEvent.click(screen.getByRole('button', { name: 'Run' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('42P01')
    await userEvent.click(screen.getByRole('button', { name: 'Run' }))
    expect(await screen.findByRole('region', { name: 'Statement 1' })).toBeVisible()
    expect(screen.getByRole('cell', { name: '1' })).toBeVisible()
  })
})
