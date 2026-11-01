import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

vi.stubEnv('VITE_APP_NAME', 'Querylab')

// Browser APIs jsdom lacks but Radix and sonner use. Skipped in
// node-environment tests (build.test.ts), which have no window.
if (typeof window !== 'undefined') {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string): Partial<MediaQueryList> => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }),
  })

  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  window.ResizeObserver = ResizeObserverStub

  // Radix Select (pointer capture, scrolling the chosen item into view).
  Element.prototype.hasPointerCapture = () => false
  Element.prototype.setPointerCapture = () => undefined
  Element.prototype.releasePointerCapture = () => undefined
  Element.prototype.scrollIntoView = () => undefined

  // Element.animate: resolve immediately, as if every animation had finished.
  Element.prototype.animate = function animate() {
    const animation: Partial<Animation> = {
      finished: Promise.resolve() as unknown as Promise<Animation>,
      cancel: () => undefined,
      finish: () => undefined,
      play: () => undefined,
      pause: () => undefined,
      onfinish: null,
      oncancel: null,
    }
    return animation as Animation
  }
}
