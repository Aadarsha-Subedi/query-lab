import { Link } from '@tanstack/react-router'

import { Text } from '@/components/typography/Text'

/** Shown wherever someone can sign in, so the Terms are in front of them before they agree. */
export function SignInNote({ className }: { className?: string }) {
  return (
    <Text variant="caption" muted className={className}>
      By continuing, you agree to the{' '}
      <Link to="/terms" className="underline underline-offset-4">
        Terms
      </Link>{' '}
      and the{' '}
      <Link to="/privacy" className="underline underline-offset-4">
        Privacy Policy
      </Link>
      .
    </Text>
  )
}
