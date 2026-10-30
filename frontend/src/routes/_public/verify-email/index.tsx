import { createFileRoute } from '@tanstack/react-router'

import { PlaceholderPage } from '@/components/PlaceholderPage'

export const Route = createFileRoute('/_public/verify-email/')({
  component: () => (
    <PlaceholderPage
      title="Check your email"
      note="We sent you a link to confirm your address. This page is finished in step 0.10d."
    />
  ),
})
