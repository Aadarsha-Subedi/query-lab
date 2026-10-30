import { createFileRoute } from '@tanstack/react-router'

import { PlaceholderPage } from '@/components/PlaceholderPage'

export const Route = createFileRoute('/_public/')({
  component: () => (
    <PlaceholderPage
      title="Querylab"
      note="Ask your database in plain English, then measure how well the AI answered. The real landing page comes in step 4."
    />
  ),
})
