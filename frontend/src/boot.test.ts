import { bootHideDelay, failBoot, finishBoot, readTimeToken } from './boot'

const DELAY_MS = 200
const MIN_VISIBLE_MS = 400

function mountBoot() {
  document.documentElement.style.setProperty('--boot-delay', `${DELAY_MS}ms`)
  document.documentElement.style.setProperty('--boot-min-visible', `${MIN_VISIBLE_MS}ms`)
  document.documentElement.style.setProperty('--duration-base', '0.2s')
  document.body.innerHTML = `
    <div id="boot" data-state="loading">
      <div class="boot-error"><button data-boot-reload>Reload page</button></div>
    </div>`
}

describe('boot screen', () => {
  beforeEach(mountBoot)

  it('reads time tokens in ms or s', () => {
    expect(readTimeToken('--boot-delay')).toBe(DELAY_MS)
    expect(readTimeToken('--duration-base')).toBe(200)
  })

  it('never shows the spinner on a fast boot and keeps it up once shown', () => {
    expect(bootHideDelay(50, DELAY_MS, MIN_VISIBLE_MS)).toBe(0)
    expect(bootHideDelay(250, DELAY_MS, MIN_VISIBLE_MS)).toBe(350)
    expect(bootHideDelay(1000, DELAY_MS, MIN_VISIBLE_MS)).toBe(0)
  })

  it('removes itself at once when the app is ready before the delay', async () => {
    await finishBoot(50)
    expect(document.getElementById('boot')).toBeNull()
  })

  it('switches to the failure state with a reload button', () => {
    failBoot()
    expect(document.getElementById('boot')?.dataset.state).toBe('error')
    expect(document.querySelector('[data-boot-reload]')).not.toBeNull()
  })
})
