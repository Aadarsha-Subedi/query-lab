import { createFileRoute } from '@tanstack/react-router'

import { traceFiltersSchema } from '@/features/workbench/api'
import { TraceRuns } from '@/features/workbench/TraceRuns'

export const Route = createFileRoute('/_app/workbench/runs/')({
  validateSearch: traceFiltersSchema,
  component: Page,
})

function Page() {
  return <TraceRuns filters={Route.useSearch()} />
}
