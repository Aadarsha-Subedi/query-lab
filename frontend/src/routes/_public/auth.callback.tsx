import { createFileRoute } from '@tanstack/react-router'

import { PlaceholderPage } from '@/components/PlaceholderPage'

export const Route = createFileRoute('/_public/auth/callback')({
  component: () => (
    <PlaceholderPage
      title="Signing you in"
      note="The Google and GitHub sign-in return here; finished in step 0.10d."
    />
  ),
})
