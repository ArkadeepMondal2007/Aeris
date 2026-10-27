const HEADERS = ['startTime', 'publishTime', 'forecast_mw', 'actual_mw', 'error_mw', 'status']

export function downloadCsv(rows, filename) {
  const cell = (value) => (value === null || value === undefined ? '' : String(value))
  const lines = rows.map((row) =>
    [new Date(row.ts).toISOString(), row.publishTime, row.forecast, row.actual, row.error, row.status].map(cell).join(','),
  )
  const url = URL.createObjectURL(new Blob([[HEADERS.join(','), ...lines].join('\n')], { type: 'text/csv;charset=utf-8' }))
  Object.assign(document.createElement('a'), { href: url, download: filename }).click()
  URL.revokeObjectURL(url)
}
