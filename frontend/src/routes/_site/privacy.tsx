import { createFileRoute } from '@tanstack/react-router'

import { PrivacyPage } from '@/features/landing/PrivacyPage'

export const Route = createFileRoute('/_site/privacy')({
  component: PrivacyPage,
})
