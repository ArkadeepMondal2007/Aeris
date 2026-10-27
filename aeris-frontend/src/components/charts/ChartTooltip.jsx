import { formatMw } from '../../utils/formatters'
import { formatTimestamp } from '../../utils/time'

export default function ChartTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload
  return (
    <div className="chart-tooltip">
      <strong>{formatTimestamp(row.ts)}</strong>
      <dl>
        <dt>Forecast</dt><dd>{formatMw(row.forecast, 0)} MW</dd>
        <dt>Actual</dt><dd>{formatMw(row.actual, 0)} MW</dd>
        <dt>Error</dt><dd>{formatMw(row.error, 0, { signed: true })} MW</dd>
        <dt>Published</dt><dd>{formatTimestamp(row.publishTime)}</dd>
      </dl>
    </div>
  )
}
