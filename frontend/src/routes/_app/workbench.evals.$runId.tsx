import { createFileRoute } from '@tanstack/react-router'

import { EvalRunView } from '@/features/workbench/EvalRunView'

export const Route = createFileRoute('/_app/workbench/evals/$runId')({
  component: Page,
})

function Page() {
  const id = Number(Route.useParams().runId)
  return Number.isInteger(id) && id > 0 ? <EvalRunView runId={id} /> : <p>That is not an eval run.</p>
}
