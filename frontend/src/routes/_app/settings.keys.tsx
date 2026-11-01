import { createFileRoute } from '@tanstack/react-router'

import { Heading } from '@/components/typography/Heading'
import { KeysPage } from '@/features/llm-keys/KeysPage'

export const Route = createFileRoute('/_app/settings/keys')({
  component: KeysRoute,
})

function KeysRoute() {
  return (
    <main id="main" tabIndex={-1} className="flex flex-col gap-6 px-4 py-6">
      <Heading level={1}>AI settings</Heading>
      <KeysPage />
    </main>
  )
}
