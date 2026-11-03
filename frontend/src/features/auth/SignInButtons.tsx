import { GithubIcon, GoogleIcon } from '@hugeicons/core-free-icons'

import { Button } from '@/components/ui/button'
import { type IconSvgElement } from '@/components/ui/icon'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

import { ALLAUTH_PROVIDER_REDIRECT, AUTH_CALLBACK_PATH, type Provider } from './api'

const PROVIDERS: { provider: Provider; label: string; icon: IconSvgElement }[] = [
  { provider: 'google', label: 'Continue with Google', icon: GoogleIcon },
  { provider: 'github', label: 'Continue with GitHub', icon: GithubIcon },
]

function csrfToken(): string {
  const entry = document.cookie.split('; ').find((part) => part.startsWith('csrftoken='))
  return entry ? decodeURIComponent(entry.slice('csrftoken='.length)) : ''
}

/**
 * allauth starts a social sign-in with a plain form POST (the browser must follow
 * the redirect to the provider), so these are real forms, not fetch calls.
 */
export function SignInButtons({ className }: { className?: string }) {
  return (
    <div className={cn('flex flex-col gap-3', className)}>
      {PROVIDERS.map(({ provider, label, icon }) => (
        <form key={provider} method="post" action={api.url(ALLAUTH_PROVIDER_REDIRECT)}>
          <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken()} />
          <input type="hidden" name="provider" value={provider} />
          <input type="hidden" name="process" value="login" />
          <input
            type="hidden"
            name="callback_url"
            value={new URL(AUTH_CALLBACK_PATH, window.location.origin).toString()}
          />
          <Button type="submit" variant="secondary" icon={icon} className="w-full">
            {label}
          </Button>
        </form>
      ))}
    </div>
  )
}
