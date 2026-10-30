import { contrastRatio } from './contrast'
import { applyDesignChoices, describeChoices, RECOMMENDED } from './options'

describe('design options', () => {
  it('sets and clears the data attributes tokens.css reacts to', () => {
    const clear = applyDesignChoices({ font: 'geist', size: '16', neutral: 'zinc' })
    const root = document.documentElement
    expect(root.dataset).toMatchObject({ font: 'geist', size: '16', neutral: 'zinc' })
    clear()
    expect(root.dataset.font).toBeUndefined()
  })

  it('describes the choices for the project thread', () => {
    expect(describeChoices(RECOMMENDED, 'light')).toContain('font: Inter + JetBrains Mono')
  })

  it('computes WCAG contrast', () => {
    expect(contrastRatio([0, 0, 0], [255, 255, 255])).toBeCloseTo(21)
    expect(contrastRatio([255, 255, 255], [255, 255, 255])).toBeCloseTo(1)
  })
})
