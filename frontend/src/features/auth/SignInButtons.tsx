import githubLogo from '@/assets/providers/github.png'
import googleLogo from '@/assets/providers/google.png'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

import { ALLAUTH_PROVIDER_REDIRECT, AUTH_CALLBACK_PATH, type Provider } from './api'

// The GitHub mark is black on transparent: inverted on the dark theme, like the OpenAI logo.
const PROVIDERS: { provider: Provider; label: string; logo: string; logoClassName?: string }[] = [
  { provider: 'google', label: 'Continue with Google', logo: googleLogo },
  { provider: 'github', label: 'Continue with GitHub', logo: githubLogo, logoClassName: 'dark:invert' },
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
      {PROVIDERS.map(({ provider, label, logo, logoClassName }) => (
        <form key={provider} method="post" action={api.url(ALLAUTH_PROVIDER_REDIRECT)}>
          <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken()} />
          <input type="hidden" name="provider" value={provider} />
          <input type="hidden" name="process" value="login" />
          <input
            type="hidden"
            name="callback_url"
            value={new URL(AUTH_CALLBACK_PATH, window.location.origin).toString()}
          />
          <Button
            type="submit"
            variant="secondary"
            icon={
              <img
                src={logo}
                alt=""
                width={20}
                height={20}
                className={cn('size-5 shrink-0', logoClassName)}
              />
            }
            className="w-full"
          >
            {label}
          </Button>
        </form>
      ))}
    </div>
  )
}
