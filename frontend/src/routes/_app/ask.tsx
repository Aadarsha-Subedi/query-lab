import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { z } from 'zod'

import { Heading } from '@/components/typography/Heading'
import { SparklesIcon } from '@hugeicons/core-free-icons'

import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { DEMO_EXAMPLES } from '@/features/ask/examples'
import { AskBox } from '@/features/ask/AskBox'
import { RunView } from '@/features/ask/RunView'
import { limitsQuery } from '@/features/limits/api'
import { WorkspaceSelect } from '@/features/workspaces/WorkspaceSelect'
import { SchemaPanel } from '@/features/schema/SchemaPanel'

const searchSchema = z.object({
  run: z.number().int().positive().optional(),
  workspace: z.number().int().positive().optional(),
  /** Pre-fills the question box (Ask again). */
  question: z.string().optional(),
  /** Ask (default) or the schema browser. */
  tab: z.enum(['ask', 'schema']).optional(),
})

export const Route = createFileRoute('/_app/ask')({
  validateSearch: searchSchema,
  component: AskPage,
})

function AskPage() {
  const { run, workspace, question, tab = 'ask' } = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const [example, setExample] = useState({ text: '', n: 0 })
  const limits = useQuery(limitsQuery(workspace))
  const runsFull = limits.data
    ? limits.data.unfinished_runs.count >= limits.data.unfinished_runs.allowed
    : false

  return (
    <main id="main" tabIndex={-1} className="flex min-w-0 flex-col gap-6 px-4 py-6">
      {/* The nav item names the page; the heading stays for screen readers and the tab title. */}
      <Heading level={1} className="sr-only">
        Ask
      </Heading>
      <Tabs
        value={tab}
        onValueChange={(next) => {
          void navigate({
            search: (previous) => ({ ...previous, tab: next === 'schema' ? 'schema' : undefined }),
          })
        }}
        className="gap-6"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <TabsList variant="line">
            <TabsTrigger value="ask">Ask</TabsTrigger>
            <TabsTrigger value="schema">Schema</TabsTrigger>
          </TabsList>
          <WorkspaceSelect
            workspace={workspace}
            onChange={(next) => {
              void navigate({ search: (previous) => ({ tab: previous.tab, workspace: next }) })
            }}
          />
        </div>
        <TabsContent
          value="ask"
          className="flex min-h-[calc(100dvh-12rem)] max-w-[var(--content-max)] flex-col gap-6"
        >
          <div className="flex flex-1 flex-col gap-6">
            {run !== undefined ? (
              <RunView runId={run} />
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center gap-2 py-12 text-center">
                <Heading level={2}>What do you want to know?</Heading>
                <p className="max-w-md text-body text-muted-foreground">
                  Ask in plain English. You read and approve the SQL before anything runs.
                </p>
              </div>
            )}
          </div>
          <div className="sticky bottom-0 flex flex-col gap-3 bg-background pt-2 pb-4">
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
                      className="h-auto min-h-8 max-w-full py-1.5 text-left whitespace-normal"
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
            <AskBox
              key={`${example.n}-${question ?? ''}`}
              initialQuestion={example.text || question}
              workspace={workspace}
              disabled={runsFull}
              onStarted={(id) => {
                void navigate({ search: (previous) => ({ ...previous, run: id }) })
              }}
            />
          </div>
        </TabsContent>
        <TabsContent value="schema">
          <SchemaPanel workspace={workspace} />
        </TabsContent>
      </Tabs>
    </main>
  )
}
