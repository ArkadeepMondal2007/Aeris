const HAS_ZONE = /(Z|[+-]\d{2}:?\d{2})$/

// Timezone-naive strings are rejected rather than silently read as UTC or local time.
export function parseUtc(value) {
  if (typeof value === 'number') return value
  return typeof value === 'string' && HAS_ZONE.test(value) ? Date.parse(value) : NaN
}

const full = new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'UTC' })
const tick = new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'UTC' })

export function formatTimestamp(value) {
  const ms = parseUtc(value)
  return Number.isNaN(ms) ? '—' : `${full.format(ms)} UTC`
}

export const formatAxisTick = (ms) => tick.format(ms)
