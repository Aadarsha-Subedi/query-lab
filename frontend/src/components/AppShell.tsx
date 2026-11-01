import {
  Clock01Icon,
  DatabaseIcon,
  Key01Icon,
  TestTube01Icon,
  Home01Icon,
  Menu01Icon,
  MessageQuestionIcon,
} from '@hugeicons/core-free-icons'
import { Link, Outlet } from '@tanstack/react-router'
import type { ComponentProps } from 'react'

import { ThemeToggle } from '@/components/ThemeToggle'
import { Button } from '@/components/ui/button'
import { Icon, type IconSvgElement } from '@/components/ui/icon'
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet'
import type { User } from '@/features/auth/api'
import { Logo } from '@/components/Logo'
import { LimitsIndicator } from '@/features/limits/LimitsIndicator'
import { UserMenu } from '@/features/auth/UserMenu'
import { appName } from '@/lib/app-name'
import { cn } from '@/lib/utils'
import { useUiStore } from '@/stores/ui'

type NavItem = { to: ComponentProps<typeof Link>['to']; label: string; icon: IconSvgElement }

/** Each screen adds its entry here when its route lands. */
const NAV_ITEMS: NavItem[] = [
  { to: '/app', label: 'Home', icon: Home01Icon },
  { to: '/ask', label: 'Ask', icon: MessageQuestionIcon },
  { to: '/history', label: 'History', icon: Clock01Icon },
  { to: '/workspaces', label: 'Workspaces', icon: DatabaseIcon },
  { to: '/settings', label: 'AI settings', icon: Key01Icon },
]

/** Only staff accounts see these; the API refuses everyone else anyway. */
const STAFF_ITEMS: NavItem[] = [{ to: '/workbench', label: 'Workbench', icon: TestTube01Icon }]

function NavLinks({ onNavigate, staff }: { onNavigate?: () => void; staff: boolean }) {
  return (
    <nav aria-label="Main" className="flex flex-col gap-1">
      {[...NAV_ITEMS, ...(staff ? STAFF_ITEMS : [])].map((item) => (
        <Link
          key={item.label}
          to={item.to}
          onClick={onNavigate}
          className={cn(
            'flex h-9 items-center gap-2 rounded-md px-3 text-body font-medium text-muted-foreground transition-colors duration-fast outline-none hover:bg-surface-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring pointer-coarse:h-11',
          )}
          activeProps={{ className: 'bg-surface-muted text-foreground' }}
        >
          <Icon icon={item.icon} size="md" />
          {item.label}
        </Link>
      ))}
    </nav>
  )
}

/** Header, side navigation (a sheet on narrow screens) and the page outlet. */
export function AppShell({ user }: { user: User }) {
  const navOpen = useUiStore((state) => state.navOpen)
  const setNavOpen = useUiStore((state) => state.setNavOpen)
  const name = appName()

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2 focus:text-body focus:shadow-md"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/90 px-4 backdrop-blur">
        <Button
          variant="ghost"
          size="icon"
          icon={Menu01Icon}
          aria-label="Open navigation"
          className="md:hidden"
          onClick={() => {
            setNavOpen(true)
          }}
        />
        <Link
          to="/app"
          className="flex items-center gap-2 text-h3 font-semibold tracking-[var(--tracking-heading)]"
        >
          <Logo />
          {name}
        </Link>
        <div className="ml-auto flex items-center gap-2">
          <LimitsIndicator />
          <ThemeToggle />
          <UserMenu user={user} />
        </div>
      </header>
      <div className="flex flex-1">
        <aside aria-label="Sidebar" className="hidden w-56 shrink-0 border-r p-3 md:block">
          <NavLinks staff={user.is_staff} />
        </aside>
        <div className="min-w-0 flex-1">
          <Outlet />
        </div>
      </div>
      <Sheet open={navOpen} onOpenChange={setNavOpen}>
        <SheetContent side="left">
          <SheetTitle>{name}</SheetTitle>
          <SheetDescription className="sr-only">Main navigation</SheetDescription>
          <NavLinks
            staff={user.is_staff}
            onNavigate={() => {
              setNavOpen(false)
            }}
          />
        </SheetContent>
      </Sheet>
    </div>
  )
}
