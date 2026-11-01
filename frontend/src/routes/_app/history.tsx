import { createFileRoute } from '@tanstack/react-router'

import { Heading } from '@/components/typography/Heading'
import { historySearchSchema } from '@/features/history/api'
import { HistoryTable } from '@/features/history/HistoryTable'

export const Route = createFileRoute('/_app/history')({
  validateSearch: historySearchSchema,
  component: HistoryPage,
})

function HistoryPage() {
  const filters = Route.useSearch()
  return (
    <main className="flex flex-col gap-6 px-4 py-6">
      <Heading level={1}>History</Heading>
      <HistoryTable filters={filters} />
    </main>
  )
}
