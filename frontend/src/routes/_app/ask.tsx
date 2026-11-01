import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { z } from 'zod'

import { Heading } from '@/components/typography/Heading'
import { SparklesIcon } from '@hugeicons/core-free-icons'

import { Button } from '@/components/ui/button'
import { DEMO_EXAMPLES } from '@/features/ask/examples'
import { AskBox } from '@/features/ask/AskBox'
import { RunView } from '@/features/ask/RunView'
import { limitsQuery } from '@/features/limits/api'
import { WorkspaceSelect } from '@/features/workspaces/WorkspaceSelect'
import { SchemaPanel } from '@/features/schema/SchemaPanel'

const searchSchema = z.object({
  run: z.number().int().positive().optional(),
  workspace: z.number().int().positive().optional(),
})

export const Route = createFileRoute('/_app/ask')({
  validateSearch: searchSchema,
  component: AskPage,
})

function AskPage() {
  const { run, workspace } = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const [example, setExample] = useState({ text: '', n: 0 })
  const limits = useQuery(limitsQuery(workspace))
  const runsFull = limits.data
    ? limits.data.unfinished_runs.count >= limits.data.unfinished_runs.allowed
    : false

  return (
    <div className="grid gap-6 px-4 py-6 lg:grid-cols-[18rem_1fr]">
      <aside
        aria-label="Schema browser"
        className="max-h-[70vh] lg:sticky lg:top-20 lg:h-[calc(100vh-7rem)] lg:max-h-none"
      >
        <Heading level={3} className="mb-3">
          Schema
        </Heading>
        <SchemaPanel workspace={workspace} />
      </aside>
      <main className="flex min-w-0 flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Heading level={1}>Ask</Heading>
          <WorkspaceSelect
            workspace={workspace}
            onChange={(next) => {
              void navigate({ search: { workspace: next } })
            }}
          />
        </div>
        <AskBox
          key={example.n}
          initialQuestion={example.text}
          workspace={workspace}
          disabled={runsFull}
          onStarted={(id) => {
            void navigate({ search: (previous) => ({ ...previous, run: id }) })
          }}
        />
        {run === undefined && workspace === undefined && (
          <section aria-label="Example questions" className="flex flex-col gap-2">
            <p className="text-small text-muted-foreground">Try one of these on the demo data:</p>
            <div className="flex flex-wrap gap-2">
              {DEMO_EXAMPLES.map((text) => (
                <Button
                  key={text}
                  variant="secondary"
                  size="sm"
                  icon={SparklesIcon}
                  onClick={() => {
                    setExample((previous) => ({ text, n: previous.n + 1 }))
                  }}
                >
                  {text}
                </Button>
              ))}
            </div>
          </section>
        )}
        {run !== undefined && <RunView runId={run} />}
      </main>
    </div>
  )
}
