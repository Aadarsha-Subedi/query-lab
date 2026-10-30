import { createFileRoute } from '@tanstack/react-router'

import { PlaceholderPage } from '@/components/PlaceholderPage'

export const Route = createFileRoute('/_public/verify-email/$key')({
  component: () => (
    <PlaceholderPage title="Confirming your email" note="Email confirmation is wired up in step 0.10d." />
  ),
})
