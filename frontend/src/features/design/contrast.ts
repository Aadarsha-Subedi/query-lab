/** WCAG contrast between two CSS colours, resolved by the browser through a canvas. */

function toRgb(color: string, context: CanvasRenderingContext2D): [number, number, number] | null {
  context.clearRect(0, 0, 1, 1)
  context.fillStyle = '#000'
  context.fillStyle = color
  context.fillRect(0, 0, 1, 1)
  const data = context.getImageData(0, 0, 1, 1).data
  const [r, g, b] = [data[0], data[1], data[2]]
  if (r === undefined || g === undefined || b === undefined) return null
  return [r, g, b]
}

function luminance([r, g, b]: [number, number, number]): number {
  const channel = (value: number) => {
    const c = value / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

export function contrastRatio(a: [number, number, number], b: [number, number, number]): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number]
  return (light + 0.05) / (dark + 0.05)
}

let canvasContext: CanvasRenderingContext2D | null | undefined

/** null when there is no canvas (tests) or the colour cannot be parsed. */
export function contrastOf(foreground: string, background: string): number | null {
  if (canvasContext === undefined) {
    try {
      canvasContext = document.createElement('canvas').getContext('2d', { willReadFrequently: true })
    } catch {
      canvasContext = null
    }
  }
  if (!canvasContext) return null
  const fg = toRgb(foreground, canvasContext)
  const bg = toRgb(background, canvasContext)
  return fg && bg ? contrastRatio(fg, bg) : null
}
