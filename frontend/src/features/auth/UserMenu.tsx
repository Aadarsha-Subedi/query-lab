import { Logout01Icon } from '@hugeicons/core-free-icons'
import { useQueryClient } from '@tanstack/react-query'
import { useRouter } from '@tanstack/react-router'
import { useState } from 'react'

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
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

import { meQuery, signOut, type User } from './api'

function initials(user: User): string {
  const name = `${user.first_name} ${user.last_name}`.trim() || user.email
  return name.slice(0, 2).toUpperCase()
}

export function UserMenu({ user }: { user: User }) {
  const queryClient = useQueryClient()
  const router = useRouter()
  const [busy, setBusy] = useState(false)

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
        <Avatar>
          <AvatarFallback>{initials(user)}</AvatarFallback>
        </Avatar>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel className="font-normal">{user.email}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled={busy} onSelect={() => void logout()}>
          <Icon icon={Logout01Icon} size="sm" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
