/*
 * DEV-ONLY. The open design decisions (the accent is decided: black), switchable on /design. Each choice
 * is a data-* attribute on <html> that tokens.css reacts to. Removed once the
 * design system is final (the chosen values become the only ones).
 */
import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'

export const DESIGN_OPTIONS = {
  font: [
    { value: 'inter', label: 'Inter + JetBrains Mono' },
    { value: 'geist', label: 'Geist + Geist Mono' },
  ],
  size: [
    { value: '14', label: '14 px' },
    { value: '16', label: '16 px' },
  ],
  neutral: [
    { value: 'stone', label: 'Warm stone' },
    { value: 'zinc', label: 'Cool zinc' },
  ],
} as const

export type DesignOptionKey = keyof typeof DESIGN_OPTIONS
export type DesignChoices = { [K in DesignOptionKey]: (typeof DESIGN_OPTIONS)[K][number]['value'] }

/** The draft's recommendations (also the :root defaults in tokens.css). */
export const RECOMMENDED: DesignChoices = { font: 'inter', size: '14', neutral: 'stone' }

type DesignOptionsState = {
  choices: DesignChoices
  choose: <K extends DesignOptionKey>(key: K, value: DesignChoices[K]) => void
  reset: () => void
}

export const useDesignOptions = create<DesignOptionsState>()(
  persist(
    (set) => ({
      choices: RECOMMENDED,
      choose: (key, value) => {
        set((state) => ({ choices: { ...state.choices, [key]: value } }))
      },
      reset: () => {
        set({ choices: RECOMMENDED })
      },
    }),
    { name: 'querylab-design-options', storage: createJSONStorage(() => localStorage) },
  ),
)

export function applyDesignChoices(choices: DesignChoices): () => void {
  const root = document.documentElement
  const keys = Object.keys(choices) as DesignOptionKey[]
  for (const key of keys) root.setAttribute(`data-${key}`, choices[key])
  return () => {
    for (const key of keys) root.removeAttribute(`data-${key}`)
  }
}

/** Text to paste back into the project thread. */
export function describeChoices(choices: DesignChoices, theme: string): string {
  const keys = Object.keys(DESIGN_OPTIONS) as DesignOptionKey[]
  const lines = keys.map((key) => {
    const option = DESIGN_OPTIONS[key].find((item) => item.value === choices[key])
    return `${key}: ${option?.label ?? choices[key]}`
  })
  return [`Design choices (viewed in ${theme} theme)`, ...lines].join('\n')
}
