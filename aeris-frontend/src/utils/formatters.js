export function formatMw(value, digits = 1, { signed = false } = {}) {
  if (value === null || value === undefined) return '—'
  return new Intl.NumberFormat('en-GB', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    signDisplay: signed ? 'exceptZero' : 'auto',
  }).format(value)
}

export const formatInt = (value) => (value === null || value === undefined ? '—' : new Intl.NumberFormat('en-GB').format(value))
