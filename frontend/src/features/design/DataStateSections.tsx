/*
 * DEV-ONLY demos of docs/design-system.md sections 13 (data states) and 14
 * (boot screen). Static: nothing here calls the API.
 */
import {
  AlertCircleIcon,
  ArrowRight01Icon,
  Loading03Icon,
  RefreshIcon,
  Time04Icon,
} from '@hugeicons/core-free-icons'
import { useState } from 'react'

import { Heading } from '@/components/typography/Heading'
import { Text } from '@/components/typography/Text'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState, ErrorState } from '@/components/ui/data-state'
import { Icon } from '@/components/ui/icon'
import { Skeleton } from '@/components/ui/skeleton'
import { Section } from '@/features/design/TokenSections'

const RUNS = [
  { question: 'Revenue by category last quarter', status: 'Passed', variant: 'success' },
  { question: 'Late deliveries by state', status: 'Low confidence', variant: 'warning' },
  { question: 'Repeat customers in 2026', status: 'Passed', variant: 'success' },
] as const

const ROW_COUNT = RUNS.length

type DemoState = 'loading' | 'error' | 'empty' | 'success'

/** One "Run history" card, the same box in every state (no layout shift). */
function RunHistoryCard({ state }: { state: DemoState }) {
  const [retrying, setRetrying] = useState(false)
  return (
    <Card aria-busy={state === 'loading' || undefined} className="flex min-h-80 flex-col">
      <CardHeader>
        <CardTitle>Run history</CardTitle>
        <Text variant="caption" muted as="span">
          State: {state}
        </Text>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col">
        {state === 'loading' && (
          <div className="flex flex-col gap-3">
            {Array.from({ length: ROW_COUNT }, (_, index) => (
              <div key={index} className="flex h-6 items-center justify-between gap-4">
                <Skeleton className="h-4 w-3/5" />
                <Skeleton className="h-4 w-16" />
              </div>
            ))}
            <span className="sr-only" aria-live="polite">
              Loading run history
            </span>
          </div>
        )}
        {state === 'error' && (
          <ErrorState
            title="Couldn't load run history."
            description="The server didn't answer. Try again, or refresh the page."
            requestId="4f1c9a2e"
            retrying={retrying}
            onRetry={() => {
              setRetrying(true)
            }}
          />
        )}
        {state === 'empty' && (
          <EmptyState
            icon={Time04Icon}
            title="No runs yet"
            description="Questions you ask appear here with their SQL and score."
            action={
              <Button size="sm" icon={ArrowRight01Icon} iconPosition="end">
                Ask a question
              </Button>
            }
          />
        )}
        {state === 'success' && (
          <ul className="flex flex-col gap-3">
            {RUNS.map((run) => (
              <li key={run.question} className="flex h-6 items-center justify-between gap-4">
                <span className="truncate text-body">{run.question}</span>
                <Badge variant={run.variant}>{run.status}</Badge>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

/** Static preview of the boot screen (the real one is plain HTML in index.html). */
function BootPreview({ failed }: { failed: boolean }) {
  return (
    <div className="flex h-64 flex-col items-center justify-center gap-4 rounded-lg border bg-background p-6 text-center">
      <span className="text-h3 font-semibold tracking-[var(--tracking-heading)]">Querylab</span>
      {failed ? (
        <div role="alert" className="flex flex-col items-center gap-2">
          <Icon icon={AlertCircleIcon} size="lg" className="text-danger-foreground" />
          <p className="text-body font-medium">Querylab can&apos;t reach the server</p>
          <p className="text-small text-muted-foreground">Check your connection and reload the page.</p>
          <Button variant="secondary" size="sm" icon={RefreshIcon} className="mt-2">
            Reload page
          </Button>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2" aria-busy="true">
          <Icon
            icon={Loading03Icon}
            size="md"
            className="animate-spin text-muted-foreground motion-reduce:animate-none"
          />
          <span className="sr-only">Loading Querylab</span>
        </div>
      )}
    </div>
  )
}

export function DataStateSections() {
  return (
    <>
      <Section
        id="data-states"
        title="Data states (draft)"
        intro="Every component that fetches owns its loading, error, empty and success states, inside its own box. No automatic retries: the user presses Try again or reloads."
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <RunHistoryCard state="loading" />
          <RunHistoryCard state="error" />
          <RunHistoryCard state="empty" />
          <RunHistoryCard state="success" />
        </div>
        <Text variant="small" muted>
          Press Try again in the error card to see its retrying state. The other cards are unaffected.
        </Text>
      </Section>
      <Section
        id="boot"
        title="Boot screen (draft)"
        intro="Shown only on the first page load, while the app checks the environment and who is signed in."
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-2">
            <Heading level={3}>Starting</Heading>
            <BootPreview failed={false} />
          </div>
          <div className="flex flex-col gap-2">
            <Heading level={3}>Can&apos;t start</Heading>
            <BootPreview failed />
          </div>
        </div>
      </Section>
    </>
  )
}
