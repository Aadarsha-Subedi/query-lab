import { ArrowLeft01Icon } from '@hugeicons/core-free-icons'
import { createFileRoute, Link } from '@tanstack/react-router'

import { Heading } from '@/components/typography/Heading'
import { Button } from '@/components/ui/button'
import { Replay } from '@/features/history/Replay'

export const Route = createFileRoute('/_app/runs/$runId/replay')({
  component: ReplayPage,
})

function ReplayPage() {
  const { runId } = Route.useParams()
  const id = Number(runId)
  return (
    <main id="main" tabIndex={-1} className="flex flex-col gap-6 px-4 py-6">
      <div className="flex items-center gap-3">
        <Button asChild variant="ghost" size="sm" icon={ArrowLeft01Icon}>
          <Link to="/history">History</Link>
        </Button>
        <Heading level={1}>Replay</Heading>
      </div>
      {Number.isInteger(id) && id > 0 ? <Replay runId={id} /> : <p>That is not a run.</p>}
    </main>
  )
}
