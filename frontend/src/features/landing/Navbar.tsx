import { ArrowRight01Icon, Login01Icon, Menu01Icon } from '@hugeicons/core-free-icons'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'

import { Logo } from '@/components/Logo'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { meQuery } from '@/features/auth/api'
import { appName } from '@/lib/app-name'

import { LANDING_SECTIONS } from './links'
import { ThemeButton } from './ThemeButton'

const NAV_LINK =
  'rounded-full px-3 py-1.5 text-small font-medium text-muted-foreground transition-colors duration-fast hover:bg-surface-muted hover:text-foreground'

/** The floating pill on the landing and legal pages. Signed in, only the way back to the app is offered. */
export function Navbar() {
  const { data: me } = useQuery({ ...meQuery, staleTime: 'static' })
  const signedIn = Boolean(me)
  return (
    <header className="pointer-events-none sticky top-0 z-40 px-4 pt-4">
      <nav
        aria-label="Main"
        className="pointer-events-auto mx-auto flex max-w-[var(--content-max)] items-center gap-2 rounded-full border bg-surface py-2 pr-2 pl-4 shadow-md"
      >
        <Link to="/" className="flex items-center gap-2 rounded-sm text-body font-semibold">
          <Logo />
          {/* The pill has no room for the name on the narrowest phones. */}
          <span className="max-[400px]:sr-only">{appName()}</span>
        </Link>
        {!signedIn && (
          <ul className="ml-4 hidden items-center gap-1 md:flex">
            {LANDING_SECTIONS.map(({ hash, label }) => (
              <li key={hash}>
                <Link to="/" hash={hash} className={NAV_LINK}>
                  {label}
                </Link>
              </li>
            ))}
          </ul>
        )}
        <div className="ml-auto flex items-center gap-1">
          <ThemeButton />
          {signedIn ? (
            <Button asChild icon={ArrowRight01Icon} iconPosition="end" className="rounded-full">
              <Link to="/ask">Open the app</Link>
            </Button>
          ) : (
            <>
              <Button asChild icon={Login01Icon} className="rounded-full">
                <Link to="/login">Sign in</Link>
              </Button>
              <MobileMenu />
            </>
          )}
        </div>
      </nav>
    </header>
  )
}

function MobileMenu() {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          icon={Menu01Icon}
          aria-label="Open menu"
          className="rounded-full md:hidden"
        />
      </SheetTrigger>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Menu</SheetTitle>
          <SheetDescription className="sr-only">Jump to a part of the home page.</SheetDescription>
        </SheetHeader>
        <ul className="-mx-3 flex flex-col gap-1">
          {LANDING_SECTIONS.map(({ hash, label }) => (
            <li key={hash}>
              <SheetClose asChild>
                <Link
                  to="/"
                  hash={hash}
                  className="flex min-h-11 items-center rounded-md px-3 text-body font-medium hover:bg-surface-muted"
                >
                  {label}
                </Link>
              </SheetClose>
            </li>
          ))}
        </ul>
      </SheetContent>
    </Sheet>
  )
}
