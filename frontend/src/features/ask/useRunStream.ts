import { useCallback, useEffect, useReducer, useRef } from 'react'

import { api, ApiError } from '@/lib/api'

import { createSseParser, type SseMessage } from './sse'
import { initialStreamState, streamReducer, type StreamState } from './stream-state'
import type { Pending, Step } from './types'

type StatusPayload = { status: string; error_code: string; pending: Pending | null }

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

/**
 * Follows one run over its event stream (GET /api/agent/runs/{id}/events).
 *
 * It opens the stream once for a run, and again only when the caller asks:
 * `reconnect()` after the user approves or edits (the server closed the stream at
 * the pause) or presses "Reconnect" after a drop. It never reopens a broken stream
 * on its own, with or without a delay: the user reloads or presses the button.
 */
export function useRunStream(runId: number | null) {
  const [state, dispatch] = useReducer(streamReducer, initialStreamState)
  const abortRef = useRef<AbortController | null>(null)
  const lastIndexRef = useRef<number | null>(null)

  useEffect(() => {
    lastIndexRef.current = state.lastIndex
  }, [state.lastIndex])

  const open = useCallback(
    async (id: number) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      dispatch({ type: 'connecting' })
      try {
        const body = await api.openStream(`/api/agent/runs/${id}/events`, {
          lastEventId: lastIndexRef.current,
          signal: controller.signal,
        })
        dispatch({ type: 'opened' })
        const reader = body.getReader()
        const decoder = new TextDecoder()
        const parser = createSseParser()
        let ended = false
        for (;;) {
          const { done, value } = await reader.read()
          if (done) break
          for (const message of parser.push(decoder.decode(value, { stream: true }))) {
            ended = handle(message, dispatch) || ended
          }
        }
        // The server closes after `status` or `timeout`; anything else is a break.
        if (!ended) dispatch({ type: 'dropped', failure: null })
      } catch (error) {
        if (controller.signal.aborted) return
        dispatch({ type: 'dropped', failure: error instanceof ApiError ? error.code : 'network_error' })
      }
    },
    [dispatch],
  )

  useEffect(() => {
    dispatch({ type: 'reset' })
    lastIndexRef.current = null
    if (runId === null) return undefined
    void open(runId)
    return () => {
      abortRef.current?.abort()
    }
  }, [runId, open])

  const reconnect = useCallback(() => {
    if (runId !== null) void open(runId)
  }, [runId, open])

  return { state, reconnect } satisfies { state: StreamState; reconnect: () => void }
}

/** Applies one message; returns true when it was the server's closing `status` or `timeout`. */
function handle(
  message: SseMessage,
  dispatch: (action: import('./stream-state').StreamAction) => void,
): boolean {
  if (message.event === 'step' && isRecord(message.data)) {
    dispatch({ type: 'step', step: message.data as unknown as Step })
    return false
  }
  if (message.event === 'status' && isRecord(message.data)) {
    const payload = message.data as unknown as StatusPayload
    dispatch({
      type: 'status',
      status: payload.status,
      errorCode: payload.error_code,
      pending: payload.pending,
    })
    return true
  }
  if (message.event === 'timeout') {
    dispatch({ type: 'timeout' })
    return true
  }
  return false
}
