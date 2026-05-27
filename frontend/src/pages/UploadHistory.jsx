import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/axios.js'

const SOURCE_LABELS = {
  SAP_FUEL_PROCUREMENT: { label: '🏭 SAP Fuel', color: 'var(--scope-1)' },
  UTILITY_ELECTRICITY:  { label: '⚡ Utility',   color: 'var(--scope-2)' },
  CORPORATE_TRAVEL:     { label: '✈️ Travel',    color: 'var(--scope-3)' },
}

function fmtDateTime(d) {
  if (!d) return '—'
  return new Date(d).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function ErrorsDrawer({ batchId, onClose }) {
  const [errors,  setErrors]  = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get(`/uploads/${batchId}/`)
      .then(res => setErrors(res.data.errors || []))
      .finally(() => setLoading(false))
  }, [batchId])

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="errors-drawer-title">
      <div className="modal" style={{ maxWidth: 620 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 className="modal-title" id="errors-drawer-title" style={{ margin: 0 }}>
            ❌ Ingestion Errors
          </h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕ Close</button>
        </div>

        {loading ? (
          <div className="loading-state"><span className="spinner" /> Loading…</div>
        ) : errors.length === 0 ? (
          <div className="empty-state">
            <span className="empty-state-icon">✅</span>
            <div className="empty-state-title">No errors</div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '55vh', overflowY: 'auto' }}>
            {errors.map(err => (
              <div key={err.id} className="error-detail-item" style={{ padding: '0.6rem 0.75rem' }}>
                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'baseline' }}>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>Row {err.row_number}</span>
                  <span style={{ color: 'var(--status-flagged)', fontSize: '0.72rem', fontWeight: 600 }}>[{err.error_type}]</span>
                </div>
                <div style={{ marginTop: '0.2rem' }}>{err.error_message}</div>
                {err.raw_line && (
                  <div style={{ marginTop: '0.2rem', fontSize: '0.7rem', color: 'var(--text-muted)', wordBreak: 'break-all' }}>
                    ↳ {err.raw_line.slice(0, 200)}{err.raw_line.length > 200 ? '…' : ''}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default function UploadHistory() {
  const [batches,    setBatches]    = useState([])
  const [loading,    setLoading]    = useState(true)
  const [errorBatch, setErrorBatch] = useState(null)  // batch id to show errors for
  const [page,       setPage]       = useState(1)
  const [count,      setCount]      = useState(0)
  const PAGE_SIZE = 50

  useEffect(() => {
    setLoading(true)
    api.get('/uploads/', { params: { page } })
      .then(res => {
        setBatches(res.data.results ?? res.data)
        setCount(res.data.count ?? (res.data.results ?? res.data).length)
      })
      .finally(() => setLoading(false))
  }, [page])

  const totalPages = Math.ceil(count / PAGE_SIZE)

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">🗂 Upload History</h1>
          <p className="page-subtitle">
            All past CSV ingestion batches with row counts and error details.
          </p>
        </div>
        <Link to="/upload" className="btn btn-primary">
          📤 New Upload
        </Link>
      </div>

      <div className="table-wrapper history-table">
        {loading ? (
          <div className="loading-state">
            <span className="spinner" style={{ width: 32, height: 32, borderWidth: 3 }} />
            Loading history…
          </div>
        ) : batches.length === 0 ? (
          <div className="empty-state">
            <span className="empty-state-icon">📭</span>
            <div className="empty-state-title">No uploads yet</div>
            <div className="empty-state-text">
              Go to <Link to="/upload">Upload Data</Link> to import your first CSV.
            </div>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Filename</th>
                <th>Source Type</th>
                <th>Uploaded By</th>
                <th>Uploaded At</th>
                <th style={{ textAlign: 'right' }}>Rows Created</th>
                <th style={{ textAlign: 'right' }}>Errors</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {batches.map(batch => {
                const src = SOURCE_LABELS[batch.source_type] || { label: batch.source_type, color: 'var(--text-muted)' }
                return (
                  <tr key={batch.id}>
                    <td>
                      <span className="filename-cell">📄 {batch.original_filename}</span>
                    </td>

                    <td>
                      <span style={{ color: src.color, fontWeight: 600, fontSize: '0.82rem' }}>
                        {src.label}
                      </span>
                    </td>

                    <td className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                      {batch.uploaded_by_username || '—'}
                    </td>

                    <td className="td-mono text-sm">
                      {fmtDateTime(batch.uploaded_at)}
                    </td>

                    <td className="td-num">
                      <strong style={{ color: 'var(--green-400)' }}>{batch.row_count}</strong>
                    </td>

                    <td style={{ textAlign: 'right' }}>
                      <span className={`error-count-pill ${batch.error_count > 0 ? 'has-errors' : 'no-errors'}`}>
                        {batch.error_count > 0 ? `⚠️ ${batch.error_count}` : `✅ 0`}
                      </span>
                    </td>

                    <td>
                      {batch.error_count > 0 && (
                        <button
                          id={`view-errors-btn-${batch.id.slice(0,8)}`}
                          className="btn btn-ghost btn-sm"
                          onClick={() => setErrorBatch(batch.id)}
                          title="View ingestion errors"
                        >
                          View Errors
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="pagination">
          <button
            id="history-prev-btn"
            className="btn btn-secondary btn-sm"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
          >← Prev</button>
          <span className="page-info">Page {page} of {totalPages}</span>
          <button
            id="history-next-btn"
            className="btn btn-secondary btn-sm"
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >Next →</button>
        </div>
      )}

      {/* Error drawer modal */}
      {errorBatch && (
        <ErrorsDrawer
          batchId={errorBatch}
          onClose={() => setErrorBatch(null)}
        />
      )}
    </div>
  )
}
