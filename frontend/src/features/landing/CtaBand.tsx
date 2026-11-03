import { Heading } from '@/components/typography/Heading'
import { Text } from '@/components/typography/Text'
import { SignInButtons } from '@/features/auth/SignInButtons'
import { SignInNote } from '@/features/auth/SignInNote'

export function CtaBand() {
  return (
    <section aria-labelledby="cta-title" className="bg-primary">
      <div className="mx-auto flex max-w-[var(--content-max)] flex-col gap-6 px-6 py-16 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-col gap-2">
          <Heading level={2} id="cta-title" className="text-primary-foreground">
            Ask the demo data your first question.
          </Heading>
          <Text className="text-primary-foreground">
            The Olist workspace is ready, and nothing runs until you approve it.
          </Text>
        </div>
        <div className="flex w-full max-w-xs shrink-0 flex-col gap-3 sm:w-auto sm:max-w-none">
          {/* The band is the primary colour, so the focus ring flips to stay visible. */}
          <SignInButtons className="sm:flex-row [&_button]:focus-visible:ring-primary-foreground [&_button]:focus-visible:ring-offset-primary" />
          <SignInNote className="text-primary-foreground [&_a]:rounded-sm [&_a]:focus-visible:outline-primary-foreground" />
        </div>
      </div>
    </section>
  )
}
