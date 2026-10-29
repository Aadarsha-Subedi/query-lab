import { contrastRatio } from './contrast'
import { applyDesignChoices, describeChoices, RECOMMENDED } from './options'

describe('design options', () => {
  it('sets and clears the data attributes tokens.css reacts to', () => {
    const clear = applyDesignChoices({ accent: 'teal', font: 'geist', size: '16', neutral: 'zinc' })
    const root = document.documentElement
    expect(root.dataset).toMatchObject({ accent: 'teal', font: 'geist', size: '16', neutral: 'zinc' })
    clear()
    expect(root.dataset.accent).toBeUndefined()
  })

  it('describes the choices for the project thread', () => {
    expect(describeChoices(RECOMMENDED, 'light')).toContain('accent: Indigo-blue')
  })

  it('computes WCAG contrast', () => {
    expect(contrastRatio([0, 0, 0], [255, 255, 255])).toBeCloseTo(21)
    expect(contrastRatio([255, 255, 255], [255, 255, 255])).toBeCloseTo(1)
  })
})
