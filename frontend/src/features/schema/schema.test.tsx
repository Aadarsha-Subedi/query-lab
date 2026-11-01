import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { initApi } from '@/lib/api'
import { createQueryClient } from '@/lib/query-client'
import { mockFetch, TEST_BASE_URL } from '@/test/http'

import { SchemaPanel } from './SchemaPanel'

const envelope = (data: unknown) => ({
  status: 200,
  body: { success: true, status_code: 200, message: '', meta: {}, data },
})

const ORDERS = {
  name: 'orders',
  comment: 'One row per order',
  row_estimate: 99441,
  primary_key: ['order_id'],
  foreign_keys: [{ columns: ['customer_id'], ref_table: 'customers', ref_columns: ['customer_id'] }],
  columns: [
    { name: 'order_id', type: 'text', nullable: false, comment: '', samples: [] },
    { name: 'customer_id', type: 'text', nullable: false, comment: 'Who ordered', samples: [] },
  ],
}
const CUSTOMERS = { ...ORDERS, name: 'customers', foreign_keys: [], columns: [ORDERS.columns[0]] }

function show(workspace?: number, table?: string, onSelect: (name: string) => void = () => undefined) {
  initApi(TEST_BASE_URL)
  render(
    <QueryClientProvider client={createQueryClient(0)}>
      <SchemaPanel workspace={workspace} table={table} onSelect={onSelect} />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

const ROWS = {
  columns: ['order_id', 'customer_id'],
  rows: [
    ['o1', 'c1'],
    ['o2', null],
  ],
  offset: 0,
  limit: 2,
  has_more: true,
  row_estimate: 99441,
}

describe('SchemaPanel', () => {
  it('opens the first table with its metadata, column headers and rows', async () => {
    mockFetch({
      '/api/schema': () => envelope({ name: 'demo', tables: [ORDERS, CUSTOMERS] }),
      '/api/schema/tables/orders/rows': () => envelope(ROWS),
    })
    show()
    const section = await screen.findByRole('region', { name: 'Table orders' })
    expect(within(section).getByText('One row per order')).toBeVisible()
    expect(within(section).getByText('Primary key')).toBeVisible()
    expect(section).toHaveTextContent('customer_id to customers(customer_id)')
    const table = await within(section).findByRole('table')
    expect(within(table).getAllByRole('columnheader')).toHaveLength(2)
    expect(within(table).getByText('PK')).toBeVisible()
    expect(within(table).getByText('FK')).toBeVisible()
    expect(within(table).getByText('o1')).toBeVisible()
    expect(within(table).getByText('null')).toBeVisible()
    expect(within(section).getByText(/of about 99,441/)).toBeVisible()
  })

  it('shows the table you pick in the list, and filters the list', async () => {
    const picked = vi.fn()
    mockFetch({
      '/api/schema': () => envelope({ name: 'demo', tables: [ORDERS, CUSTOMERS] }),
      '/api/schema/tables/orders/rows': () => envelope(ROWS),
      '/api/schema/tables/customers/rows': () => envelope({ ...ROWS, columns: ['order_id'], rows: [['x']] }),
    })
    show(undefined, 'customers', picked)
    const section = await screen.findByRole('region', { name: 'Table customers' })
    expect(await within(section).findByText('x')).toBeVisible()
    await userEvent.click(
      within(screen.getByRole('list', { name: 'Tables' })).getByRole('button', { name: /^orders/ }),
    )
    expect(picked).toHaveBeenCalledWith('orders')
    await userEvent.type(screen.getByRole('searchbox'), 'zzz')
    expect(screen.getByText('No match')).toBeVisible()
  })

  it('pages with Next and asks for the next offset', async () => {
    const asked: string[] = []
    const fetchMock = mockFetch({
      '/api/schema': () => envelope({ name: 'demo', tables: [ORDERS] }),
      '/api/schema/tables/orders/rows': () => envelope(ROWS),
    })
    show()
    await userEvent.click(await screen.findByRole('button', { name: 'Next' }))
    await screen.findByRole('table')
    for (const call of fetchMock.mock.calls)
      asked.push(call[0] instanceof Request ? call[0].url : call[0].toString())
    expect(asked.some((url) => url.includes('/rows?offset=2'))).toBe(true)
  })

  it('shows the empty state for a workspace with no tables', async () => {
    mockFetch({ '/api/schema': () => envelope({ name: 'ws', tables: [] }) })
    show(7)
    expect(await screen.findByText('No tables yet')).toBeVisible()
  })

  it('shows an empty table as No rows', async () => {
    mockFetch({
      '/api/schema': () => envelope({ name: 'demo', tables: [ORDERS] }),
      '/api/schema/tables/orders/rows': () => envelope({ ...ROWS, rows: [], has_more: false }),
    })
    show()
    expect(await screen.findByText('No rows')).toBeVisible()
  })

  it('passes the workspace and shows an error with its own Try again', async () => {
    let calls = 0
    mockFetch({
      '/api/schema': () => {
        calls += 1
        return calls === 1
          ? { status: 500, body: { success: false, message: 'Boom.', code: 'internal_error', errors: [] } }
          : envelope({ name: 'ws', tables: [ORDERS] })
      },
      '/api/schema/tables/orders/rows': () => envelope(ROWS),
    })
    show(7)
    expect(await screen.findByText("Couldn't load the schema.")).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(await screen.findByRole('region', { name: 'Table orders' })).toBeVisible()
  })
})
