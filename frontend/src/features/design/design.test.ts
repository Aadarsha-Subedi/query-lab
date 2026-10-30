import { contrastRatio } from './contrast'

describe('contrast', () => {
  it('computes WCAG contrast', () => {
    expect(contrastRatio([0, 0, 0], [255, 255, 255])).toBeCloseTo(21)
    expect(contrastRatio([255, 255, 255], [255, 255, 255])).toBeCloseTo(1)
  })
})
