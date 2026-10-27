import { useMemo, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { Download } from 'lucide-react'
import DataPanel from '../components/common/DataPanel'
import DateRangeFilter from '../components/filters/DateRangeFilter'
import ObservationsTable, { TablePagination } from '../components/tables/ObservationsTable'
import { useApi } from '../hooks/useApi'
import { fetchObservations, fetchOverview } from '../services/forecastService'
import { downloadCsv } from '../utils/csvExport'

const PAGE_SIZE = 50
const EMPTY_RANGE = { from: '', to: '' }
const absError = (row) => (row.error === null ? -1 : Math.abs(row.error))

function sortRows(rows, sort) {
  if (sort === 'time-desc') return [...rows].sort((a, b) => b.ts - a.ts)
  if (sort === 'abs-desc') return [...rows].sort((a, b) => absError(b) - absError(a))
  return rows
}

function matchesStatus(row, status) {
  if (status === 'all') return true
  return (status === 'matched') === (row.status === 'matched')
}

export default function DataExplorerPage() {
  const { refreshKey } = useOutletContext()
  const [range, setRange] = useState(EMPTY_RANGE)
  const [status, setStatus] = useState('all')
  const [sort, setSort] = useState('time-asc')
  const [page, setPage] = useState(0)
  const overview = useApi(fetchOverview, null, refreshKey)
  const observations = useApi(fetchObservations, range, refreshKey)

  const rows = useMemo(
    () => sortRows((observations.data ?? []).filter((row) => matchesStatus(row, status)), sort),
    [observations.data, status, sort],
  )

  const change = (setter) => (value) => { setter(value); setPage(0) }
  const reset = () => { setRange(EMPTY_RANGE); setStatus('all'); setPage(0) }
  const exportName = `aeris-observations_${range.from || 'start'}_${range.to || 'end'}.csv`

  return (
    <>
      <div className="toolbar">
        <DateRangeFilter period={overview.data?.period} value={range} onChange={change(setRange)} />
        <label className="field">Status
          <select value={status} onChange={(e) => change(setStatus)(e.target.value)}>
            <option value="all">All intervals</option>
            <option value="matched">Matched only</option>
            <option value="incomplete">Missing forecast or actual</option>
          </select>
        </label>
        <label className="field">Sort by
          <select value={sort} onChange={(e) => change(setSort)(e.target.value)}>
            <option value="time-asc">Time, oldest first</option>
            <option value="time-desc">Time, newest first</option>
            <option value="abs-desc">Largest absolute error</option>
          </select>
        </label>
        <button type="button" className="btn" disabled={!rows.length} onClick={() => downloadCsv(rows, exportName)}>
          <Download size={14} aria-hidden="true" />Export CSV
        </button>
      </div>
      <DataPanel title="Hourly observations" note="Missing values are shown as — and are never treated as zero." query={observations} isEmpty={rows.length === 0} onReset={reset}>
        <ObservationsTable rows={rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)} />
        <TablePagination page={page} pageSize={PAGE_SIZE} total={rows.length} onPage={setPage} />
      </DataPanel>
    </>
  )
}
