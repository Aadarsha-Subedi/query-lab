import type { ReactNode } from 'react'

import { Heading } from '@/components/typography/Heading'
import { Text } from '@/components/typography/Text'

import { ISSUES_URL, LEGAL_LAST_UPDATED } from './links'

export const legalLink = 'underline underline-offset-4'

export function IssuesLink({ children }: { children: ReactNode }) {
  return (
    <a href={ISSUES_URL} target="_blank" rel="noreferrer" className={legalLink}>
      {children}
    </a>
  )
}

/** One heading, then readable text at reading width; the project notice always comes first. */
export function LegalPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <article className="mx-auto flex max-w-[var(--reading-max)] flex-col gap-8 px-6 py-16">
      <header className="flex flex-col gap-2">
        <Heading level={1}>{title}</Heading>
        <Text variant="small" muted>
          Last updated {LEGAL_LAST_UPDATED}
        </Text>
      </header>
      <div className="flex flex-col gap-3 rounded-lg border bg-surface-muted p-6">
        <Text className="font-medium">
          Querylab is a personal learning and portfolio project, not a commercial service.
        </Text>
        <ul className="flex list-disc flex-col gap-1 pl-5 text-body">
          <li>It comes with no warranty and no promise of uptime.</li>
          <li>Data and accounts may be wiped at any time, without notice.</li>
          <li>Features may change or disappear.</li>
          <li>Do not upload personal, sensitive or production data.</li>
        </ul>
      </div>
      {children}
    </article>
  )
}

export function LegalSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <Heading level={2}>{title}</Heading>
      {children}
    </section>
  )
}

export function LegalList({ children }: { children: ReactNode }) {
  return <ul className="flex list-disc flex-col gap-2 pl-5 text-body">{children}</ul>
}
