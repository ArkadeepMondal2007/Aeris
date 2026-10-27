import { ChevronLeft, ChevronRight } from 'lucide-react'
import { formatInt, formatMw } from '../../utils/formatters'
import { formatTimestamp } from '../../utils/time'

const STATUS_LABELS = { matched: 'Matched', missing_forecast: 'No forecast', missing_actual: 'No actual', missing_both: 'No data' }

export function TablePagination({ page, pageSize, total, onPage }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return (
    <div className="pagination">
      <span>Page {formatInt(page + 1)} of {formatInt(pages)} · {formatInt(total)} rows</span>
      <button type="button" className="btn" aria-label="Previous page" disabled={page === 0} onClick={() => onPage(page - 1)}><ChevronLeft size={14} /></button>
      <button type="button" className="btn" aria-label="Next page" disabled={page >= pages - 1} onClick={() => onPage(page + 1)}><ChevronRight size={14} /></button>
    </div>
  )
}

export default function ObservationsTable({ rows }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Target start (UTC)</th>
            <th>Forecast published (UTC)</th>
            <th className="num">Forecast (MW)</th>
            <th className="num">Actual (MW)</th>
            <th className="num">Error (MW)</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.ts}>
              <td>{formatTimestamp(row.ts)}</td>
              <td>{formatTimestamp(row.publishTime)}</td>
              <td className="num">{formatMw(row.forecast, 0)}</td>
              <td className="num">{formatMw(row.actual, 0)}</td>
              <td className="num">{formatMw(row.error, 0, { signed: true })}</td>
              <td><span className={row.status === 'matched' ? 'tag' : 'tag tag--warn'}>{STATUS_LABELS[row.status]}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
