import { Heading } from '@/components/typography/Heading'
import { Text } from '@/components/typography/Text'
import { SignInButtons } from '@/features/auth/SignInButtons'

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
        <SignInButtons className="w-full max-w-xs shrink-0 sm:w-auto sm:max-w-none sm:flex-row" />
      </div>
    </section>
  )
}
