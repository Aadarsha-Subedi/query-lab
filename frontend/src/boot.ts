/*
 * The boot screen's behaviour (design-system.md section 14). Its markup and
 * styles live in index.html and src/styles/boot.css so it shows before any
 * JavaScript; this module only ends it.
 *
 * Timing: the spinner fades in at --boot-delay. A boot that finishes before
 * then removes the screen at once (the spinner never showed). Otherwise the
 * spinner stays until at least --boot-delay + --boot-min-visible, so it never
 * blinks, then the screen fades out over --duration-base.
 */
const BOOT_ELEMENT_ID = 'boot'
const MS_PER_SECOND = 1000

function element(): HTMLElement | null {
  return document.getElementById(BOOT_ELEMENT_ID)
}

/** A CSS time token ("200ms" or "0.2s") in milliseconds. */
export function readTimeToken(name: string): number {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  if (value.endsWith('ms')) return Number.parseFloat(value)
  if (value.endsWith('s')) return Number.parseFloat(value) * MS_PER_SECOND
  throw new Error(`Design token ${name} is not a time: "${value}"`)
}

function prefersReducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/** When the boot screen may disappear, given the time since navigation start. */
export function bootHideDelay(elapsedMs: number, delayMs: number, minVisibleMs: number): number {
  if (elapsedMs < delayMs) return 0
  return Math.max(0, delayMs + minVisibleMs - elapsedMs)
}

/** The app is ready: remove the boot screen without a flash. */
export async function finishBoot(elapsedMs: number = performance.now()): Promise<void> {
  const boot = element()
  if (!boot) return
  if (elapsedMs < readTimeToken('--boot-delay')) {
    boot.remove()
    return
  }
  await wait(bootHideDelay(elapsedMs, readTimeToken('--boot-delay'), readTimeToken('--boot-min-visible')))
  if (prefersReducedMotion()) {
    boot.remove()
    return
  }
  boot.dataset.state = 'leaving'
  await wait(readTimeToken('--duration-base'))
  boot.remove()
}

/** The app cannot start: show the full-page "can't reach the server" state. */
export function failBoot(): void {
  const boot = element()
  if (!boot) return
  boot.dataset.state = 'error'
  boot.querySelector<HTMLButtonElement>('[data-boot-reload]')?.addEventListener('click', () => {
    window.location.reload()
  })
}
