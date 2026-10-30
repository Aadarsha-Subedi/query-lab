import { createFileRoute } from '@tanstack/react-router'

import { PlaceholderPage } from '@/components/PlaceholderPage'

export const Route = createFileRoute('/_public/signup')({
  component: () => (
    <PlaceholderPage title="Create your account" note="The sign-up form comes in step 0.10d." />
  ),
})
