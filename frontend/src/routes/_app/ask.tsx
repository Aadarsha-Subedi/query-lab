import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { z } from 'zod'

import { Heading } from '@/components/typography/Heading'
import {
  MessageScroller,
  MessageScrollerButton,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from '@/components/ui/message-scroller'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { DEMO_EXAMPLES } from '@/features/ask/examples'
import { AskBox } from '@/features/ask/AskBox'
import { RunView } from '@/features/ask/RunView'
import { Suggestion, Suggestions } from '@/features/ask/Suggestion'
import { cn } from '@/lib/utils'
import { limitsQuery } from '@/features/limits/api'
import { SchemaPanel } from '@/features/schema/SchemaPanel'

const searchSchema = z.object({
  run: z.number().int().positive().optional(),
  workspace: z.number().int().positive().optional(),
  /** Pre-fills the question box (Ask again). */
  question: z.string().optional(),
  /** Ask (default) or the schema browser. `import` and `sql` are old links; they open Schema, where those live now. */
  tab: z.enum(['ask', 'schema', 'import', 'sql']).optional(),
  /** The table open on the Schema tab. */
  table: z.string().optional(),
})

export const Route = createFileRoute('/_app/ask')({
  validateSearch: searchSchema,
  component: AskPage,
})

/** The editor tabs fill the page's width, centred, and scroll with the page (only the chat scrolls inside itself). */
const WIDE = 'mx-auto w-full max-w-[var(--content-max)] pb-8'

type AskTab = NonNullable<z.infer<typeof searchSchema>['tab']>

/** A tab that does not exist for this workspace falls back to its nearest one (an old link, or a changed workspace). */
function coerceTab(tab: AskTab): AskTab {
  return tab === 'import' || tab === 'sql' ? 'schema' : tab
}

function AskPage() {
  const { run, workspace, question, tab: requested = 'ask', table } = Route.useSearch()
  const tab = coerceTab(requested)
  const navigate = useNavigate({ from: Route.fullPath })
  const [example, setExample] = useState({ text: '', n: 0 })
  const limits = useQuery(limitsQuery(workspace))
  const runsFull = limits.data
    ? limits.data.unfinished_runs.count >= limits.data.unfinished_runs.allowed
    : false

  return (
    <main
      id="main"
      tabIndex={-1}
      className={cn(
        'flex min-w-0 flex-col gap-6 px-4 pt-4 pb-6',
        // The chat fills the screen and scrolls inside itself; the schema scrolls with the page.
        tab === 'ask' && 'h-[calc(100dvh-3.5rem)] pb-0',
      )}
    >
      {/* The nav item names the page; the heading stays for screen readers and the tab title. */}
      <Heading level={1} className="sr-only">
        Ask
      </Heading>
      <Tabs
        value={tab}
        onValueChange={(next) => {
          void navigate({
            search: (previous) => ({ ...previous, tab: next === 'ask' ? undefined : (next as AskTab) }),
          })
        }}
        className="min-h-0 flex-1 gap-4"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <TabsList variant="line">
            <TabsTrigger value="ask">Ask</TabsTrigger>
            <TabsTrigger value="schema">Schema</TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="ask" className="flex min-h-0 flex-1 flex-col gap-3">
          <MessageScrollerProvider>
            <MessageScroller>
              <MessageScrollerViewport>
                <MessageScrollerContent className="mx-auto w-full max-w-[var(--chat-max)] px-1 py-4">
                  {run !== undefined ? (
                    <MessageScrollerItem messageId={`run-${run}`} scrollAnchor>
                      <RunView runId={run} />
                    </MessageScrollerItem>
                  ) : (
                    <div className="flex flex-1 flex-col items-center justify-center gap-2 py-12 text-center">
                      <Heading level={2}>What do you want to know?</Heading>
                      <p className="max-w-md text-body text-muted-foreground">
                        Ask in plain English. You read and approve the SQL before anything runs.
                      </p>
                    </div>
                  )}
                </MessageScrollerContent>
              </MessageScrollerViewport>
              <MessageScrollerButton />
            </MessageScroller>
          </MessageScrollerProvider>
          <div className="mx-auto flex w-full max-w-[var(--chat-max)] flex-col gap-3 pb-4">
            {run === undefined && workspace === undefined && (
              <Suggestions>
                {DEMO_EXAMPLES.map((text) => (
                  <Suggestion
                    key={text}
                    text={text}
                    onSelect={(chosen) => {
                      setExample((previous) => ({ text: chosen, n: previous.n + 1 }))
                    }}
                  />
                ))}
              </Suggestions>
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
        <TabsContent value="schema" className={WIDE}>
          <SchemaPanel
            workspace={workspace}
            table={table}
            onSelect={(next) => {
              void navigate({ search: (previous) => ({ ...previous, table: next }) })
            }}
          />
        </TabsContent>
      </Tabs>
    </main>
  )
}
