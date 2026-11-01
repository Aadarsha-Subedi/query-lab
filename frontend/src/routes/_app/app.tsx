import { MessageQuestionIcon } from '@hugeicons/core-free-icons'
import { createFileRoute, Link } from '@tanstack/react-router'

import { Heading } from '@/components/typography/Heading'
import { Text } from '@/components/typography/Text'
import { Button } from '@/components/ui/button'
import { RecentRuns } from '@/features/home/RecentRuns'

export const Route = createFileRoute('/_app/app')({
  component: AppHome,
})

const STEPS = [
  { title: 'Ask', text: 'Type a question in plain English about your data.' },
  { title: 'Approve', text: 'Read the SQL the agent wrote, then approve, edit or cancel it.' },
  {
    title: 'Measure',
    text: 'Mark the answer right or wrong. Wrong answers become review cases for the team.',
  },
] as const

function AppHome() {
  return (
    <main
      id="main"
      tabIndex={-1}
      className="mx-auto flex max-w-[var(--reading-max)] flex-col gap-8 px-6 py-12"
    >
      <header className="flex flex-col items-start gap-4">
        <Heading level={1}>Ask your data</Heading>
        <Text muted>
          Ask a question, check the SQL, and see how well the AI answered. Nothing runs until you approve it.
        </Text>
        <Button asChild icon={MessageQuestionIcon}>
          <Link to="/ask">Ask a question</Link>
        </Button>
      </header>
      <section aria-labelledby="how-it-works" className="flex flex-col gap-3">
        <Heading level={2} id="how-it-works">
          How it works
        </Heading>
        <ol className="grid gap-3 sm:grid-cols-3">
          {STEPS.map((step, index) => (
            <li key={step.title} className="flex flex-col gap-1 rounded-lg border bg-surface p-4">
              <span className="text-small font-medium text-muted-foreground">Step {index + 1}</span>
              <span className="text-body-lg font-semibold">{step.title}</span>
              <span className="text-small text-muted-foreground">{step.text}</span>
            </li>
          ))}
        </ol>
      </section>
      <section aria-labelledby="recent" className="flex flex-col gap-3">
        <Heading level={2} id="recent">
          Recent questions
        </Heading>
        <RecentRuns />
        <Link to="/history" className="self-start text-small underline underline-offset-4">
          See all history
        </Link>
      </section>
    </main>
  )
}
