import type { Pending, Step } from './types'

/** The live view of one run: what the event stream has told us so far. */
export type StreamPhase =
  | 'idle'
  | 'connecting'
  | 'live'
  /** The server closed the stream because the run paused or finished. */
  | 'ended'
  /** The stream broke or timed out. Only the user reconnects (a button). */
  | 'dropped'

export type StreamState = {
  phase: StreamPhase
  steps: Step[]
  /** The newest step index seen: sent as Last-Event-ID when reconnecting. */
  lastIndex: number | null
  status: string | null
  errorCode: string
  pending: Pending | null
  /** An ApiError code when the stream could not open (e.g. agent_stream_limit). */
  failure: string | null
}

export const initialStreamState: StreamState = {
  phase: 'idle',
  steps: [],
  lastIndex: null,
  status: null,
  errorCode: '',
  pending: null,
  failure: null,
}

export type StreamAction =
  | { type: 'connecting' }
  | { type: 'opened' }
  | { type: 'step'; step: Step }
  | { type: 'status'; status: string; errorCode: string; pending: Pending | null }
  | { type: 'timeout' }
  | { type: 'dropped'; failure: string | null }
  | { type: 'reset' }

export function streamReducer(state: StreamState, action: StreamAction): StreamState {
  switch (action.type) {
    case 'connecting':
      return { ...state, phase: 'connecting', failure: null }
    case 'opened':
      return { ...state, phase: 'live' }
    case 'step': {
      // Reconnecting with Last-Event-ID should not repeat steps, but never show one twice.
      if (state.steps.some((step) => step.index === action.step.index)) return state
      const steps = [...state.steps, action.step].sort((a, b) => a.index - b.index)
      return { ...state, steps, lastIndex: Math.max(state.lastIndex ?? -1, action.step.index) }
    }
    case 'status':
      return {
        ...state,
        phase: 'ended',
        status: action.status,
        errorCode: action.errorCode,
        pending: action.pending,
      }
    case 'timeout':
      return { ...state, phase: 'dropped' }
    case 'dropped':
      return { ...state, phase: 'dropped', failure: action.failure }
    case 'reset':
      return initialStreamState
  }
}
