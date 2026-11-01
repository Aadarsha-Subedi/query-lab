import { formatBytes, formatDuration, formatNumber, formatPercent, formatRelative } from './format'

describe('format', () => {
  it('groups numbers and formats percents', () => {
    expect(formatNumber(1234567)).toBe(new Intl.NumberFormat().format(1234567))
    expect(formatPercent(0.951)).toBe(
      new Intl.NumberFormat(undefined, {
        style: 'percent',
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      }).format(0.951),
    )
  })

  it('picks a byte unit', () => {
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(1536)).toContain('KB')
    expect(formatBytes(5 * 1024 * 1024)).toContain('MB')
    expect(formatBytes(3 * 1024 ** 3)).toContain('GB')
  })

  it('formats durations in the largest sensible units', () => {
    expect(formatDuration(4.2)).toContain('s')
    expect(formatDuration(125)).toBe('2 min 5 s')
    expect(formatDuration(120)).toBe('2 min')
    expect(formatDuration(3780)).toBe('1 h 3 min')
    expect(formatDuration(7200)).toBe('2 h')
  })

  it('describes past and future times against a given now', () => {
    const now = new Date('2026-11-01T12:00:00Z')
    expect(formatRelative('2026-11-01T11:57:00Z', now)).toBe(
      new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' }).format(-3, 'minute'),
    )
    expect(formatRelative('2026-11-01T14:00:00Z', now)).toBe(
      new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' }).format(2, 'hour'),
    )
    expect(formatRelative('2026-10-30T12:00:00Z', now)).toBe(
      new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' }).format(-2, 'day'),
    )
  })
})
