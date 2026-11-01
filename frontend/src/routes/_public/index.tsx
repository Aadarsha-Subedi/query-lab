import { CheckmarkCircle02Icon, Login01Icon, PlayIcon, Search01Icon } from '@hugeicons/core-free-icons'
import { createFileRoute, Link } from '@tanstack/react-router'

import { Heading } from '@/components/typography/Heading'
import { Text } from '@/components/typography/Text'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Icon, type IconSvgElement } from '@/components/ui/icon'

export const Route = createFileRoute('/_public/')({
  component: Landing,
})

const STEPS: { icon: IconSvgElement; title: string; text: string }[] = [
  {
    icon: Search01Icon,
    title: 'Ask',
    text: 'Type a question about the data in plain English. The agent plans, writes SQL and checks it against your schema.',
  },
  {
    icon: PlayIcon,
    title: 'Approve',
    text: 'You see the SQL, the reasoning and what the safety guard changed before anything runs. Edit it or cancel.',
  },
  {
    icon: CheckmarkCircle02Icon,
    title: 'Measure',
    text: 'Every run is stored. Reviewed cases feed an eval set, so you can tell whether a change made the answers better or worse.',
  },
]

function Landing() {
  return (
    <main className="mx-auto flex max-w-[var(--content-max)] flex-col gap-16 px-6 py-16">
      <section className="flex max-w-[var(--reading-max)] flex-col gap-6">
        <Heading level="display">Ask your database in plain English, then measure the answer.</Heading>
        <Text variant="body-lg" muted>
          Querylab turns a question into reviewed SQL, shows its work, and scores how well the AI did.
        </Text>
        <div>
          <Button asChild icon={Login01Icon} size="md">
            <Link to="/login">Sign in to start</Link>
          </Button>
        </div>
      </section>
      <section aria-labelledby="how-it-works" className="flex flex-col gap-6">
        <Heading level={2} id="how-it-works">
          How it works
        </Heading>
        <div className="grid gap-4 md:grid-cols-3">
          {STEPS.map((step) => (
            <Card key={step.title}>
              <CardHeader>
                <Icon icon={step.icon} size="lg" />
                <CardTitle>{step.title}</CardTitle>
                <CardDescription>{step.text}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </section>
      <section className="flex flex-col gap-2">
        <Text variant="caption" muted>
          The demo workspace is built from the Olist Brazilian e-commerce dataset, licensed{' '}
          <a
            href="https://creativecommons.org/licenses/by-nc-sa/4.0/"
            className="underline underline-offset-4"
            target="_blank"
            rel="noreferrer"
          >
            CC BY-NC-SA 4.0
          </a>{' '}
          (non-commercial).
        </Text>
      </section>
    </main>
  )
}
