import { NavLink } from 'react-router-dom'
import { Wind } from 'lucide-react'
import { NAV } from '../../app/navigation'

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand__mark"><Wind size={18} aria-hidden="true" /></span>
        <div>
          <strong>AERIS</strong>
          <span>Wind Forecast Intelligence</span>
        </div>
      </div>
      <nav className="nav" aria-label="Primary">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} end>
            <Icon size={16} aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="sidebar__foot">
        <strong>Historical Analysis</strong>
        January 2026
      </div>
    </aside>
  )
}
