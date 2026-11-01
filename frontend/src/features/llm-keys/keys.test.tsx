import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
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

const MODELS = { gemini: ['gem-a', 'gem-b'], openai: ['gpt-a', 'gpt-b'] }
const key = (provider: string, over: Record<string, unknown> = {}) => ({
  provider,
  key_last4: 'wxyz',
  model: provider === 'openai' ? 'gpt-a' : 'gem-a',
  is_active: false,
  updated_at: '2026-11-01T10:00:00Z',
  ...over,
})
const base = (source: 'querylab' | 'own', saved: unknown[] = []) => ({
  'GET /api/llm-settings': () => ok({ source, querylab_model: 'gem-a' }),
  'GET /api/llm-keys': () => ok(saved),
  'GET /api/llm-keys-models': () => ok(MODELS),
  'GET /api/agent/limits': () => ok({}),
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('KeysPage', () => {
  it('hides the key table while QueryLab AI is chosen', async () => {
    serveApi(base('querylab'))
    show()
    expect(await screen.findByRole('combobox', { name: 'AI for your questions' })).toHaveTextContent(
      'QueryLab AI',
    )
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add new API key' })).not.toBeInTheDocument()
  })

  it('lets you pick the Gemini model used on QueryLab AI', async () => {
    let sent: unknown
    serveApi({
      ...base('querylab'),
      'PUT /api/llm-settings': (request) => {
        sent = request.body
        return ok({ source: 'querylab', querylab_model: 'gem-b' })
      },
    })
    show()
    const field = await screen.findByRole('combobox', { name: 'QueryLab AI model' })
    expect(field).toHaveTextContent('gem-a')
    await userEvent.click(field)
    await userEvent.click(await screen.findByRole('option', { name: 'gem-b' }))
    await waitFor(() => {
      expect(sent).toEqual({ querylab_model: 'gem-b' })
    })
  })

  it('hides the QueryLab model choice for a custom AI', async () => {
    serveApi(base('own', []))
    show()
    await screen.findByText('No API keys yet')
    expect(screen.queryByRole('combobox', { name: 'QueryLab AI model' })).not.toBeInTheDocument()
  })

  it('switches to a custom AI and saves the choice', async () => {
    let sent: unknown
    const calls = serveApi({
      ...base('querylab'),
      'PUT /api/llm-settings': (request) => {
        sent = request.body
        return ok({ source: 'own' })
      },
    })
    show()
    await userEvent.click(await screen.findByRole('combobox', { name: 'AI for your questions' }))
    await userEvent.click(await screen.findByRole('option', { name: 'Custom AI' }))
    await waitFor(() => {
      expect(calls).toContain('PUT /api/llm-settings')
    })
    expect(sent).toEqual({ source: 'own' })
  })

  it('shows an empty state with one Add new API key button and no inline form', async () => {
    serveApi(base('own', []))
    show()
    expect(await screen.findByText('No API keys yet')).toBeVisible()
    expect(screen.getAllByRole('button', { name: 'Add new API key' })).toHaveLength(1)
    expect(screen.queryByLabelText(/API key$/)).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('lists only saved keys and never shows a key', async () => {
    serveApi(base('own', [key('openai', { is_active: true })]))
    show()
    const table = await screen.findByRole('table')
    expect(within(table).getAllByRole('row')).toHaveLength(2)
    expect(within(table).getByText('Key ends in wxyz')).toBeVisible()
    expect(within(table).getByRole('radio', { name: 'Use the OpenAI key' })).toBeChecked()
    expect(within(table).queryByText('Google Gemini')).not.toBeInTheDocument()
    // The other provider can still be added.
    expect(screen.getByRole('button', { name: 'Add new API key' })).toBeVisible()
  })

  it('warns that questions are paused when no key is in use', async () => {
    serveApi(base('own', [key('openai')]))
    show()
    expect(await screen.findByRole('status')).toHaveTextContent('Questions are paused')
  })

  it('makes the other key the one in use', async () => {
    const calls = serveApi({
      ...base('own', [key('openai', { is_active: true }), key('gemini')]),
      'PUT /api/llm-keys/gemini/activate': () => ok(key('gemini', { is_active: true })),
    })
    show()
    await userEvent.click(await screen.findByRole('radio', { name: 'Use the Google Gemini key' }))
    await waitFor(() => {
      expect(calls).toContain('PUT /api/llm-keys/gemini/activate')
    })
  })

  it('changes a model without sending the key', async () => {
    let sent: unknown
    serveApi({
      ...base('own', [key('openai', { is_active: true })]),
      'PUT /api/llm-keys/openai/model': (request) => {
        sent = request.body
        return ok(key('openai', { model: 'gpt-b' }))
      },
    })
    show()
    await userEvent.click(await screen.findByRole('combobox', { name: 'OpenAI model' }))
    await userEvent.click(await screen.findByRole('option', { name: 'gpt-b' }))
    await waitFor(() => {
      expect(sent).toEqual({ model: 'gpt-b' })
    })
  })

  it('adds a key in a modal, sends the model, then closes it', async () => {
    let sent: unknown
    serveApi({
      ...base('own', []),
      'PUT /api/llm-keys/openai': (request) => {
        sent = request.body
        return ok(key('openai', { is_active: true }))
      },
    })
    show()
    await userEvent.click(await screen.findByRole('button', { name: 'Add new API key' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText('OpenAI API key'), '  secret-key-1234  ')
    expect(within(dialog).getByLabelText('OpenAI API key')).toHaveAttribute('type', 'password')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save key' }))
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
    expect(sent).toEqual({ api_key: 'secret-key-1234', model: 'gpt-a' })
  })

  it('shows the provider refusing a key and keeps the field for correction', async () => {
    serveApi({
      ...base('own', []),
      'PUT /api/llm-keys/openai': () => fail(400, 'llm_invalid_key', 'The key was rejected.'),
    })
    show()
    await userEvent.click(await screen.findByRole('button', { name: 'Add new API key' }))
    const dialog = await screen.findByRole('dialog')
    const field = within(dialog).getByLabelText('OpenAI API key')
    await userEvent.type(field, 'bad-key-value')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save key' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('The provider rejected the key')
    expect(field).toHaveValue('bad-key-value')
  })

  it('replaces a saved key from its row', async () => {
    serveApi(base('own', [key('gemini', { is_active: true })]))
    show()
    await userEvent.click(await screen.findByRole('button', { name: 'Replace the Google Gemini key' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByRole('heading', { name: 'Replace the Google Gemini key' })).toBeVisible()
  })

  it('removes a key', async () => {
    const calls = serveApi({
      ...base('own', [key('gemini', { is_active: true })]),
      'DELETE /api/llm-keys/gemini': () => ok(null),
    })
    show()
    await userEvent.click(await screen.findByRole('button', { name: 'Remove the Google Gemini key' }))
    await waitFor(() => {
      expect(calls).toContain('DELETE /api/llm-keys/gemini')
    })
  })
})
