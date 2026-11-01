import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { CompareView } from '@/features/workbench/CompareView'

export const Route = createFileRoute('/_app/workbench/evals/compare')({
  validateSearch: z.object({ base: z.number().int().positive(), other: z.number().int().positive() }),
  component: Page,
})

function Page() {
  const { base, other } = Route.useSearch()
  return <CompareView base={base} other={other} />
}
