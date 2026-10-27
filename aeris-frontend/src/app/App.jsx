import { Route, Routes } from 'react-router-dom'
import AppShell from '../components/layout/AppShell'
import OverviewPage from '../pages/OverviewPage'
import DataExplorerPage from '../pages/DataExplorerPage'
import NotFoundPage from '../pages/NotFoundPage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<OverviewPage />} />
        <Route path="explorer" element={<DataExplorerPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
