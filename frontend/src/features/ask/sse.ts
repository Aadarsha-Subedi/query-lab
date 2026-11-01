/*
 * A small Server-Sent Events parser for a fetch body. The server sends
 * `id:`, `event:` and `data:` lines, a blank line between messages and
 * `: heartbeat` comments while idle (agent/stream.py).
 */
export type SseMessage = { event: string; id: number | null; data: unknown }

const MESSAGE_BREAK = '\n\n'

export function createSseParser() {
  let buffer = ''
  return {
    /** Feed a decoded chunk; returns the messages it completed. */
    push(text: string): SseMessage[] {
      buffer += text.replaceAll('\r\n', '\n')
      const messages: SseMessage[] = []
      let end = buffer.indexOf(MESSAGE_BREAK)
      while (end !== -1) {
        const block = buffer.slice(0, end)
        buffer = buffer.slice(end + MESSAGE_BREAK.length)
        const message = parseBlock(block)
        if (message) messages.push(message)
        end = buffer.indexOf(MESSAGE_BREAK)
      }
      return messages
    },
  }
}

function parseBlock(block: string): SseMessage | null {
  let event = 'message'
  let id: number | null = null
  const data: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith(':')) continue // comment / heartbeat
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    const value = colon === -1 ? '' : line.slice(colon + 1).replace(/^ /, '')
    if (field === 'event') event = value
    else if (field === 'id') id = Number.isFinite(Number(value)) && value !== '' ? Number(value) : null
    else if (field === 'data') data.push(value)
  }
  if (data.length === 0) return null
  try {
    return { event, id, data: JSON.parse(data.join('\n')) as unknown }
  } catch {
    return null
  }
}
