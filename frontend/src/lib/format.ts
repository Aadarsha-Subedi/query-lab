/*
 * One place for numbers, sizes, durations and times shown to the user.
 * All output goes through Intl so it follows the browser's locale.
 */
const BYTE_UNITS = ['B', 'KB', 'MB', 'GB'] as const
const BYTES_PER_UNIT = 1024
const SECONDS_PER_MINUTE = 60
const SECONDS_PER_HOUR = 3600
const SECONDS_PER_DAY = 86_400
const MS_PER_SECOND = 1000

const numberFormat = new Intl.NumberFormat()
const dateTimeFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })
const relativeFormat = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })

export function formatNumber(value: number): string {
  return numberFormat.format(value)
}

export function formatPercent(fraction: number, digits = 1): string {
  return new Intl.NumberFormat(undefined, {
    style: 'percent',
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(fraction)
}

export function formatBytes(bytes: number): string {
  let value = bytes
  let unit = 0
  while (value >= BYTES_PER_UNIT && unit < BYTE_UNITS.length - 1) {
    value /= BYTES_PER_UNIT
    unit += 1
  }
  const digits = unit === 0 || value >= 10 ? 0 : 1
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(value)} ${BYTE_UNITS[unit] ?? 'B'}`
}

/** 4.2 s, 2 min 5 s, 1 h 3 min. For a span of seconds. */
export function formatDuration(seconds: number): string {
  if (seconds < SECONDS_PER_MINUTE)
    return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(seconds)} s`
  const total = Math.round(seconds)
  if (total < SECONDS_PER_HOUR) {
    const minutes = Math.floor(total / SECONDS_PER_MINUTE)
    const rest = total % SECONDS_PER_MINUTE
    return rest ? `${minutes} min ${rest} s` : `${minutes} min`
  }
  const hours = Math.floor(total / SECONDS_PER_HOUR)
  const minutes = Math.floor((total % SECONDS_PER_HOUR) / SECONDS_PER_MINUTE)
  return minutes ? `${hours} h ${minutes} min` : `${hours} h`
}

export function formatDateTime(iso: string): string {
  return dateTimeFormat.format(new Date(iso))
}

/** "3 minutes ago", "in 2 hours". `now` is injectable for tests. */
export function formatRelative(iso: string, now: Date = new Date()): string {
  const seconds = Math.round((new Date(iso).getTime() - now.getTime()) / MS_PER_SECOND)
  const abs = Math.abs(seconds)
  if (abs < SECONDS_PER_MINUTE) return relativeFormat.format(seconds, 'second')
  if (abs < SECONDS_PER_HOUR) return relativeFormat.format(Math.round(seconds / SECONDS_PER_MINUTE), 'minute')
  if (abs < SECONDS_PER_DAY) return relativeFormat.format(Math.round(seconds / SECONDS_PER_HOUR), 'hour')
  return relativeFormat.format(Math.round(seconds / SECONDS_PER_DAY), 'day')
}
