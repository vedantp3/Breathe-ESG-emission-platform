import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import LoginPage      from './pages/LoginPage.jsx'
import UploadPage     from './pages/UploadPage.jsx'
import Dashboard      from './pages/Dashboard.jsx'
import UploadHistory  from './pages/UploadHistory.jsx'
import Navbar         from './components/Navbar.jsx'

function ProtectedRoute({ children }) {
  const token = localStorage.getItem('access_token')
  return token ? children : <Navigate to="/login" replace />
}

function AppShell({ children }) {
  return (
    <div className="app-shell">
      <Navbar />
      <main className="page-content">{children}</main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route path="/upload" element={
          <ProtectedRoute>
            <AppShell><UploadPage /></AppShell>
          </ProtectedRoute>
        } />

        <Route path="/dashboard" element={
          <ProtectedRoute>
            <AppShell><Dashboard /></AppShell>
          </ProtectedRoute>
        } />

        <Route path="/uploads" element={
          <ProtectedRoute>
            <AppShell><UploadHistory /></AppShell>
          </ProtectedRoute>
        } />

        {/* Default redirect */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
