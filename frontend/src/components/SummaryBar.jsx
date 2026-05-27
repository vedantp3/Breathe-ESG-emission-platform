function fmt(val) {
  if (val == null) return '—'
  const n = parseFloat(val)
  if (isNaN(n)) return '—'
  return n.toLocaleString('en-GB', { maximumFractionDigits: 1 })
}

function fmtInt(val) {
  if (val == null) return '0'
  return parseInt(val, 10).toLocaleString('en-GB')
}

export default function SummaryBar({ data }) {
  if (!data) {
    return (
      <div className="summary-bar">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="summary-card" style={{ opacity: 0.4 }}>
            <div className="summary-label">Loading…</div>
            <div className="summary-value">—</div>
          </div>
        ))}
      </div>
    )
  }

  const cards = [
    {
      cls:   'scope-1-card',
      label: 'Scope 1 (Direct)',
      value: fmt(data.scope_1_kgco2e),
      unit:  'tCO₂e',
      raw:   data.scope_1_kgco2e,
    },
    {
      cls:   'scope-2-card',
      label: 'Scope 2 (Electricity)',
      value: fmt(data.scope_2_kgco2e),
      unit:  'tCO₂e',
      raw:   data.scope_2_kgco2e,
    },
    {
      cls:   'scope-3-card',
      label: 'Scope 3 (Value Chain)',
      value: fmt(data.scope_3_kgco2e),
      unit:  'tCO₂e',
      raw:   data.scope_3_kgco2e,
    },
    {
      cls:   'total-card',
      label: 'Total Emissions',
      value: fmt(data.total_kgco2e),
      unit:  'tCO₂e total',
      raw:   data.total_kgco2e,
    },
    {
      cls:   'pending-card',
      label: 'Pending Review',
      value: fmtInt(data.pending_count),
      unit:  'rows to review',
    },
    {
      cls:   'flagged-card',
      label: 'Flagged',
      value: fmtInt(data.flagged_count),
      unit:  'rows flagged',
    },
  ]

  return (
    <div className="summary-bar" role="region" aria-label="Emissions summary">
      {cards.map((card) => (
        <div key={card.label} className={`summary-card ${card.cls}`}>
          <div className="summary-label">{card.label}</div>
          <div className="summary-value">{card.value}</div>
          <div className="summary-unit">{card.unit}</div>
        </div>
      ))}
    </div>
  )
}
