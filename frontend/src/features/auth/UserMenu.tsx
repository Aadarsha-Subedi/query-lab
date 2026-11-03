import { ComputerIcon, Logout01Icon, Moon02Icon, Sun03Icon } from '@hugeicons/core-free-icons'
import { useQueryClient } from '@tanstack/react-query'
import { useRouter } from '@tanstack/react-router'
import { useState } from 'react'

import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Icon } from '@/components/ui/icon'
import { toast } from '@/components/ui/toast-api'
import { ApiError } from '@/lib/api'
import { useThemeStore, type ThemePreference } from '@/stores/theme'

import { meQuery, signOut, type User } from './api'

const THEME_LABEL: Record<ThemePreference, string> = { system: 'System', light: 'Light', dark: 'Dark' }
const THEME_ICON = { system: ComputerIcon, light: Sun03Icon, dark: Moon02Icon }
const NEXT_THEME: Record<ThemePreference, ThemePreference> = {
  system: 'light',
  light: 'dark',
  dark: 'system',
}

function UserAvatar({ user, size }: { user: User; size?: 'sm' | 'default' }) {
  return (
    <Avatar size={size}>
      {user.avatar_url && <AvatarImage src={user.avatar_url} alt="" referrerPolicy="no-referrer" />}
      <AvatarFallback>{initials(user)}</AvatarFallback>
    </Avatar>
  )
}

function initials(user: User): string {
  const name = `${user.first_name} ${user.last_name}`.trim() || user.email
  return name.slice(0, 2).toUpperCase()
}

export function UserMenu({ user }: { user: User }) {
  const queryClient = useQueryClient()
  const router = useRouter()
  const [busy, setBusy] = useState(false)
  const { preference, setPreference } = useThemeStore()

  async function logout() {
    setBusy(true)
    try {
      await signOut()
      queryClient.clear()
      queryClient.setQueryData(meQuery.queryKey, null)
      await router.navigate({ to: '/' })
    } catch (error) {
      toast.error('Could not sign out', {
        description: error instanceof ApiError ? error.message : 'Try again.',
      })
    } finally {
      setBusy(false)
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Account menu"
        className="rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      >
        <UserAvatar user={user} />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel className="flex items-center gap-2 font-normal">
          <UserAvatar user={user} size="sm" />
          {user.email}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {/* One line that steps through System, Light and Dark; the menu stays open so the change shows. */}
        <DropdownMenuItem
          onSelect={(event) => {
            event.preventDefault()
            setPreference(NEXT_THEME[preference])
          }}
        >
          <Icon icon={THEME_ICON[preference]} size="sm" />
          Theme
          <span className="ml-auto text-small text-muted-foreground">{THEME_LABEL[preference]}</span>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled={busy} onSelect={() => void logout()}>
          <Icon icon={Logout01Icon} size="sm" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
