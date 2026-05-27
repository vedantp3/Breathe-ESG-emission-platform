const STATUS_CONFIG = {
  PENDING:        { label: 'Pending',        icon: '⏳', cls: 'badge-pending'        },
  FLAGGED:        { label: 'Flagged',        icon: '🚩', cls: 'badge-flagged'        },
  APPROVED:       { label: 'Approved',       icon: '✅', cls: 'badge-approved'       },
  LOCKED:         { label: 'Locked',         icon: '🔒', cls: 'badge-locked'         },
  NEEDS_DISTANCE: { label: 'Needs Distance', icon: '📍', cls: 'badge-needs_distance' },
}

export function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || { label: status, icon: '?', cls: 'badge-pending' }
  return (
    <span className={`badge ${cfg.cls}`} title={status}>
      {cfg.icon} {cfg.label}
    </span>
  )
}

export function ScopePill({ scope }) {
  const labels = { 1: 'Scope 1', 2: 'Scope 2', 3: 'Scope 3' }
  return (
    <span className={`scope-pill scope-${scope}`}>
      {labels[scope] || `Scope ${scope}`}
    </span>
  )
}
