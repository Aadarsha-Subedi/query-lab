import { createFileRoute } from '@tanstack/react-router'

import { casesFiltersSchema } from '@/features/workbench/api'
import { Cases } from '@/features/workbench/Cases'

export const Route = createFileRoute('/_app/workbench/cases/')({
  validateSearch: casesFiltersSchema,
  component: Page,
})

function Page() {
  return <Cases filters={Route.useSearch()} />
}
