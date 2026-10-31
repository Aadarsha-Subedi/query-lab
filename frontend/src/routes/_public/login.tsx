import { createFileRoute } from '@tanstack/react-router'

import { PlaceholderPage } from '@/components/PlaceholderPage'

export const Route = createFileRoute('/_public/login')({
  component: () => (
    <PlaceholderPage title="Sign in" note="Sign in with Google or GitHub. The two buttons come in step 9." />
  ),
})
