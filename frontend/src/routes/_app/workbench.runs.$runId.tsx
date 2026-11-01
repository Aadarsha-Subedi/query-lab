import { createFileRoute } from '@tanstack/react-router'

import { TraceDetailView } from '@/features/workbench/TraceDetailView'

export const Route = createFileRoute('/_app/workbench/runs/$runId')({
  component: Page,
})

function Page() {
  const id = Number(Route.useParams().runId)
  return Number.isInteger(id) && id > 0 ? <TraceDetailView runId={id} /> : <p>That is not a run.</p>
}
