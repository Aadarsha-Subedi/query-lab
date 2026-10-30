import { QueryClientProvider, useQuery } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { QueryBoundary } from '@/components/QueryBoundary'
import { createQueryClient } from '@/lib/query-client'

const STALE_TIME_MS = 0

function Widget({ name, load }: { name: string; load: () => Promise<string[]> }) {
  const query = useQuery({ queryKey: [name], queryFn: load })
  return (
    <section aria-label={name}>
      <QueryBoundary
        query={query}
        loading={<p>Loading {name}</p>}
        errorTitle={`Couldn't load ${name}.`}
        isEmpty={(items) => items.length === 0}
        empty={<p>No {name} yet</p>}
      >
        {(items) => <p>{items.join(', ')}</p>}
      </QueryBoundary>
    </section>
  )
}

function renderWidgets(widgets: { name: string; load: () => Promise<string[]> }[]) {
  render(
    <QueryClientProvider client={createQueryClient(STALE_TIME_MS)}>
      {widgets.map((widget) => (
        <Widget key={widget.name} {...widget} />
      ))}
    </QueryClientProvider>,
  )
}

describe('QueryBoundary', () => {
  it('shows loading, then the content', async () => {
    renderWidgets([{ name: 'runs', load: () => Promise.resolve(['a', 'b']) }])
    expect(screen.getByText('Loading runs').parentElement).toHaveAttribute('aria-busy', 'true')
    expect(await screen.findByText('a, b')).toBeInTheDocument()
  })

  it('shows the empty state', async () => {
    renderWidgets([{ name: 'runs', load: () => Promise.resolve([]) }])
    expect(await screen.findByText('No runs yet')).toBeInTheDocument()
  })

  it('keeps an error inside its component and retries only that component', async () => {
    const failing = vi.fn(() => Promise.reject(new Error('The server did not answer.')))
    const healthy = vi.fn(() => Promise.resolve(['ok']))
    renderWidgets([
      { name: 'runs', load: failing },
      { name: 'health', load: healthy },
    ])
    expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't load runs.")
    expect(await screen.findByText('ok')).toBeInTheDocument() // the other component is unaffected
    expect(failing).toHaveBeenCalledTimes(1) // no automatic retry

    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(failing).toHaveBeenCalledTimes(2)
    expect(healthy).toHaveBeenCalledTimes(1)
  })
})
