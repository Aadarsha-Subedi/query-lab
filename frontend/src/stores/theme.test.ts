import { applyTheme, resolveTheme, THEME_STORAGE_KEY, useThemeStore } from './theme'

describe('theme', () => {
  it('resolves system to the OS preference', () => {
    expect(resolveTheme('system', true)).toBe('dark')
    expect(resolveTheme('system', false)).toBe('light')
    expect(resolveTheme('light', true)).toBe('light')
  })

  it('persists the preference', () => {
    useThemeStore.getState().setPreference('dark')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toContain('"preference":"dark"')
  })

  it('puts the dark class on <html>', () => {
    const stop = applyTheme('dark')
    expect(document.documentElement).toHaveClass('dark')
    stop()
    applyTheme('light')
    expect(document.documentElement).not.toHaveClass('dark')
  })
})
