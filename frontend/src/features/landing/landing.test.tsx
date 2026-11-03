import { QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { initApi } from '@/lib/api'
import { createQueryClient } from '@/lib/query-client'
import { createAppRouter } from '@/router'
import { mockFetch, signedOut, TEST_BASE_URL } from '@/test/http'

async function openAt(path: string) {
  initApi(TEST_BASE_URL)
  mockFetch({ '/api/me': signedOut })
  const queryClient = createQueryClient(0)
  const router = createAppRouter(queryClient, createMemoryHistory({ initialEntries: [path] }))
  await router.load()
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('landing page', () => {
  it('has the headline and a real sign-in form in the hero and the closing band', async () => {
    await openAt('/')
    expect(
      await screen.findByRole('heading', {
        level: 1,
        name: 'Ask your database in plain English, then measure the answer.',
      }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Continue with Google' })).toHaveLength(2)
    expect(screen.getAllByRole('button', { name: 'Continue with GitHub' })).toHaveLength(2)
  })

  it('links the navbar to a section for every anchor, and to sign-in', async () => {
    await openAt('/')
    const nav = await screen.findByRole('navigation', { name: 'Main' })
    for (const [label, hash] of [
      ['How it works', 'how-it-works'],
      ['Features', 'features'],
      ['Evals', 'evals'],
      ['FAQ', 'faq'],
    ] as const) {
      expect(within(nav).getByRole('link', { name: label })).toHaveAttribute('href', `/#${hash}`)
      expect(document.getElementById(hash)).toBeInTheDocument()
    }
    expect(within(nav).getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
  })

  it('makes no request but the sign-in check: the preview is static', async () => {
    await openAt('/')
    await screen.findByRole('table')
    expect(screen.getByText('Checked')).toBeInTheDocument()
    expect(vi.mocked(fetch).mock.calls).toHaveLength(1)
  })

  it('labels the eval numbers as a baseline', async () => {
    await openAt('/')
    expect(await screen.findByText('Olist golden set, baseline')).toBeInTheDocument()
    expect(screen.getByText('95.1%')).toBeInTheDocument()
    expect(screen.getByText('Spider held-out, baseline')).toBeInTheDocument()
    expect(screen.getByText('86.6%')).toBeInTheDocument()
  })

  it('opens an FAQ answer, and says this is a learning project', async () => {
    const user = userEvent.setup()
    await openAt('/')
    await user.click(await screen.findByRole('button', { name: /Is this a real product/ }))
    expect(await screen.findByText(/learning and portfolio project/)).toBeVisible()
  })

  it('links the footer to the legal pages and the repository', async () => {
    await openAt('/')
    const footer = await screen.findByRole('contentinfo')
    expect(within(footer).getByRole('link', { name: 'Privacy' })).toHaveAttribute('href', '/privacy')
    expect(within(footer).getByRole('link', { name: 'Terms' })).toHaveAttribute('href', '/terms')
    expect(within(footer).getByRole('link', { name: 'GitHub' })).toHaveAttribute(
      'href',
      'https://github.com/Aadarsha-Subedi/query-lab',
    )
  })
})

describe.each(['/privacy', '/terms'])('%s', (path) => {
  it('opens by saying this is a learning project with no warranty', async () => {
    await openAt(path)
    expect(await screen.findByText(/personal learning and portfolio project/)).toBeInTheDocument()
    expect(screen.getByText(/no warranty and no promise of uptime/)).toBeInTheDocument()
    expect(screen.getByText(/Do not upload personal, sensitive or production data/)).toBeInTheDocument()
    expect(screen.getByText(/Last updated/)).toBeInTheDocument()
  })
})
