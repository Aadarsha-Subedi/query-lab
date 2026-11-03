import { Heading } from '@/components/typography/Heading'
import { Text } from '@/components/typography/Text'
import { SignInButtons } from '@/features/auth/SignInButtons'

import { ProductPreview } from './ProductPreview'

export function Hero() {
  return (
    <section className="mx-auto flex max-w-[var(--content-max)] flex-col items-center gap-12 px-6 pt-16 pb-16 text-center">
      <div className="flex max-w-[var(--reading-max)] flex-col items-center gap-6">
        <Heading level="display" className="text-balance">
          Ask your database in plain English, then measure the answer.
        </Heading>
        <Text variant="body-lg" muted className="text-balance">
          Querylab turns a question into reviewed SQL, shows its work, and scores how well the AI did.
        </Text>
        <SignInButtons className="w-full max-w-xs sm:max-w-none sm:flex-row sm:justify-center" />
      </div>
      <div className="w-full">
        <ProductPreview />
      </div>
    </section>
  )
}
