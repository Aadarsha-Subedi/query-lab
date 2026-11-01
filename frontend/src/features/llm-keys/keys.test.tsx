import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { initApi } from '@/lib/api'
import { createQueryClient } from '@/lib/query-client'
import { fail, ok, serveApi, TEST_BASE_URL } from '@/test/http'

import { KeysPage } from './KeysPage'

function show() {
  initApi(TEST_BASE_URL)
  render(
    <QueryClientProvider client={createQueryClient(0)}>
      <KeysPage />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('KeysPage', () => {
  it('shows what is saved without ever showing a key', async () => {
    serveApi({ 'GET /api/llm-keys': () => ok([{ provider: 'openai', key_last4: 'wxyz', model: 'gpt-x' }]) })
    show()
    expect(await screen.findByText('Ends in wxyz. Model: gpt-x.')).toBeVisible()
    expect(screen.getByText('Key saved')).toBeVisible()
    expect(screen.getByText('No key')).toBeVisible()
    expect(screen.getByLabelText('Replace the OpenAI key')).toHaveAttribute('type', 'password')
  })

  it('saves a key, sends the model or null, and clears the field', async () => {
    let sent: unknown
    serveApi({
      'GET /api/llm-keys': () => ok([]),
      'PUT /api/llm-keys/gemini': (request) => {
        sent = request.body
        return ok({ provider: 'gemini', key_last4: '1234', model: 'm' })
      },
      'GET /api/agent/limits': () => ok({}),
    })
    show()
    const field = await screen.findByLabelText('Google Gemini API key')
    await userEvent.type(field, '  secret-key-1234  ')
    await userEvent.click(screen.getAllByRole('button', { name: 'Save key' })[0] as HTMLElement)
    await waitFor(() => {
      expect(field).toHaveValue('')
    })
    expect(sent).toEqual({ api_key: 'secret-key-1234', model: null })
  })

  it('shows the provider refusing a key and keeps the field for correction', async () => {
    serveApi({
      'GET /api/llm-keys': () => ok([]),
      'PUT /api/llm-keys/gemini': () => fail(400, 'llm_invalid_key', 'The key was rejected.'),
    })
    show()
    const field = await screen.findByLabelText('Google Gemini API key')
    await userEvent.type(field, 'bad-key-value')
    await userEvent.click(screen.getAllByRole('button', { name: 'Save key' })[0] as HTMLElement)
    expect(await screen.findByRole('alert')).toHaveTextContent('The provider rejected the key')
    expect(field).toHaveValue('bad-key-value')
  })

  it('removes a key', async () => {
    const calls = serveApi({
      'GET /api/llm-keys': () => ok([{ provider: 'gemini', key_last4: '1234', model: 'm' }]),
      'DELETE /api/llm-keys/gemini': () => ok(null),
      'GET /api/agent/limits': () => ok({}),
    })
    show()
    await userEvent.click(await screen.findByRole('button', { name: 'Remove Google Gemini key' }))
    await waitFor(() => {
      expect(calls).toContain('DELETE /api/llm-keys/gemini')
    })
  })
})
