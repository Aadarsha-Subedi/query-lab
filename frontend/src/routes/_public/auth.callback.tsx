import { createFileRoute, Link } from '@tanstack/react-router'

import { Heading } from '@/components/typography/Heading'
import { Text } from '@/components/typography/Text'

/**
 * The provider sends the browser back here after a full page load. If sign-in
 * worked, the _public guard has already moved a signed-in user on to /ask, so
 * seeing this page means it did not.
 */
export const Route = createFileRoute('/_public/auth/callback')({
  component: CallbackPage,
})

function CallbackPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-4 px-6 py-16">
      <Heading level={1}>Sign-in did not finish</Heading>
      <Text muted>
        The sign-in was cancelled or the provider refused it. Nothing was changed on your account.
      </Text>
      <Text>
        <Link to="/login" className="underline underline-offset-4">
          Try signing in again
        </Link>
      </Text>
    </main>
  )
}
