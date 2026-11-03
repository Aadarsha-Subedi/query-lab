import { createFileRoute, Link } from '@tanstack/react-router'

import { Heading } from '@/components/typography/Heading'
import { Text } from '@/components/typography/Text'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { SignInButtons } from '@/features/auth/SignInButtons'
import { SignInNote } from '@/features/auth/SignInNote'

export const Route = createFileRoute('/_public/login')({
  component: LoginPage,
})

function LoginPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-6 px-6 py-16">
      <Heading level={1}>Sign in</Heading>
      <Card>
        <CardHeader>
          <CardTitle>Welcome to Querylab</CardTitle>
          <CardDescription>Sign in with the account you already use. There is no password.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <SignInButtons />
          <SignInNote />
        </CardContent>
      </Card>
      <Text variant="caption" muted>
        <Link to="/" className="underline underline-offset-4">
          Back to the home page
        </Link>
      </Text>
    </main>
  )
}
