import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/axios.js'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState('')
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await api.post('/auth/token/', { username, password })
      localStorage.setItem('access_token',  res.data.access)
      localStorage.setItem('refresh_token', res.data.refresh)
      localStorage.setItem('username', username)
      navigate('/dashboard')
    } catch (err) {
      setError(
        err.response?.status === 401
          ? 'Invalid username or password.'
          : 'Could not reach the server. Is the backend running?'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-box">
        <div className="login-logo">
          <span className="login-logo-icon">🌿</span>
          <h1><em>Breathe</em> ESG</h1>
          <p>Carbon Emissions Data Platform</p>
        </div>

        <form className="login-form" onSubmit={handleSubmit} noValidate>
          {error && <div className="login-error" role="alert">{error}</div>}

          <div className="form-group">
            <label className="form-label" htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              className="form-input"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="analyst"
              autoComplete="username"
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              className="form-input"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
              required
            />
          </div>

          <button
            id="login-btn"
            type="submit"
            className="btn btn-primary btn-full btn-lg"
            disabled={loading || !username || !password}
          >
            {loading ? <><span className="spinner" /> Signing in…</> : 'Sign In'}
          </button>
        </form>

        <p className="text-muted" style={{ textAlign: 'center', marginTop: '1.5rem' }}>
          Prototype credentials: <span className="mono">analyst / analyst123</span>
        </p>
      </div>
    </div>
  )
}
