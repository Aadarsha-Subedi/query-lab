import { Time04Icon } from '@hugeicons/core-free-icons'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { EmptyState, ErrorState } from '@/components/ui/data-state'

describe('ErrorState', () => {
  it('announces the error and retries only when asked', async () => {
    const onRetry = vi.fn()
    render(
      <ErrorState
        title="Couldn't load run history."
        description="Try again, or refresh the page."
        requestId="4f1c9a2e"
        onRetry={onRetry}
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent("Couldn't load run history.")
    expect(screen.getByText('Request 4f1c9a2e')).toBeInTheDocument()
    expect(onRetry).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('shows the retry in progress on its button', () => {
    render(<ErrorState title="Failed." description="Try again." onRetry={() => undefined} retrying />)
    expect(screen.getByRole('button', { name: 'Try again' })).toHaveAttribute('aria-busy', 'true')
  })
})

describe('EmptyState', () => {
  it('names what will appear and offers one next step', () => {
    render(
      <EmptyState
        icon={Time04Icon}
        title="No runs yet"
        description="Questions you ask appear here."
        action={<button type="button">Ask a question</button>}
      />,
    )
    expect(screen.getByText('No runs yet')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ask a question' })).toBeInTheDocument()
  })
})
