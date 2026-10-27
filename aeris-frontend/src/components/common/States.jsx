import { AlertTriangle, SearchX } from 'lucide-react'

export const LoadingState = () => <div className="skeleton skeleton--chart" role="status" aria-label="Loading data" />

export function ErrorState({ message, onRetry }) {
  return (
    <div className="state" role="alert">
      <AlertTriangle size={18} aria-hidden="true" />
      <div>
        <strong>Could not load data</strong>
        <p>{message}</p>
      </div>
      <button type="button" className="btn" onClick={onRetry}>Retry</button>
    </div>
  )
}

export function EmptyState({ onReset }) {
  return (
    <div className="state">
      <SearchX size={18} aria-hidden="true" />
      <div>
        <strong>No observations match the selected filters</strong>
        <p>Widen the date range or change the status filter.</p>
      </div>
      <button type="button" className="btn" onClick={onReset}>Reset filters</button>
    </div>
  )
}
