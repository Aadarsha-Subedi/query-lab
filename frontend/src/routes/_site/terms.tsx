import { createFileRoute } from '@tanstack/react-router'

import { TermsPage } from '@/features/landing/TermsPage'

export const Route = createFileRoute('/_site/terms')({
  component: TermsPage,
})
