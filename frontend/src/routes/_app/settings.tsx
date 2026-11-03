import { createFileRoute } from '@tanstack/react-router'

import { Heading } from '@/components/typography/Heading'
import { KeysPage } from '@/features/llm-keys/KeysPage'

export const Route = createFileRoute('/_app/settings')({
  component: KeysRoute,
})

function KeysRoute() {
  return (
    <main
      id="main"
      tabIndex={-1}
      className="mx-auto flex w-full max-w-[var(--reading-max)] flex-col gap-6 px-4 py-8"
    >
      {/* The nav item names the page; the heading stays for screen readers and the tab title. */}
      <Heading level={1} className="sr-only">
        AI settings
      </Heading>
      <KeysPage />
    </main>
  )
}
