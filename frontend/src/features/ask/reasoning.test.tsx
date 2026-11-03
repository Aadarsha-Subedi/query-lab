import { render, screen } from '@testing-library/react'

import { Reasoning } from './Reasoning'

describe('Reasoning', () => {
  it('shows the current stage, the newest notes and the sources', () => {
    render(
      <Reasoning
        stages={['Planning the query', 'Reading the orders table']}
        reasoning={['one', 'two', 'three', 'four', 'five']}
        sources={['orders']}
      />,
    )
    expect(screen.getByRole('status')).toHaveTextContent('Reading the orders table')
    const notes = screen.getByRole('list', { name: "The agent's notes" })
    expect(notes).toHaveTextContent('five')
    expect(notes).not.toHaveTextContent('one')
    expect(screen.getByRole('list', { name: 'Tables it looked at' })).toHaveTextContent('orders')
  })

  it('reads Thought, with the step count, once the agent is done', () => {
    render(
      <Reasoning
        stages={['Planning the query', 'Running the query']}
        reasoning={['a note']}
        active={false}
      />,
    )
    expect(screen.getByRole('status')).toHaveTextContent('Thought')
    expect(screen.getByRole('status')).toHaveTextContent('2 steps')
  })

  it('shows nothing before there is a stage', () => {
    const { container } = render(<Reasoning stages={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
