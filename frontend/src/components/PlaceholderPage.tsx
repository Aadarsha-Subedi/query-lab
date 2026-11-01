import type { ReactNode } from 'react'

import { Heading } from '@/components/typography/Heading'
import { Text } from '@/components/typography/Text'

/** Temporary page frame until the real screens land (step 9). */
export function PlaceholderPage({
  title,
  note,
  children,
}: {
  title: string
  note: string
  children?: ReactNode
}) {
  return (
    <main
      id="main"
      tabIndex={-1}
      className="mx-auto flex max-w-[var(--reading-max)] flex-col gap-4 px-6 py-16"
    >
      <Heading level={1}>{title}</Heading>
      <Text muted>{note}</Text>
      {children}
    </main>
  )
}
