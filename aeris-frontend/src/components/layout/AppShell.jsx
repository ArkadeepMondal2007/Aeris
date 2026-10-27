import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import { useApi } from '../../hooks/useApi'
import { fetchHealth } from '../../services/forecastService'

export default function AppShell() {
  const [refreshKey, setRefreshKey] = useState(0)
  const health = useApi(fetchHealth, null, refreshKey)

  return (
    <div className="shell">
      <Sidebar />
      <div className="shell__main">
        <Header health={health} onRefresh={() => setRefreshKey((key) => key + 1)} />
        <main className="page">
          <Outlet context={{ refreshKey }} />
        </main>
      </div>
    </div>
  )
}
