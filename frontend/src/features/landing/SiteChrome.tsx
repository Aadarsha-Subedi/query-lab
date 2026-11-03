import type { ReactNode } from 'react'

import { Footer } from './Footer'
import { Navbar } from './Navbar'

/** The navbar, footer and skip link around the landing and legal pages. */
export function SiteChrome({ glow = false, children }: { glow?: boolean; children: ReactNode }) {
  return (
    <div className="relative isolate flex min-h-screen flex-col">
      {glow && (
        <div
          aria-hidden
          className="absolute inset-x-0 top-0 -z-10 h-screen bg-[radial-gradient(ellipse_at_50%_0%,var(--primary-subtle),transparent_70%)]"
        />
      )}
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-surface px-3 py-2 text-small focus:not-sr-only focus:absolute focus:top-2 focus:left-2"
      >
        Skip to content
      </a>
      <Navbar />
      <main id="main" tabIndex={-1} className="flex-1 outline-none">
        {children}
      </main>
      <Footer />
    </div>
  )
}
