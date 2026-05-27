import { useState, useEffect, useCallback } from 'react'
import api from '../api/axios.js'
import SummaryBar from '../components/SummaryBar.jsx'
import { StatusBadge, ScopePill } from '../components/StatusBadge.jsx'

// ── Helpers ───────────────────────────────────────────────────────────────

function fmt(val, decimals = 2) {
  const n = parseFloat(val)
  if (isNaN(n)) return '—'
  return n.toLocaleString('en-GB', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

function fmtDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

// ── Flag Modal ─────────────────────────────────────────────────────────────

function FlagModal({ row, onClose, onSaved }) {
  const [reason, setReason] = useState('')
  const [notes,  setNotes]  = useState('')
  const [saving, setSaving] = useState(false)
  const [err,    setErr]    = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    if (!reason.trim()) { setErr('A reason is required.'); return }
    setSaving(true)
    try {
      await api.patch(`/rows/${row.id}/flag/`, { reason, analyst_notes: notes })
      onSaved()
    } catch (e) {
      setErr(e.response?.data?.error || 'Failed to flag row.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="flag-modal-title">
      <div className="modal">
        <h2 className="modal-title" id="flag-modal-title">🚩 Flag Row</h2>
        <p className="text-muted text-sm" style={{ marginBottom: '1rem' }}>
          Activity: <strong>{row.activity_description || row.site_name}</strong>
        </p>
        <form onSubmit={handleSubmit}>
          <div className="form-group" style={{ marginBottom: '0.75rem' }}>
            <label className="form-label" htmlFor="flag-reason">Reason *</label>
            <input
              id="flag-reason"
              className="form-input"
              placeholder="e.g. Duplicate entry, incorrect unit…"
              value={reason}
              onChange={e => setReason(e.target.value)}
              required
              autoFocus
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="flag-notes">Analyst Notes</label>
            <textarea
              id="flag-notes"
              className="form-textarea"
              placeholder="Optional additional context…"
              value={notes}
              onChange={e => setNotes(e.target.value)}
            />
          </div>
          {err && <div className="alert alert-error" style={{ marginTop: '0.75rem' }}><span className="alert-icon">❌</span>{err}</div>}
          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={saving}>Cancel</button>
            <button type="submit" id="flag-confirm-btn" className="btn btn-danger" disabled={saving}>
              {saving ? <><span className="spinner" /> Flagging…</> : '🚩 Flag Row'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Edit Modal ─────────────────────────────────────────────────────────────

function EditModal({ row, onClose, onSaved }) {
  const [rawValue,  setRawValue]  = useState(row.raw_value ?? '')
  const [rawUnit,   setRawUnit]   = useState(row.raw_unit  ?? '')
  const [kgco2e,    setKgco2e]    = useState(row.kgco2e    ?? '')
  const [notes,     setNotes]     = useState(row.analyst_notes ?? '')
  const [saving,    setSaving]    = useState(false)
  const [err,       setErr]       = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    try {
      await api.patch(`/rows/${row.id}/`, {
        raw_value: rawValue,
        raw_unit:  rawUnit,
        kgco2e,
        analyst_notes: notes,
      })
      onSaved()
    } catch (e) {
      setErr(e.response?.data?.error || 'Failed to save changes.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="edit-modal-title">
      <div className="modal">
        <h2 className="modal-title" id="edit-modal-title">✏️ Edit Row</h2>
        <p className="text-muted text-sm" style={{ marginBottom: '1rem' }}>
          Original values are preserved for audit. Editing <strong>{row.activity_description || row.site_name}</strong>
        </p>

        {row.was_edited && (
          <div className="alert alert-warning" style={{ marginBottom: '0.75rem' }}>
            <span className="alert-icon">ℹ️</span>
            <span>Previously edited. Original: <span className="mono">{row.original_raw_value} {row.original_raw_unit} / {row.original_kgco2e} kgCO₂e</span></span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
            <div className="form-group">
              <label className="form-label" htmlFor="edit-raw-value">Raw Value</label>
              <input id="edit-raw-value" type="number" step="any" className="form-input" value={rawValue} onChange={e => setRawValue(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="edit-raw-unit">Unit</label>
              <input id="edit-raw-unit" type="text" className="form-input" value={rawUnit} onChange={e => setRawUnit(e.target.value)} />
            </div>
          </div>
          <div className="form-group" style={{ marginBottom: '0.75rem' }}>
            <label className="form-label" htmlFor="edit-kgco2e">kgCO₂e</label>
            <input id="edit-kgco2e" type="number" step="any" className="form-input" value={kgco2e} onChange={e => setKgco2e(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="edit-notes">Analyst Notes</label>
            <textarea id="edit-notes" className="form-textarea" value={notes} onChange={e => setNotes(e.target.value)} placeholder="Reason for correction…" />
          </div>
          {err && <div className="alert alert-error" style={{ marginTop: '0.75rem' }}><span className="alert-icon">❌</span>{err}</div>}
          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={saving}>Cancel</button>
            <button type="submit" id="edit-confirm-btn" className="btn btn-primary" disabled={saving}>
              {saving ? <><span className="spinner" /> Saving…</> : '💾 Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Lock Modal ─────────────────────────────────────────────────────────────

function LockModal({ selectedIds, onClose, onSaved }) {
  const [locking, setLocking] = useState(false)
  const [err,     setErr]     = useState('')

  async function handleLock() {
    setLocking(true)
    try {
      const res = await api.post('/rows/lock/', { row_ids: selectedIds })
      onSaved(res.data)
    } catch (e) {
      setErr(e.response?.data?.error || 'Lock failed.')
    } finally {
      setLocking(false)
    }
  }

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="lock-modal-title">
      <div className="modal">
        <h2 className="modal-title" id="lock-modal-title">🔒 Lock for Audit</h2>
        <p className="text-muted" style={{ marginBottom: '1rem' }}>
          You are about to lock <strong>{selectedIds.length}</strong> approved row(s).
          Locked rows cannot be edited or re-approved. This action is intended for final audit submission.
        </p>
        {err && <div className="alert alert-error"><span className="alert-icon">❌</span>{err}</div>}
        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onClose} disabled={locking}>Cancel</button>
          <button id="lock-confirm-btn" className="btn btn-primary" onClick={handleLock} disabled={locking}>
            {locking ? <><span className="spinner" /> Locking…</> : '🔒 Confirm Lock'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Filter Bar ─────────────────────────────────────────────────────────────

function FilterBar({ filters, onChange }) {
  function set(key, val) { onChange({ ...filters, [key]: val }) }

  return (
    <div className="filter-bar">
      <div className="form-group">
        <label className="form-label" htmlFor="filter-source">Source</label>
        <select id="filter-source" className="form-select" value={filters.source} onChange={e => set('source', e.target.value)}>
          <option value="">All Sources</option>
          <option value="SAP_FUEL_PROCUREMENT">SAP Fuel</option>
          <option value="UTILITY_ELECTRICITY">Utility</option>
          <option value="CORPORATE_TRAVEL">Travel</option>
        </select>
      </div>

      <div className="form-group">
        <label className="form-label" htmlFor="filter-status">Status</label>
        <select id="filter-status" className="form-select" value={filters.status} onChange={e => set('status', e.target.value)}>
          <option value="">All Statuses</option>
          <option value="PENDING">Pending</option>
          <option value="NEEDS_DISTANCE">Needs Distance</option>
          <option value="FLAGGED">Flagged</option>
          <option value="APPROVED">Approved</option>
          <option value="LOCKED">Locked</option>
        </select>
      </div>

      <div className="form-group">
        <label className="form-label" htmlFor="filter-scope">Scope</label>
        <select id="filter-scope" className="form-select" value={filters.scope} onChange={e => set('scope', e.target.value)}>
          <option value="">All Scopes</option>
          <option value="1">Scope 1</option>
          <option value="2">Scope 2</option>
          <option value="3">Scope 3</option>
        </select>
      </div>

      <div className="form-group">
        <label className="form-label" htmlFor="filter-date-from">From</label>
        <input id="filter-date-from" type="date" className="form-input" value={filters.date_from} onChange={e => set('date_from', e.target.value)} />
      </div>

      <div className="form-group">
        <label className="form-label" htmlFor="filter-date-to">To</label>
        <input id="filter-date-to" type="date" className="form-input" value={filters.date_to} onChange={e => set('date_to', e.target.value)} />
      </div>

      <div className="form-group">
        <label className="form-label" htmlFor="filter-search">Search</label>
        <input
          id="filter-search"
          type="text"
          className="form-input"
          placeholder="Site, description…"
          value={filters.search}
          onChange={e => set('search', e.target.value)}
        />
      </div>

      <button
        id="clear-filters-btn"
        className="btn btn-ghost btn-sm"
        style={{ marginBottom: '0.4rem' }}
        onClick={() => onChange({ source: '', status: '', scope: '', date_from: '', date_to: '', search: '' })}
      >
        ✕ Clear
      </button>
    </div>
  )
}

// ── Main Dashboard ─────────────────────────────────────────────────────────

const DEFAULT_FILTERS = { source: '', status: '', scope: '', date_from: '', date_to: '', search: '' }

export default function Dashboard() {
  const [rows,     setRows]     = useState([])
  const [summary,  setSummary]  = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [filters,  setFilters]  = useState(DEFAULT_FILTERS)
  const [page,     setPage]     = useState(1)
  const [count,    setCount]    = useState(0)
  const [selected, setSelected] = useState(new Set())

  // Modal state
  const [flagRow,  setFlagRow]  = useState(null)
  const [editRow,  setEditRow]  = useState(null)
  const [showLock, setShowLock] = useState(false)

  // Inline approve feedback
  const [approvingId, setApprovingId] = useState(null)

  const PAGE_SIZE = 50

  const fetchRows = useCallback(async (pg = 1, f = filters) => {
    setLoading(true)
    try {
      const params = { page: pg }
      if (f.source)    params.source    = f.source
      if (f.status)    params.status    = f.status
      if (f.scope)     params.scope     = f.scope
      if (f.date_from) params.date_from = f.date_from
      if (f.date_to)   params.date_to   = f.date_to
      if (f.search)    params.search    = f.search

      const [rowsRes, summaryRes] = await Promise.all([
        api.get('/rows/', { params }),
        api.get('/summary/'),
      ])

      setRows(rowsRes.data.results ?? rowsRes.data)
      setCount(rowsRes.data.count  ?? (rowsRes.data.results ?? rowsRes.data).length)
      setSummary(summaryRes.data)
    } catch (_) {
      // error handled by axios interceptor
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    fetchRows(page, filters)
  }, [page, filters])

  function handleFilterChange(f) {
    setFilters(f)
    setPage(1)
    setSelected(new Set())
  }

  // ── Approve inline ──────────────────────────────────────────────────────
  async function handleApprove(row) {
    setApprovingId(row.id)
    try {
      await api.patch(`/rows/${row.id}/approve/`)
      fetchRows(page, filters)
    } catch (_) { /* error shown to user via alert below if needed */ }
    finally { setApprovingId(null) }
  }

  // ── Selection logic ─────────────────────────────────────────────────────
  function toggleSelect(id) {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function toggleSelectAll() {
    const approvedIds = rows.filter(r => r.status === 'APPROVED').map(r => r.id)
    if (approvedIds.every(id => selected.has(id))) {
      setSelected(new Set())
    } else {
      setSelected(new Set(approvedIds))
    }
  }

  const selectedApproved = rows.filter(r => r.status === 'APPROVED' && selected.has(r.id)).map(r => r.id)
  const totalPages = Math.ceil(count / PAGE_SIZE)

  return (
    <div className="dashboard-layout">
      <div className="page-header">
        <div>
          <h1 className="page-title">📊 Emissions Review</h1>
          <p className="page-subtitle">
            Review, approve, and flag imported emissions data before audit lock.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          {selectedApproved.length > 0 && (
            <button
              id="lock-selected-btn"
              className="btn btn-secondary"
              onClick={() => setShowLock(true)}
            >
              🔒 Lock {selectedApproved.length} Approved
            </button>
          )}
          <button id="refresh-btn" className="btn btn-ghost" onClick={() => fetchRows(page, filters)}>
            🔄 Refresh
          </button>
        </div>
      </div>

      {/* Summary */}
      <SummaryBar data={summary} />

      {/* Filters */}
      <FilterBar filters={filters} onChange={handleFilterChange} />

      {/* Table */}
      <div className="table-wrapper">
        {loading ? (
          <div className="loading-state">
            <span className="spinner" style={{ width: 32, height: 32, borderWidth: 3 }} />
            Loading rows…
          </div>
        ) : rows.length === 0 ? (
          <div className="empty-state">
            <span className="empty-state-icon">🔍</span>
            <div className="empty-state-title">No rows found</div>
            <div className="empty-state-text">
              Try changing your filters or upload some data first.
            </div>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th style={{ width: 36 }}>
                  <input
                    type="checkbox"
                    id="select-all-cb"
                    title="Select all approved rows on this page"
                    onChange={toggleSelectAll}
                    checked={
                      rows.filter(r => r.status === 'APPROVED').length > 0 &&
                      rows.filter(r => r.status === 'APPROVED').every(r => selected.has(r.id))
                    }
                  />
                </th>
                <th>Source</th>
                <th>Date</th>
                <th>Site / Location</th>
                <th>Activity</th>
                <th>Raw Value</th>
                <th>kgCO₂e</th>
                <th>Scope</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.id}>
                  <td>
                    {row.status === 'APPROVED' && (
                      <input
                        type="checkbox"
                        id={`cb-${row.id.slice(0,8)}`}
                        checked={selected.has(row.id)}
                        onChange={() => toggleSelect(row.id)}
                        aria-label={`Select row ${row.id.slice(0,8)}`}
                      />
                    )}
                  </td>

                  <td>
                    <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                      {row.source_type === 'SAP_FUEL_PROCUREMENT' ? '🏭 SAP'
                        : row.source_type === 'UTILITY_ELECTRICITY' ? '⚡ Utility'
                        : '✈️ Travel'}
                    </span>
                  </td>

                  <td className="td-mono">{fmtDate(row.activity_date)}</td>

                  <td>
                    <div className="activity-cell">
                      <div className="activity-cell-desc">{row.site_name || '—'}</div>
                      <div className="activity-cell-site">{row.location || ''}</div>
                    </div>
                  </td>

                  <td>
                    <div className="activity-cell">
                      <div className="activity-cell-desc" title={row.activity_description}>
                        {row.activity_description?.slice(0, 55) || '—'}
                        {row.activity_description?.length > 55 ? '…' : ''}
                      </div>
                      {row.was_edited && (
                        <span className="text-sm" style={{ color: 'var(--status-pending)' }}>✏️ edited</span>
                      )}
                    </div>
                  </td>

                  <td className="td-mono" style={{ whiteSpace: 'nowrap' }}>
                    {fmt(row.raw_value, 1)} <span className="text-muted">{row.raw_unit}</span>
                  </td>

                  <td className="kgco2e-cell td-num">
                    {fmt(row.kgco2e, 2)}
                  </td>

                  <td><ScopePill scope={row.scope} /></td>

                  <td>
                    <StatusBadge status={row.status} />
                    {row.flagged_reason && (
                      <div className="text-sm text-muted" style={{ marginTop: '0.2rem', maxWidth: 160 }} title={row.flagged_reason}>
                        {row.flagged_reason.slice(0, 50)}{row.flagged_reason.length > 50 ? '…' : ''}
                      </div>
                    )}
                  </td>

                  <td>
                    <div className="row-actions">
                      {row.status !== 'LOCKED' && row.status !== 'APPROVED' && (
                        <button
                          id={`approve-btn-${row.id.slice(0,8)}`}
                          className="btn btn-sm btn-primary"
                          onClick={() => handleApprove(row)}
                          disabled={approvingId === row.id}
                          title="Approve this row"
                        >
                          {approvingId === row.id ? <span className="spinner" /> : '✅'}
                        </button>
                      )}

                      {row.status !== 'LOCKED' && (
                        <>
                          <button
                            id={`flag-btn-${row.id.slice(0,8)}`}
                            className="btn btn-sm btn-ghost"
                            onClick={() => setFlagRow(row)}
                            title="Flag this row"
                          >🚩</button>

                          <button
                            id={`edit-btn-${row.id.slice(0,8)}`}
                            className="btn btn-sm btn-ghost"
                            onClick={() => setEditRow(row)}
                            title="Edit values"
                          >✏️</button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="pagination">
          <button
            id="prev-page-btn"
            className="btn btn-secondary btn-sm"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
          >← Prev</button>
          <span className="page-info">Page {page} of {totalPages} ({count} rows)</span>
          <button
            id="next-page-btn"
            className="btn btn-secondary btn-sm"
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >Next →</button>
        </div>
      )}

      {/* Modals */}
      {flagRow && (
        <FlagModal
          row={flagRow}
          onClose={() => setFlagRow(null)}
          onSaved={() => { setFlagRow(null); fetchRows(page, filters) }}
        />
      )}

      {editRow && (
        <EditModal
          row={editRow}
          onClose={() => setEditRow(null)}
          onSaved={() => { setEditRow(null); fetchRows(page, filters) }}
        />
      )}

      {showLock && (
        <LockModal
          selectedIds={selectedApproved}
          onClose={() => setShowLock(false)}
          onSaved={() => { setShowLock(false); setSelected(new Set()); fetchRows(page, filters) }}
        />
      )}
    </div>
  )
}
