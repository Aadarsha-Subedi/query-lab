import type { Step } from './types'

/** One agent step in plain words: what it was doing, what it found, and which table it looked at. */
export type StepText = {
  /** What the agent was doing ("Reading the orders table"). */
  stage: string
  /** What it found or decided, in a sentence or two. Never raw JSON. */
  note: string | null
  /** A table the step looked at, shown as a source. */
  source: string | null
}

type Json = Record<string, unknown>

function parse(text: string): Json | null {
  const trimmed = text.trim()
  if (!trimmed.startsWith('{')) return null
  try {
    const value: unknown = JSON.parse(trimmed)
    return typeof value === 'object' && value !== null && !Array.isArray(value) ? (value as Json) : null
  } catch {
    return null
  }
}

const str = (value: unknown): string | null =>
  typeof value === 'string' && value.trim() ? value.trim() : null
const list = (value: unknown): unknown[] => (Array.isArray(value) ? value : [])
const count = (n: number, one: string, many: string) => `${n.toLocaleString('en-US')} ${n === 1 ? one : many}`

/** Text that is not JSON can be shown as it is; JSON the app does not know is dropped. */
function plain(output: string): string | null {
  const trimmed = output.trim()
  if (!trimmed || trimmed.startsWith('{') || trimmed.startsWith('[')) return null
  return trimmed
}

function input(step: Step): Json {
  return step.input
}

function tool(step: Step): StepText {
  const data = parse(step.output)
  const given = input(step)
  switch (step.tool_name) {
    case 'list_tables': {
      const n = list(data?.tables).length
      return {
        stage: 'Looking at the tables',
        note: n ? `Found ${count(n, 'table', 'tables')}.` : null,
        source: null,
      }
    }
    case 'describe_table': {
      const table = str(data?.table) ?? str(given.table)
      const n = list(data?.columns).length
      return {
        stage: table ? `Reading the ${table} table` : 'Reading a table',
        note: n ? `${count(n, 'column', 'columns')}.` : plain(step.output),
        source: table,
      }
    }
    case 'sample_values': {
      const table = str(data?.table) ?? str(given.table)
      const column = str(data?.column) ?? str(given.column)
      const values = list(data?.values).filter((v): v is string => typeof v === 'string')
      return {
        stage: column ? `Checking the values of ${column}` : 'Checking values',
        note: values.length
          ? `Common values: ${values.slice(0, 5).join(', ')}.`
          : (str(data?.note) ?? plain(step.output)),
        source: table,
      }
    }
    case 'propose_sql':
      return { stage: 'Drafting the SQL', note: str(data?.rationale) ?? plain(step.output), source: null }
    case 'finish':
      return { stage: 'Writing the answer', note: str(data?.answer) ?? str(given.answer), source: null }
    case 'give_up':
      return { stage: 'Stopping here', note: str(data?.reason) ?? str(given.reason), source: null }
    default:
      return { stage: 'Using a tool', note: plain(step.output), source: null }
  }
}

export function describeStep(step: Step): StepText {
  switch (step.kind) {
    case 'plan':
      return { stage: 'Planning the query', note: plain(step.output), source: null }
    case 'tool':
      return tool(step)
    case 'approval':
      return step.actor === 'user'
        ? { stage: 'You approved the SQL', note: null, source: null }
        : { stage: 'Waiting for your approval', note: null, source: null }
    case 'execute': {
      const data = parse(step.output)
      const rows = typeof data?.row_count === 'number' ? data.row_count : null
      const cut = data?.truncated === true ? ' The result was cut short.' : ''
      return {
        stage: 'Running the query',
        note: rows === null ? plain(step.output) : `Got ${count(rows, 'row', 'rows')}.${cut}`,
        source: null,
      }
    }
    case 'reflect': {
      const data = parse(step.output)
      const verdict = str(data?.verdict)
      const reason = str(data?.reason)
      const lead = verdict === 'ok' ? 'Looks right.' : verdict ? 'Needs another try.' : null
      return {
        stage: 'Checking the result',
        note: [lead, reason].filter(Boolean).join(' ') || plain(step.output),
        source: null,
      }
    }
    case 'final':
      return { stage: 'Finished', note: plain(step.output), source: null }
    default:
      return { stage: 'Working', note: plain(step.output), source: null }
  }
}
