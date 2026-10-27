import DataPanel from './common/DataPanel'
import { formatInt, formatMw } from '../utils/formatters'
import { formatTimestamp } from '../utils/time'

function direction(bias) {
  if (bias > 0) return 'overestimated'
  return bias < 0 ? 'underestimated' : 'matched'
}

export default function InsightsPanel({ query, summary, onReset }) {
  const { bias, largest, missing, total, matched } = summary
  return (
    <DataPanel title="Insights" note="Calculated from the observations in the selected range." query={query} isEmpty={total === 0} onReset={onReset}>
      <ul className="insights">
        <li>
          {bias === null
            ? 'No matched intervals, so average error is unavailable.'
            : `Across ${formatInt(matched)} matched intervals, forecasts ${direction(bias)} generation by ${formatMw(Math.abs(bias))} MW on average (mean error ${formatMw(bias, 1, { signed: true })} MW).`}
        </li>
        {largest && (
          <li>
            Largest absolute error: {formatMw(largest.error, 0, { signed: true })} MW for the interval starting {formatTimestamp(largest.ts)}, using the forecast published {formatTimestamp(largest.publishTime)}.
          </li>
        )}
        <li>
          {missing === 0
            ? 'Every interval in range has both a forecast and an actual.'
            : `${formatInt(missing)} of ${formatInt(total)} intervals lack a forecast or an actual and are excluded from these figures.`}
        </li>
      </ul>
    </DataPanel>
  )
}
