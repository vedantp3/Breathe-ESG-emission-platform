import { useState, useRef } from 'react'
import api from '../api/axios.js'

const SOURCES = [
  {
    key:      'sap',
    endpoint: '/ingest/sap/',
    label:    'SAP Fuel & Procurement',
    scope:    'Scope 1 — Direct emissions',
    icon:     '🏭',
    iconCls:  'icon-sap',
    hint:     'Semicolon-delimited SAP MM flat file. Columns: BUKRS, WERKS, BLDAT, MENGE, MEINS, MATNR, SGTXT',
    accept:   '.csv',
  },
  {
    key:      'utility',
    endpoint: '/ingest/utility/',
    label:    'Utility Electricity',
    scope:    'Scope 2 — Indirect (grid)',
    icon:     '⚡',
    iconCls:  'icon-utility',
    hint:     'Comma-delimited portal export. Columns: meter_id, site_name, billing_period_start/end, consumption_kwh, consumption_unit, tariff_code, supplier_name',
    accept:   '.csv',
  },
  {
    key:      'travel',
    endpoint: '/ingest/travel/',
    label:    'Corporate Travel',
    scope:    'Scope 3 — Value chain',
    icon:     '✈️',
    iconCls:  'icon-travel',
    hint:     'Concur/Navan-style export. Columns: trip_id, traveler_id, travel_date, origin, destination, transport_mode, distance_km, nights, cabin_class, cost_usd',
    accept:   '.csv',
  },
]

function UploadCard({ source }) {
  const [file,    setFile]    = useState(null)
  const [loading, setLoading] = useState(false)
  const [result,  setResult]  = useState(null)
  const [error,   setError]   = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef(null)

  function pickFile(f) {
    if (f && f.name.endsWith('.csv')) {
      setFile(f)
      setResult(null)
      setError(null)
    } else if (f) {
      setError({ message: 'Please select a .csv file.' })
    }
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    pickFile(f)
  }

  async function handleUpload() {
    if (!file) return
    setLoading(true)
    setResult(null)
    setError(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await api.post(source.endpoint, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(res.data)
      setFile(null)
      if (inputRef.current) inputRef.current.value = ''
    } catch (err) {
      setError({
        message: err.response?.data?.error || 'Upload failed. Check the server logs.',
      })
    } finally {
      setLoading(false)
    }
  }

  function clearFile() {
    setFile(null)
    setResult(null)
    setError(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div className="upload-source-card">
      {/* Header */}
      <div className="upload-source-header">
        <div className={`upload-source-icon ${source.iconCls}`}>
          {source.icon}
        </div>
        <div>
          <div className="upload-source-name">{source.label}</div>
          <div className="upload-source-scope">{source.scope}</div>
        </div>
      </div>

      {/* Drop zone */}
      <div
        className={`upload-zone ${dragOver ? 'drag-over' : ''}`}
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-label={`Upload ${source.label} CSV`}
        onKeyDown={e => e.key === 'Enter' && inputRef.current?.click()}
      >
        <span className="upload-zone-icon">📂</span>
        <div className="upload-zone-text">
          {file ? 'File selected — click Upload to proceed' : 'Drop CSV here or click to browse'}
        </div>
        <div className="upload-zone-hint">{source.hint}</div>
        <input
          ref={inputRef}
          type="file"
          accept={source.accept}
          style={{ display: 'none' }}
          id={`file-input-${source.key}`}
          onChange={e => pickFile(e.target.files[0])}
        />
      </div>

      {/* Selected file display */}
      {file && (
        <div className="file-selected">
          <span>📄</span>
          <span className="file-selected-name">{file.name}</span>
          <span className="text-muted text-sm">
            ({(file.size / 1024).toFixed(1)} KB)
          </span>
          <button
            className="btn btn-ghost btn-sm"
            onClick={clearFile}
            aria-label="Remove file"
          >✕</button>
        </div>
      )}

      {/* Upload button */}
      <button
        id={`upload-btn-${source.key}`}
        className="btn btn-primary"
        onClick={handleUpload}
        disabled={!file || loading}
      >
        {loading
          ? <><span className="spinner" /> Uploading…</>
          : `Upload ${source.label}`
        }
      </button>

      {/* Result */}
      {result && (
        <div className={`alert ${result.errors_logged > 0 ? 'alert-warning' : 'alert-success'}`}>
          <span className="alert-icon">
            {result.errors_logged > 0 ? '⚠️' : '✅'}
          </span>
          <div>
            <strong>
              {result.rows_created} row{result.rows_created !== 1 ? 's' : ''} imported
              {result.errors_logged > 0 && `, ${result.errors_logged} error${result.errors_logged !== 1 ? 's' : ''}`}
            </strong>
            <div className="text-sm" style={{ marginTop: '0.25rem' }}>
              Batch ID: <span className="mono">{result.batch_id?.slice(0, 8)}…</span>
            </div>

            {result.errors?.length > 0 && (
              <div className="error-detail-list" style={{ marginTop: '0.5rem' }}>
                {result.errors.slice(0, 6).map((err, i) => (
                  <div key={i} className="error-detail-item">
                    Row {err.row_number} [{err.error_type}]: {err.error_message}
                  </div>
                ))}
                {result.errors.length > 6 && (
                  <div className="text-muted text-sm">
                    +{result.errors.length - 6} more — see Upload History for full detail
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {error && (
        <div className="alert alert-error">
          <span className="alert-icon">❌</span>
          <div>{error.message}</div>
        </div>
      )}
    </div>
  )
}

export default function UploadPage() {
  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">📤 Upload Emissions Data</h1>
          <p className="page-subtitle">
            Import CSV files from SAP, utility portals, or your travel management system.
            Each file is validated, normalised, and queued for analyst review.
          </p>
        </div>
      </div>

      <div className="upload-grid">
        {SOURCES.map(source => (
          <UploadCard key={source.key} source={source} />
        ))}
      </div>
    </div>
  )
}
