import { createFileRoute } from '@tanstack/react-router'

import { CaseReview } from '@/features/workbench/CaseReview'

export const Route = createFileRoute('/_app/workbench/cases/$caseId')({
  component: Page,
})

function Page() {
  const id = Number(Route.useParams().caseId)
  return Number.isInteger(id) && id > 0 ? <CaseReview caseId={id} /> : <p>That is not a case.</p>
}
