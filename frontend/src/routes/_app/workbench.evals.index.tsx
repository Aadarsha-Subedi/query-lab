import { createFileRoute } from '@tanstack/react-router'

import { evalFiltersSchema } from '@/features/workbench/api'
import { Evals } from '@/features/workbench/Evals'

export const Route = createFileRoute('/_app/workbench/evals/')({
  validateSearch: evalFiltersSchema,
  component: Page,
})

function Page() {
  return <Evals filters={Route.useSearch()} />
}
