/**
 * Axios instance pre-configured for the Breathe ESG API.
 *
 * - In dev: base URL is /api (proxied to Django by Vite)
 * - In production: reads VITE_API_BASE_URL env var and appends /api
 *   (set this to your deployed Django backend URL in Vercel/Netlify env vars)
 *
 * Attaches JWT access token from localStorage on every request.
 * 401 responses clear the token and redirect to /login.
 */
import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL
  ? `${import.meta.env.VITE_API_BASE_URL}/api`
  : '/api'

const api = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
})

// ── Request interceptor: inject Bearer token ──────────────────────────────
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Response interceptor: handle 401 ─────────────────────────────────────
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
