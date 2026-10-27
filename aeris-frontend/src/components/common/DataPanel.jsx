import { EmptyState, ErrorState, LoadingState } from './States'

export default function DataPanel({ title, note, query, isEmpty, onReset, children }) {
  let body = children
  if (query.loading) body = <LoadingState />
  else if (query.error) body = <ErrorState message={query.error} onRetry={query.refresh} />
  else if (isEmpty) body = <EmptyState onReset={onReset} />

  return (
    <section className="card">
      <div className="card__head">
        <h2>{title}</h2>
        {note && <p>{note}</p>}
      </div>
      {body}
    </section>
  )
}
