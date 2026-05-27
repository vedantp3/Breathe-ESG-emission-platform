import { NavLink, useNavigate } from 'react-router-dom'

export default function Navbar() {
  const navigate  = useNavigate()
  const username  = localStorage.getItem('username') || 'Analyst'
  const initials  = username.slice(0, 2).toUpperCase()

  function handleLogout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('username')
    navigate('/login')
  }

  return (
    <nav className="navbar" role="navigation" aria-label="Main navigation">
      <div className="navbar-brand">
        <span className="leaf">🌿</span>
        <span><em>Breathe</em> ESG</span>
      </div>

      <div className="navbar-nav">
        <NavLink
          to="/dashboard"
          className={({ isActive }) => 'nav-link' + (isActive ? ' active' : '')}
        >
          📊 Dashboard
        </NavLink>
        <NavLink
          to="/upload"
          className={({ isActive }) => 'nav-link' + (isActive ? ' active' : '')}
        >
          📤 Upload Data
        </NavLink>
        <NavLink
          to="/uploads"
          className={({ isActive }) => 'nav-link' + (isActive ? ' active' : '')}
        >
          🗂 History
        </NavLink>
      </div>

      <div className="navbar-right">
        <div className="navbar-user">
          <div className="avatar" aria-hidden="true">{initials}</div>
          <span>{username}</span>
        </div>
        <button
          id="logout-btn"
          className="btn btn-ghost btn-sm"
          onClick={handleLogout}
          aria-label="Log out"
        >
          Sign out
        </button>
      </div>
    </nav>
  )
}
