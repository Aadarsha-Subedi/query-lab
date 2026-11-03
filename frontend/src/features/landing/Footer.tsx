import { Link } from '@tanstack/react-router'

import { Logo } from '@/components/Logo'
import { Text } from '@/components/typography/Text'
import { appName } from '@/lib/app-name'

import { OLIST_LICENCE_URL, REPO_URL } from './links'

const FOOTER_LINK = 'text-small text-muted-foreground underline underline-offset-4 hover:text-foreground'

export function Footer() {
  return (
    <footer className="border-t">
      <div className="mx-auto flex max-w-[var(--content-max)] flex-col gap-6 px-6 py-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <span className="flex items-center gap-2 text-body font-semibold">
            <Logo />
            {appName()}
          </span>
          <ul className="flex flex-wrap items-center gap-4">
            <li>
              <a href={REPO_URL} target="_blank" rel="noreferrer" className={FOOTER_LINK}>
                GitHub
              </a>
            </li>
            <li>
              <Link to="/privacy" className={FOOTER_LINK}>
                Privacy
              </Link>
            </li>
            <li>
              <Link to="/terms" className={FOOTER_LINK}>
                Terms
              </Link>
            </li>
          </ul>
        </div>
        <div className="flex flex-col gap-1">
          <Text variant="caption" muted>
            The demo workspace is built from the Olist Brazilian e-commerce dataset, licensed{' '}
            <a
              href={OLIST_LICENCE_URL}
              className="underline underline-offset-4"
              target="_blank"
              rel="noreferrer"
            >
              CC BY-NC-SA 4.0
            </a>{' '}
            (non-commercial).
          </Text>
          <Text variant="caption" muted>
            A learning project by Aadarsha.
          </Text>
        </div>
      </div>
    </footer>
  )
}
