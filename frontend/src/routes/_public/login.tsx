import { createFileRoute } from '@tanstack/react-router'

import { PlaceholderPage } from '@/components/PlaceholderPage'

export const Route = createFileRoute('/_public/login')({
  component: () => <PlaceholderPage title="Sign in" note="The sign-in form comes in step 0.10d." />,
})
