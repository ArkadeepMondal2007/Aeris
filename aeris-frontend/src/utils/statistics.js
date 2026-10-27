// Error = forecast − actual: positive means generation was overestimated.
export function summarise(rows) {
  const matched = rows.filter((row) => row.status === 'matched')
  const bias = matched.length ? matched.reduce((sum, row) => sum + row.error, 0) / matched.length : null
  const largest = matched.reduce((max, row) => (!max || Math.abs(row.error) > Math.abs(max.error) ? row : max), null)
  return { total: rows.length, matched: matched.length, missing: rows.length - matched.length, bias, largest }
}
