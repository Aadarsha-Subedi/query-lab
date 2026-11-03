import type { ReactNode } from 'react'

import { Code, CodeBlock } from '@/components/typography/Code'
import { Heading } from '@/components/typography/Heading'
import { Text } from '@/components/typography/Text'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

function Tile({
  title,
  text,
  className,
  children,
}: {
  title: string
  text: string
  className?: string
  children: ReactNode
}) {
  return (
    <li className={cn('flex flex-col gap-4 rounded-lg border bg-surface p-6', className)}>
      <div className="flex flex-col gap-2">
        <Heading level={3}>{title}</Heading>
        <Text muted>{text}</Text>
      </div>
      <div className="mt-auto">{children}</div>
    </li>
  )
}

/** The wording matches what the Ask page and Replay say for these steps (features/ask/step-text.ts). */
const TRACE = [
  { stage: 'Looking at the tables', note: 'Found 9 tables.' },
  { stage: 'Reading the orders table', note: '8 columns.' },
  {
    stage: 'Checking the values of order_status',
    note: 'Common values: delivered, shipped, canceled, unavailable, invoiced.',
  },
  { stage: 'Waiting for your approval', note: 'Nothing has run yet.' },
]

function TraceSteps() {
  return (
    <ol className="flex flex-col gap-3 rounded-md bg-surface-muted p-4">
      {TRACE.map((step, index) => (
        <li key={step.stage} className="grid grid-cols-[1.5rem_1fr] gap-x-2">
          <Text as="span" variant="small" muted className="tabular-nums">
            {index + 1}
          </Text>
          <div className="min-w-0">
            <Text variant="small" className="font-medium">
              {step.stage}
            </Text>
            <Text variant="small" muted>
              {step.note}
            </Text>
          </div>
        </li>
      ))}
    </ol>
  )
}

function GuardVerdicts() {
  return (
    <ul className="flex flex-col gap-3 rounded-md bg-surface-muted p-4">
      <li className="flex flex-col items-start gap-1">
        <Code className="bg-transparent px-0">DROP TABLE orders</Code>
        <Badge variant="danger">Refused</Badge>
      </li>
      <li className="flex flex-col items-start gap-1">
        <Code className="bg-transparent px-0">SELECT * FROM orders</Code>
        <Badge variant="success">Runs, with a row limit added</Badge>
      </li>
    </ul>
  )
}

function KeyChoices() {
  return (
    <dl className="grid gap-4 border-t pt-4 sm:grid-cols-2">
      <div className="flex flex-col gap-1">
        <dt className="text-small font-medium">QueryLab AI</dt>
        <dd className="text-small text-muted-foreground">Our Groq key, with a daily limit per user.</dd>
      </div>
      <div className="flex flex-col gap-1">
        <dt className="text-small font-medium">Custom AI</dt>
        <dd className="text-small text-muted-foreground">
          Your Gemini or OpenAI key and your choice of model. Stored encrypted; only the last 4 characters are
          ever shown.
        </dd>
      </div>
    </dl>
  )
}

export function Features() {
  return (
    <section
      id="features"
      aria-labelledby="features-title"
      className="mx-auto flex max-w-[var(--content-max)] scroll-mt-20 flex-col gap-6 px-6 py-16"
    >
      <Heading level={2} id="features-title">
        Features
      </Heading>
      <ul className="grid gap-4 lg:grid-cols-3">
        <Tile
          title="It shows its work"
          text="Every step the agent takes is stored as a trace. Replay any finished run from History, one step at a time."
          className="lg:col-span-2"
        >
          <TraceSteps />
        </Tile>
        <Tile
          title="A guard reads the SQL first"
          text="It parses each statement and lets through one SELECT on known tables. What passes runs on a read-only role, with a time limit."
        >
          <GuardVerdicts />
        </Tile>
        <Tile
          title="Bring your own Postgres dump"
          text="Upload a plain-SQL pg_dump of up to 50 MB. You can keep up to 3 private workspaces, each a read-only copy that only you can query."
        >
          <CodeBlock code="pg_dump mydb | gzip > dump.sql.gz" language="text" />
        </Tile>
        <Tile
          title="Bring your own LLM key"
          text="Start on the shared key, or switch to your own when you want a different model or no daily limit from us."
          className="lg:col-span-2"
        >
          <KeyChoices />
        </Tile>
      </ul>
    </section>
  )
}
