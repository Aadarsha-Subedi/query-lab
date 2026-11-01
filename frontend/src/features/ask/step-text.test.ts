import { describeStep } from './step-text'
import type { Step } from './types'

const step = (over: Partial<Step>): Step => ({
  index: 0,
  kind: 'plan',
  tool_name: '',
  input: {},
  output: '',
  status: 'ok',
  error_code: '',
  input_tokens: 0,
  output_tokens: 0,
  latency_ms: 0,
  actor: 'agent',
  created_at: '2026-11-01T00:00:00Z',
  ...over,
})

describe('describeStep', () => {
  it('turns a table description into a sentence and a source, never JSON', () => {
    const text = describeStep(
      step({
        kind: 'tool',
        tool_name: 'describe_table',
        output: JSON.stringify({ table: 'orders', columns: [{ name: 'a' }, { name: 'b' }], primary_key: [] }),
      }),
    )
    expect(text).toEqual({ stage: 'Reading the orders table', note: '2 columns.', source: 'orders' })
  })

  it('reads the reflect verdict', () => {
    const text = describeStep(
      step({ kind: 'reflect', output: JSON.stringify({ verdict: 'ok', reason: 'Counts the right rows.' }) }),
    )
    expect(text.note).toBe('Looks right. Counts the right rows.')
  })

  it('counts the rows of an execute step without showing them', () => {
    const text = describeStep(
      step({
        kind: 'execute',
        output: JSON.stringify({ row_count: 1, truncated: false, preview: [['secret']] }),
      }),
    )
    expect(text.note).toBe('Got 1 row.')
  })

  it('shows plain text as it is and drops JSON it does not know', () => {
    expect(describeStep(step({ kind: 'plan', output: 'Count the orders.' })).note).toBe('Count the orders.')
    expect(describeStep(step({ kind: 'tool', tool_name: 'brand_new', output: '{"x":1}' })).note).toBeNull()
  })

  it('tells a user approval from the wait for it', () => {
    expect(describeStep(step({ kind: 'approval', actor: 'user' })).stage).toBe('You approved the SQL')
    expect(describeStep(step({ kind: 'approval', actor: 'agent' })).stage).toBe('Waiting for your approval')
  })
})
