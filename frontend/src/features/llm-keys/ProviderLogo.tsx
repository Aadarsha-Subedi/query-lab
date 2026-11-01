import googleLogo from '@/assets/providers/google.png'
import openaiLogo from '@/assets/providers/openai.png'
import { cn } from '@/lib/utils'

import type { ProviderName } from './providers'

const LOGO: Record<ProviderName, string> = { gemini: googleLogo, openai: openaiLogo }

/** The provider's mark. Decorative: the provider's name is always written next to it. */
export function ProviderLogo({ provider, className }: { provider: ProviderName; className?: string }) {
  return (
    <img
      src={LOGO[provider]}
      alt=""
      width={20}
      height={20}
      // The OpenAI mark is black on transparent: invert it on the dark theme.
      className={cn('size-5 shrink-0', provider === 'openai' && 'dark:invert', className)}
    />
  )
}
