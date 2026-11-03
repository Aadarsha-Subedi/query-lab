import { ComputerIcon, Moon02Icon, Sun03Icon } from '@hugeicons/core-free-icons'

import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useThemeStore, type ThemePreference } from '@/stores/theme'

const NEXT: Record<ThemePreference, ThemePreference> = { system: 'light', light: 'dark', dark: 'system' }
const ICON = { system: ComputerIcon, light: Sun03Icon, dark: Moon02Icon }

/** The signed-out pages have no user menu, so the theme gets its own button: system, light, dark. */
export function ThemeButton() {
  const { preference, setPreference } = useThemeStore()
  const label = `Theme: ${preference}. Switch to ${NEXT[preference]}.`
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          icon={ICON[preference]}
          aria-label={label}
          className="rounded-full"
          onClick={() => {
            setPreference(NEXT[preference])
          }}
        />
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}
