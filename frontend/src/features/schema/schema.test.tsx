import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { initApi } from '@/lib/api'
import { createQueryClient } from '@/lib/query-client'
import { mockFetch, TEST_BASE_URL } from '@/test/http'

import { SchemaPanel } from './SchemaPanel'
import { useSchemaPanelStore } from './store'

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

function show(workspace?: number) {
  initApi(TEST_BASE_URL)
  render(
    <QueryClientProvider client={createQueryClient(0)}>
      <SchemaPanel workspace={workspace} />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  useSchemaPanelStore.setState({ open: {} })
})
afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SchemaPanel', () => {
  it('lists tables, expands columns with keys, and filters', async () => {
    mockFetch({ '/api/schema': () => envelope({ name: 'demo', tables: [ORDERS, CUSTOMERS] }) })
    show()
    await userEvent.click(await screen.findByRole('button', { name: /^orders/ }))
    const columns = screen.getByRole('list', { name: 'orders columns' })
    expect(within(columns).getByText('PK')).toBeVisible()
    expect(within(columns).getByText('FK')).toBeVisible()

    await userEvent.type(screen.getByRole('searchbox', { name: 'Filter tables and columns' }), 'customers')
    expect(screen.queryByRole('button', { name: /^orders/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /customers/ })).toBeVisible()
  })

  it('opens the table detail from the info button', async () => {
    mockFetch({
      '/api/schema': () => envelope({ name: 'demo', tables: [ORDERS] }),
      '/api/schema/tables/orders': () => envelope(ORDERS),
    })
    show()
    await userEvent.click(await screen.findByRole('button', { name: 'Details of orders' }))
    expect(await screen.findByText('One row per order')).toBeVisible()
    expect(screen.getByText('FK to customers')).toBeVisible()
  })

  it('shows the empty state for a workspace with no tables', async () => {
    mockFetch({ '/api/schema': () => envelope({ name: 'ws', tables: [] }) })
    show(7)
    expect(await screen.findByText('No tables yet')).toBeVisible()
  })

  it('passes the workspace and shows an error with its own Try again', async () => {
    let calls = 0
    const fetchMock = mockFetch({
      '/api/schema': () => {
        calls += 1
        return calls === 1
          ? { status: 500, body: { success: false, message: 'Boom.', code: 'internal_error', errors: [] } }
          : envelope({ name: 'ws', tables: [ORDERS] })
      },
    })
    show(7)
    expect(await screen.findByText("Couldn't load the schema.")).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(await screen.findByRole('button', { name: /^orders/ })).toBeVisible()
    expect((fetchMock.mock.calls[0]?.[0] as URL).search).toBe('?workspace=7')
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
