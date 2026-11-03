import { Heading } from '@/components/typography/Heading'
import { Card, CardDescription, CardHeader } from '@/components/ui/card'

const STEPS = [
  {
    title: 'Ask',
    text: 'Type a question about the data in plain English. The agent plans, writes SQL and checks it against your schema.',
  },
  {
    title: 'Approve',
    text: 'You see the SQL, the reasoning and what the safety guard changed before anything runs. Edit it or cancel.',
  },
  {
    title: 'Measure',
    text: 'Every run is stored. Reviewed cases feed an eval set, so you can tell whether a change made the answers better or worse.',
  },
]

export function HowItWorks() {
  return (
    <section
      id="how-it-works"
      aria-labelledby="how-it-works-title"
      className="mx-auto flex max-w-[var(--content-max)] scroll-mt-20 flex-col gap-6 px-6 py-16"
    >
      <Heading level={2} id="how-it-works-title">
        How it works
      </Heading>
      <ol className="grid gap-4 md:grid-cols-3">
        {STEPS.map((step, index) => (
          <li key={step.title} className="flex">
            <Card className="w-full">
              <CardHeader>
                <span aria-hidden className="text-h1 font-semibold text-muted-foreground tabular-nums">
                  {index + 1}
                </span>
                <Heading level={3}>{step.title}</Heading>
                <CardDescription>{step.text}</CardDescription>
              </CardHeader>
            </Card>
          </li>
        ))}
      </ol>
    </section>
  )
}
