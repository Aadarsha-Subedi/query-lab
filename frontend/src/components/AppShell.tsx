import { Home01Icon, Menu01Icon } from '@hugeicons/core-free-icons'
import { Link, Outlet } from '@tanstack/react-router'
import type { ComponentProps } from 'react'

import { ThemeToggle } from '@/components/ThemeToggle'
import { Button } from '@/components/ui/button'
import { Icon, type IconSvgElement } from '@/components/ui/icon'
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet'
import type { User } from '@/features/auth/api'
import { LimitsIndicator } from '@/features/limits/LimitsIndicator'
import { UserMenu } from '@/features/auth/UserMenu'
import { appName } from '@/lib/app-name'
import { cn } from '@/lib/utils'
import { useUiStore } from '@/stores/ui'

type NavItem = { to: ComponentProps<typeof Link>['to']; label: string; icon: IconSvgElement }

/** Each screen adds its entry here when its route lands. */
const NAV_ITEMS: NavItem[] = [{ to: '/app', label: 'Home', icon: Home01Icon }]

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Main" className="flex flex-col gap-1">
      {NAV_ITEMS.map((item) => (
        <Link
          key={item.label}
          to={item.to}
          onClick={onNavigate}
          className={cn(
            'flex h-9 items-center gap-2 rounded-md px-3 text-body font-medium text-muted-foreground transition-colors duration-fast outline-none hover:bg-surface-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring',
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
        <Link to="/app" className="text-h3 font-semibold tracking-[var(--tracking-heading)]">
          {name}
        </Link>
        <div className="ml-auto flex items-center gap-2">
          <LimitsIndicator />
          <ThemeToggle />
          <UserMenu user={user} />
        </div>
      </header>
      <div className="flex flex-1">
        <aside className="hidden w-56 shrink-0 border-r p-3 md:block">
          <NavLinks />
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
            onNavigate={() => {
              setNavOpen(false)
            }}
          />
        </SheetContent>
      </Sheet>
    </div>
  )
}
