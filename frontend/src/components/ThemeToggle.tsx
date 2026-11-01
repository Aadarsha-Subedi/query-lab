import { ComputerIcon, Moon02Icon, Sun03Icon } from '@hugeicons/core-free-icons'

import { Button } from '@/components/ui/button'
import { useThemeStore, type ThemePreference } from '@/stores/theme'

const NEXT: Record<ThemePreference, ThemePreference> = { system: 'light', light: 'dark', dark: 'system' }
const ICON = { system: ComputerIcon, light: Sun03Icon, dark: Moon02Icon }

/** Cycles system, light, dark. */
export function ThemeToggle() {
  const { preference, setPreference } = useThemeStore()
  return (
    <Button
      variant="ghost"
      size="icon"
      icon={ICON[preference]}
      aria-label={`Theme: ${preference}. Switch to ${NEXT[preference]}.`}
      onClick={() => {
        setPreference(NEXT[preference])
      }}
    />
  )
}
