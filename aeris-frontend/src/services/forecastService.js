import { ApiError, getJson } from './apiClient'
import { parseUtc } from '../utils/time'

const toNumber = (value) => (typeof value === 'number' && Number.isFinite(value) ? value : null)

function statusOf(forecast, actual) {
  if (forecast !== null && actual !== null) return 'matched'
  if (forecast === null && actual === null) return 'missing_both'
  return forecast === null ? 'missing_forecast' : 'missing_actual'
}

export function normalizeOverview(payload) {
  const metrics = payload?.metrics
  if (!metrics || typeof metrics !== 'object') throw new ApiError('The overview response has no metrics.')
  return {
    period: payload.period ?? null,
    convention: typeof payload.convention === 'string' ? payload.convention : null,
    metrics: {
      mae: toNumber(metrics.mae_mw),
      rmse: toNumber(metrics.rmse_mw),
      bias: toNumber(metrics.bias_mw),
      matched: toNumber(metrics.matched_intervals),
      missing: toNumber(metrics.missing_intervals),
    },
  }
}

export function normalizeObservations(payload) {
  const rows = Array.isArray(payload) ? payload : payload?.observations
  if (!Array.isArray(rows)) throw new ApiError('The observations response is malformed.')
  return rows
    .flatMap((row) => {
      const ts = parseUtc(row.startTime)
      if (Number.isNaN(ts)) return []
      const forecast = toNumber(row.forecast_mw)
      const actual = toNumber(row.actual_mw)
      const error = toNumber(row.error_mw) ?? (forecast !== null && actual !== null ? forecast - actual : null)
      return [{ ts, publishTime: row.publishTime ?? null, forecast, actual, error, status: statusOf(forecast, actual) }]
    })
    .sort((a, b) => a.ts - b.ts)
}

export const fetchHealth = (_, signal) => getJson('/health', { signal })
export const fetchOverview = (_, signal) => getJson('/api/overview', { signal }).then(normalizeOverview)
export const fetchObservations = (params, signal) =>
  getJson('/api/forecast-actuals', { params, signal }).then(normalizeObservations)
