import { act, renderHook, waitFor } from '@testing-library/react'

import { initApi } from '@/lib/api'
import { TEST_BASE_URL } from '@/test/http'

import { createSseParser } from './sse'
import { initialStreamState, streamReducer } from './stream-state'
import type { Step } from './types'
import { useRunStream } from './useRunStream'

const step = (index: number): Step => ({
  index,
  kind: 'tool',
  tool_name: 'list_tables',
  input: {},
  output: 'ok',
  status: 'ok',
  error_code: '',
  input_tokens: 0,
  output_tokens: 0,
  latency_ms: 1,
  actor: 'agent',
  created_at: '2026-11-01T00:00:00Z',
})

const frame = (event: string, data: unknown, id?: number) =>
  `${id === undefined ? '' : `id: ${id}\n`}event: ${event}\ndata: ${JSON.stringify(data)}\n\n`

describe('SSE parser', () => {
  it('parses messages split across chunks and skips heartbeats', () => {
    const parser = createSseParser()
    const text = `: heartbeat\n\n${frame('step', { a: 1 }, 3)}`
    expect(parser.push(text.slice(0, 20))).toEqual([])
    expect(parser.push(text.slice(20))).toEqual([{ event: 'step', id: 3, data: { a: 1 } }])
  })

  it('handles CRLF and ignores a message with no data', () => {
    const parser = createSseParser()
    expect(parser.push('event: step\r\nid: 1\r\ndata: {"x":2}\r\n\r\n')).toEqual([
      { event: 'step', id: 1, data: { x: 2 } },
    ])
    expect(parser.push('event: step\n\n')).toEqual([])
  })
})

describe('stream reducer', () => {
  it('collects steps in order, never twice', () => {
    let state = streamReducer(initialStreamState, { type: 'step', step: step(2) })
    state = streamReducer(state, { type: 'step', step: step(1) })
    state = streamReducer(state, { type: 'step', step: step(2) })
    expect(state.steps.map((item) => item.index)).toEqual([1, 2])
    expect(state.lastIndex).toBe(2)
  })

  it('ends on status, drops on timeout or failure, and resets', () => {
    const ended = streamReducer(initialStreamState, {
      type: 'status',
      status: 'awaiting_approval',
      errorCode: '',
      pending: null,
    })
    expect(ended.phase).toBe('ended')
    expect(streamReducer(ended, { type: 'timeout' }).phase).toBe('dropped')
    expect(streamReducer(ended, { type: 'dropped', failure: 'agent_stream_limit' })).toMatchObject({
      phase: 'dropped',
      failure: 'agent_stream_limit',
    })
    expect(streamReducer(ended, { type: 'reset' })).toEqual(initialStreamState)
  })
})

function sseResponse(chunks: string[], init: { status?: number } = {}) {
  const encoder = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
  return new Response(stream, {
    status: init.status ?? 200,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useRunStream', () => {
  it('follows steps to a pause and reopens with Last-Event-ID only when asked', async () => {
    initApi(TEST_BASE_URL)
    const pending = {
      sql: 'select 1',
      rationale: 'r',
      assumptions: [],
      guard: [],
      revision: 0,
      expires_at: '2026-11-01T01:00:00Z',
    }
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        sseResponse([
          frame('step', step(0), 0),
          frame('step', step(1), 1),
          frame('status', { status: 'awaiting_approval', error_code: '', pending }),
        ]),
      )
      .mockResolvedValueOnce(
        sseResponse([
          frame('step', step(2), 2),
          frame('status', { status: 'succeeded', error_code: '', pending: null }),
        ]),
      )
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useRunStream(5))
    await waitFor(() => {
      expect(result.current.state.phase).toBe('ended')
    })
    expect(result.current.state.status).toBe('awaiting_approval')
    expect(result.current.state.pending?.sql).toBe('select 1')
    expect(result.current.state.lastIndex).toBe(1)
    expect(fetchMock).toHaveBeenCalledTimes(1)

    act(() => {
      result.current.reconnect()
    })
    await waitFor(() => {
      expect(result.current.state.status).toBe('succeeded')
    })
    const headers = fetchMock.mock.calls[1]?.[1]?.headers as Record<string, string>
    expect(headers['Last-Event-ID']).toBe('1')
    expect(result.current.state.steps).toHaveLength(3)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('drops when the stream breaks, and does not reconnect by itself', async () => {
    initApi(TEST_BASE_URL)
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(sseResponse([frame('step', step(0), 0)]))
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useRunStream(5))
    await waitFor(() => {
      expect(result.current.state.phase).toBe('dropped')
    })
    await new Promise((resolve) => setTimeout(resolve, 100))
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('reports the stream-limit error instead of opening', async () => {
    initApi(TEST_BASE_URL)
    vi.stubGlobal(
      'fetch',
      vi
        .fn<typeof fetch>()
        .mockResolvedValue(
          new Response(
            JSON.stringify({
              success: false,
              message: 'Busy',
              code: 'agent_stream_limit',
              retry_after_seconds: null,
            }),
            { status: 429, headers: { 'Content-Type': 'application/json' } },
          ),
        ),
    )
    const { result } = renderHook(() => useRunStream(5))
    await waitFor(() => {
      expect(result.current.state.failure).toBe('agent_stream_limit')
    })
    expect(result.current.state.phase).toBe('dropped')
  })

  it('does nothing without a run', () => {
    const fetchMock = vi.fn<typeof fetch>()
    vi.stubGlobal('fetch', fetchMock)
    renderHook(() => useRunStream(null))
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
