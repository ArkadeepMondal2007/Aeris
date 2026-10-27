import { useLocation } from 'react-router-dom'
import { AlertTriangle, CalendarDays, CheckCircle2, Loader2, RefreshCw } from 'lucide-react'
import { NAV } from '../../app/navigation'

function StatusPill({ health }) {
  if (health.loading) return <span className="pill"><Loader2 size={14} className="spin" aria-hidden="true" />Checking API</span>
  if (health.error) return <span className="pill pill--error"><AlertTriangle size={14} aria-hidden="true" />API unreachable</span>
  return <span className="pill pill--ok"><CheckCircle2 size={14} aria-hidden="true" />API online</span>
}

export default function Header({ health, onRefresh }) {
  const { pathname } = useLocation()
  const page = NAV.find((item) => item.to === pathname)

  return (
    <header className="header">
      <div>
        <h1>{page ? page.label : 'Page not found'}</h1>
        <p>{page?.subtitle}</p>
      </div>
      <div className="header__tools">
        <span className="pill"><CalendarDays size={14} aria-hidden="true" />January 2026</span>
        <StatusPill health={health} />
        <button type="button" className="btn" onClick={onRefresh} disabled={health.loading}>
          <RefreshCw size={14} aria-hidden="true" />Refresh
        </button>
      </div>
    </header>
  )
}
