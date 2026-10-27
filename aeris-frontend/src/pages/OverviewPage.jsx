import { useMemo, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { Ban, Hash, Scale, Sigma, Target } from 'lucide-react'
import KpiCard from '../components/common/KpiCard'
import DataPanel from '../components/common/DataPanel'
import DateRangeFilter from '../components/filters/DateRangeFilter'
import ForecastActualChart from '../components/charts/ForecastActualChart'
import ForecastErrorChart from '../components/charts/ForecastErrorChart'
import InsightsPanel from '../components/InsightsPanel'
import { useApi } from '../hooks/useApi'
import { fetchObservations, fetchOverview } from '../services/forecastService'
import { formatInt, formatMw } from '../utils/formatters'
import { summarise } from '../utils/statistics'

const EMPTY_RANGE = { from: '', to: '' }

const KPIS = [
  { key: 'mae', label: 'Mean absolute error', unit: 'MW', icon: Target, info: 'MAE = mean(|forecast − actual|). Average size of the error, ignoring direction.', hint: 'Average miss per hour', format: (v) => formatMw(v) },
  { key: 'rmse', label: 'Root mean squared error', unit: 'MW', icon: Sigma, info: 'RMSE = √mean((forecast − actual)²). Penalises large misses more than MAE.', hint: 'Weighted towards large misses', format: (v) => formatMw(v) },
  { key: 'bias', label: 'Forecast bias', unit: 'MW', icon: Scale, info: 'Bias = mean(forecast − actual). Positive: forecasts too high. Negative: too low.', hint: 'Positive = overestimate', format: (v) => formatMw(v, 1, { signed: true }) },
  { key: 'matched', label: 'Matched intervals', unit: 'intervals', icon: Hash, info: 'Hours with both an eligible forecast and an actual.', hint: 'Used in all metrics', format: formatInt },
  { key: 'missing', label: 'Missing intervals', unit: 'intervals', icon: Ban, info: 'Hours lacking a forecast or an actual. Never counted as zero.', hint: 'Excluded from metrics', format: formatInt },
]

export default function OverviewPage() {
  const { refreshKey } = useOutletContext()
  const [range, setRange] = useState(EMPTY_RANGE)
  const overview = useApi(fetchOverview, null, refreshKey)
  const observations = useApi(fetchObservations, range, refreshKey)
  const summary = useMemo(() => summarise(observations.data ?? []), [observations.data])
  const metrics = overview.data?.metrics
  const resetRange = () => setRange(EMPTY_RANGE)
  const noRows = !observations.data?.length

  return (
    <>
      <section className="kpis" aria-label="Forecast accuracy metrics">
        {KPIS.map(({ key, format, hint, ...kpi }) => {
          const value = metrics?.[key] ?? null
          let shownHint = hint
          if (overview.error) shownHint = 'Unavailable: API error'
          else if (value === null) shownHint = 'Not reported by the API'
          return <KpiCard key={key} {...kpi} loading={overview.loading} value={value === null ? '—' : format(value)} hint={shownHint} />
        })}
      </section>
      {overview.error && <p className="notice" role="alert">Metrics could not be loaded: {overview.error}</p>}
      <p className="notice">
        {overview.data?.convention ?? 'The API has not reported which decision cutoff was used to select forecasts.'} Metrics cover the whole analysis period; charts follow the date filter.
      </p>

      <DateRangeFilter period={overview.data?.period} value={range} onChange={setRange} />

      <DataPanel title="Forecast vs actual wind generation" note="Hourly values in MW, UTC. Gaps mark missing data." query={observations} isEmpty={noRows} onReset={resetRange}>
        <ForecastActualChart data={observations.data} />
      </DataPanel>

      <div className="split">
        <DataPanel title="Forecast error" note="Error = forecast − actual. Above zero: overestimated. Below zero: underestimated." query={observations} isEmpty={noRows} onReset={resetRange}>
          <ForecastErrorChart data={observations.data} />
        </DataPanel>
        <InsightsPanel query={observations} summary={summary} onReset={resetRange} />
      </div>
    </>
  )
}
