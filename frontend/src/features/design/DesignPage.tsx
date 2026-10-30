/*
 * DEV-ONLY design system showcase (/design). main.tsx loads it only when
 * import.meta.env.DEV is true, so production builds do not contain it.
 */
import { Copy01Icon, Moon02Icon, RefreshIcon, Sun03Icon, ComputerIcon } from '@hugeicons/core-free-icons'
import { useEffect, useState } from 'react'

import { Heading } from '@/components/typography/Heading'
import { Text } from '@/components/typography/Text'
import { Button } from '@/components/ui/button'
import { Icon } from '@/components/ui/icon'
import { Toaster } from '@/components/ui/toast'
import { toast } from '@/components/ui/toast-api'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ComponentSections } from '@/features/design/ComponentSections'
import {
  DESIGN_OPTIONS,
  applyDesignChoices,
  describeChoices,
  useDesignOptions,
  type DesignOptionKey,
} from '@/features/design/options'
import { TokenSections } from '@/features/design/TokenSections'
import { cn } from '@/lib/utils'
import { useThemeStore, type ThemePreference } from '@/stores/theme'

const OPTION_TITLES: Record<DesignOptionKey, string> = {
  font: 'Fonts',
  size: 'Base text',
  neutral: 'Neutral',
}

const THEMES: { value: ThemePreference; label: string; icon: typeof Sun03Icon }[] = [
  { value: 'system', label: 'System', icon: ComputerIcon },
  { value: 'light', label: 'Light', icon: Sun03Icon },
  { value: 'dark', label: 'Dark', icon: Moon02Icon },
]

type Choice<T extends string> = { value: T; label: string; icon?: typeof Sun03Icon }

function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: readonly Choice<T>[]
  value: T
  onChange: (value: T) => void
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex flex-col gap-1">
      <Text variant="caption" muted as="span">
        {label}
      </Text>
      <div className="inline-flex flex-wrap gap-1 rounded-md bg-surface-muted p-1">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={option.value === value}
            onClick={() => {
              onChange(option.value)
            }}
            className={cn(
              'inline-flex h-7 items-center gap-1.5 rounded-sm px-2.5 text-small font-medium text-muted-foreground transition-colors duration-fast hover:text-foreground',
              option.value === value && 'bg-surface text-foreground shadow-sm',
            )}
          >
            {option.icon && <Icon icon={option.icon} size="sm" />}
            {option.label}
          </button>
        ))}
      </div>
    </div>
  )
}

function ControlPanel() {
  const { choices, choose, reset } = useDesignOptions()
  const { preference, setPreference } = useThemeStore()
  const keys = Object.keys(DESIGN_OPTIONS) as DesignOptionKey[]

  const copyChoices = () => {
    void navigator.clipboard.writeText(describeChoices(choices, preference)).then(() => {
      toast.success('Choices copied', { description: 'Paste them into the project thread.' })
    })
  }

  return (
    <div className="sticky top-0 z-40 border-b bg-background/90 backdrop-blur">
      <div className="mx-auto flex max-w-[var(--content-max)] flex-wrap items-end gap-4 px-6 py-3">
        <Segmented label="Theme" options={THEMES} value={preference} onChange={setPreference} />
        {keys.map((key) => (
          <Segmented
            key={key}
            label={OPTION_TITLES[key]}
            options={DESIGN_OPTIONS[key] as readonly Choice<string>[]}
            value={choices[key]}
            onChange={(value) => {
              choose(key, value as never)
            }}
          />
        ))}
        <div className="ml-auto flex gap-2">
          <Button variant="ghost" size="sm" icon={RefreshIcon} onClick={reset}>
            Recommended
          </Button>
          <Button variant="secondary" size="sm" icon={Copy01Icon} onClick={copyChoices}>
            Copy choices
          </Button>
        </div>
      </div>
    </div>
  )
}

export function DesignPage() {
  const choices = useDesignOptions((state) => state.choices)
  const preference = useThemeStore((state) => state.preference)
  useEffect(() => applyDesignChoices(choices), [choices])

  // Token values (and their contrast) are read from the live CSS, so re-read
  // them after every change to the choices or the theme.
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      setRevision((value) => value + 1)
    })
    return () => {
      cancelAnimationFrame(frame)
    }
  }, [choices, preference])

  return (
    <TooltipProvider delayDuration={300}>
      <div className="min-h-screen bg-background">
        <ControlPanel />
        <main className="mx-auto flex max-w-[var(--content-max)] flex-col gap-12 px-6 py-10">
          <header className="flex flex-col gap-2">
            <Text variant="caption" muted className="tracking-[var(--tracking-caps)] uppercase">
              Dev only · not in production builds
            </Text>
            <Heading level="display">Querylabs design system</Heading>
            <Text variant="body-lg" muted className="max-w-[var(--reading-max)]">
              Every token and base component in each state. Switch the open decisions above, compare, then
              copy your choices into the project thread. The draft lives in frontend/docs/design-system.md.
            </Text>
          </header>
          <TokenSections revision={revision} />
          <ComponentSections />
        </main>
      </div>
      <Toaster />
    </TooltipProvider>
  )
}
