# MODEL.md — Data Model Design
**Breathe ESG · Carbon Emissions Ingestion Platform**

---

## Why this document matters

The data model is the hardest part of this problem. Getting it wrong means either (a) you can't join data across sources cleanly, (b) the audit trail is incomplete, or (c) multi-tenancy is bolted on as an afterthought. This document explains every structural decision made and what we'd change in a production system.

---

## Entity Relationship Overview

```
auth.User (Django built-in)
    │ 1-to-1
    ▼
UserProfile ──── FK ───► Client
    (role: ANALYST | ADMIN)       (name, slug, grid_ef_kwh)
                                        │
                            ┌───────────┴────────────┐
                            │ 1                       │ 1
                            ▼ n                       ▼ n
                       UploadBatch              EmissionRow
                       (source_type,             (source_type, scope,
                        filename, who,            activity_date, site,
                        when, row_count,          raw_value, raw_unit,
                        error_count)              kgco2e, status,
                            │ 1                   approved_by, locked_at,
                            ▼ n                   original_*, edited_by,
                       IngestionError             extra_data JSON)
                       (row_number,
                        error_type,
                        raw_line)
```

---

## Multi-tenancy design

**Decision:** Every model has a direct `client` ForeignKey. All querysets are filtered by `request.user.profile.client` in every view — no query ever runs without a client filter.

**Why not row-level security (Postgres RLS)?**
RLS is powerful but couples your security model to the database layer, making it invisible to the ORM and harder to test. For a prototype with one analyst per tenant, application-layer scoping is sufficient and easier to reason about.

**Why not separate schemas per tenant?**
Schema-per-tenant (e.g. django-tenants) is the right call at scale but adds complexity to migrations and connection pooling. At prototype stage, shared schema with FK scoping is the pragmatic choice. The FK is indexed.

**What we'd change at scale:** Evaluate Postgres RLS for defence-in-depth once the analyst count per deployment exceeds ~10 clients.

---

## The `EmissionRow` model — design rationale

This is the core normalised record. Every field has a reason.

### Source-of-truth tracking
```
batch (FK → UploadBatch)   ← which file produced this row
batch.original_filename     ← what was uploaded
batch.uploaded_by           ← who uploaded it
batch.uploaded_at           ← when
```
This gives a complete chain of custody without a separate event log. You can always trace any row back to the exact file byte-for-byte.

### Raw vs normalised values
```
raw_value     — exactly what appeared in the source CSV (Decimal, never rounded)
raw_unit      — exactly what the source said ("L", "KWH", "MWh", "KG")
kgco2e        — the normalised emission value after applying unit conversion + EF
emission_factor_used  — the EF applied, stored for reproducibility
normalized_value_kwh  — intermediate step for electricity (raw → kWh → kgCO2e)
```

Storing raw values separately from normalised values means:
- An auditor can verify the calculation independently
- If an emission factor is updated, we know which rows need recalculation
- A wrong unit in the source is visible without unpicking the calculation

### Scope 1/2/3
Stored as an integer field (1/2/3) on every row, not derived from source_type. This matters because:
- In future, some SAP fuel rows may be Scope 3 (e.g. purchased goods combusted by a third party)
- The source type determines the *default* scope at ingest time; an analyst can correct it

### Status lifecycle
```
PENDING → FLAGGED         (analyst sees a problem)
        → NEEDS_DISTANCE  (auto-set: flight with unknown IATA pair)
        → APPROVED        (analyst confirms)
             → LOCKED     (final audit lock — immutable)
```
We chose a flat status field over a state machine library because the transitions are simple enough and a library would add a dependency with minimal benefit at prototype scale.

### Edit tracking
```
original_raw_value   ← copied from raw_value on first edit
original_raw_unit    ← copied from raw_unit on first edit
original_kgco2e      ← copied from kgco2e on first edit
edited_by (FK→User)
edited_at (timestamp)
```

**What this gives you:** A single-level undo / audit trail. The original value is always visible alongside the correction, stamped with who changed it.

**What it doesn't give you:** Full change history if a row is edited multiple times. For production, `django-simple-history` would record every version of every row in a separate history table. We chose not to include it in the prototype because it triples the table size and the PM said "review and sign off" — not "show me 12 versions."

### `extra_data` (JSONField)
Each source has columns that don't belong in the shared schema (SAP's BUKRS, MATNR; travel's trip_id, cabin_class). These go into `extra_data`. This avoids schema pollution while preserving all source data for debugging. In production, the important ones (e.g. trip_id for travel reconciliation) would get their own indexed columns.

---

## The `UploadBatch` model

Represents one file upload event. Key design choice: **the batch is created before parsing begins**, inside a `transaction.atomic()` block. If parsing fails mid-file, the batch record still exists with `error_count` reflecting what went wrong. This means:
- Upload history is always complete, even for failed imports
- Partial imports are visible (10 rows created, 3 errors)
- The source file is stored in media/ for re-processing if needed

---

## The `IngestionError` model

Every row-level parse error is written here, not to a log file, and the import continues. Design rationale:
- A 2000-row SAP export should not fail completely because row 47 has a German date
- Analysts can review errors in the UI, not grep server logs
- The `raw_line` field stores the original CSV text so analysts can see exactly what was wrong

---

## The `Client` model

Carries `grid_emission_factor_kgco2e_per_kwh` (default 0.233 — UK DEFRA 2023 average). This means changing the grid factor for a client requires no code change — only a database update. In production this would be a time-series table (factor changes every year; the DEFRA publication cycle is annual).

---

## What the model deliberately does not handle

- **Multiple reporting periods per client** — rows are dated but there's no "reporting year" entity. A production system would have a `ReportingPeriod` model that rows are assigned to.
- **Currency normalisation** — `cost_usd` is stored but not used in any calculation. In production, spend-based emission estimates (Scope 3 Category 1) would require FX conversion.
- **Market-based vs location-based Scope 2** — we store location-based (grid average). Market-based (using renewable energy certificates) requires a separate `supplier_ef` per meter row.
- **Organisational hierarchy** — we model Client as a flat entity. A real enterprise might have subsidiaries, divisions, and cost centres that affect Scope 3 boundary decisions.
