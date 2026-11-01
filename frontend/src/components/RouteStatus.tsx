import { AlertCircleIcon, Home01Icon, SearchRemoveIcon } from '@hugeicons/core-free-icons'
import { Link } from '@tanstack/react-router'

import { Heading } from '@/components/typography/Heading'
import { Text } from '@/components/typography/Text'
import { Button } from '@/components/ui/button'
import { Icon, type IconSvgElement } from '@/components/ui/icon'
import { ApiError } from '@/lib/api'
import { describeError } from '@/lib/api/errors'

function StatusPage({
  icon,
  title,
  text,
  detail,
}: {
  icon: IconSvgElement
  title: string
  text: string
  detail?: string
}) {
  return (
    <main className="mx-auto flex max-w-[var(--reading-max)] flex-col items-start gap-4 px-6 py-24">
      <Icon icon={icon} size="lg" className="text-muted-foreground" />
      <Heading level={1}>{title}</Heading>
      <Text muted>{text}</Text>
      {detail && (
        <Text variant="caption" muted>
          {detail}
        </Text>
      )}
      <Button asChild icon={Home01Icon} variant="secondary">
        <Link to="/">Go to the home page</Link>
      </Button>
    </main>
  )
}

export function NotFoundPage() {
  return (
    <StatusPage icon={SearchRemoveIcon} title="Page not found" text="There is nothing at this address." />
  )
}

/** Shown when a route throws. Never shows a stack trace; an API error shows its request id. */
export function RouteErrorPage({ error }: { error: unknown }) {
  if (error instanceof ApiError && error.code === 'staff_only') {
    return (
      <StatusPage
        icon={AlertCircleIcon}
        title="Not available"
        text={describeError('staff_only', error.message).hint}
      />
    )
  }
  return (
    <StatusPage
      icon={AlertCircleIcon}
      title="Something went wrong"
      text="This page could not be shown. Reload the page to try again."
      detail={error instanceof ApiError && error.requestId ? `Request id: ${error.requestId}` : undefined}
    />
  )
}
