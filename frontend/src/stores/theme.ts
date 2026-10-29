import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'

export type ThemePreference = 'system' | 'light' | 'dark'

/** localStorage key; index.html reads it before first paint to avoid a flash. */
export const THEME_STORAGE_KEY = 'querylab-theme'

type ThemeState = {
  preference: ThemePreference
  setPreference: (preference: ThemePreference) => void
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      preference: 'system',
      setPreference: (preference) => {
        set({ preference })
      },
    }),
    { name: THEME_STORAGE_KEY, storage: createJSONStorage(() => localStorage) },
  ),
)

export function prefersDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

export function resolveTheme(preference: ThemePreference, systemDark: boolean): 'light' | 'dark' {
  if (preference === 'system') return systemDark ? 'dark' : 'light'
  return preference
}

/** Puts the resolved theme on <html> and follows system changes while on "system". */
export function applyTheme(preference: ThemePreference): () => void {
  const root = document.documentElement
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  const update = () => {
    root.classList.toggle('dark', resolveTheme(preference, media.matches) === 'dark')
  }
  update()
  media.addEventListener('change', update)
  return () => {
    media.removeEventListener('change', update)
  }
}
