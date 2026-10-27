import { Info } from 'lucide-react'

export default function KpiCard({ label, value, unit, hint, info, icon: Icon, loading }) {
  return (
    <article className="kpi" aria-busy={loading}>
      <div className="kpi__head">
        <h3>{label}</h3>
        <span className="kpi__info" title={info} tabIndex={0} aria-label={`${label}: ${info}`}>
          <Info size={14} aria-hidden="true" />
        </span>
      </div>
      {loading ? (
        <div className="skeleton skeleton--kpi" />
      ) : (
        <p className="kpi__value">{value}{value !== '—' && <small>{unit}</small>}</p>
      )}
      <p className="kpi__hint"><Icon size={13} aria-hidden="true" />{hint}</p>
    </article>
  )
}
