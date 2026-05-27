# Breathe ESG — Carbon Emissions Data Platform

A production-quality prototype for ingesting, normalising, and reviewing corporate GHG emissions across SAP Fuel (Scope 1), Utility Electricity (Scope 2), and Corporate Travel (Scope 3) sources.

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+ running locally (or Docker)

---

## 1. Backend Setup

```powershell
# Create and activate virtual environment
cd backend
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment (edit as needed)
copy .env.example .env

# Create the PostgreSQL database
# (psql must be on PATH, or use pgAdmin)
psql -U postgres -c "CREATE DATABASE breathe_esg;"

# Run migrations
python manage.py migrate

# Seed the analyst user (username: analyst / password: analyst123)
python manage.py seed_analyst

# Start the Django dev server
python manage.py runserver
```

The API is now available at **http://localhost:8000/api/**

---

## 2. Frontend Setup

```powershell
cd frontend
npm install
npm run dev
```

The React app is now at **http://localhost:5173**

---

## 3. Login

Open http://localhost:5173/login and sign in with:
- **Username:** `analyst`
- **Password:** `analyst123`

---

## 4. Upload Sample Data

Go to **Upload Data** (/upload) and upload the files from `sample_data/`:

| File | Source | Expected Result |
|------|--------|----------------|
| `sap_sample.csv` | SAP Fuel | 19 rows, 1 UNKNOWN_MATERIAL warning |
| `utility_sample.csv` | Utility | 14 rows, 0 errors |
| `travel_sample.csv` | Corporate Travel | 25 rows, 2 NEEDS_DISTANCE flagged |

---

## 5. API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/token/` | Get JWT access + refresh tokens |
| POST | `/api/auth/token/refresh/` | Refresh access token |
| POST | `/api/ingest/sap/` | Upload SAP CSV |
| POST | `/api/ingest/utility/` | Upload utility CSV |
| POST | `/api/ingest/travel/` | Upload travel CSV |
| GET | `/api/rows/` | List rows (filter: source, status, scope, date_from, date_to, search) |
| PATCH | `/api/rows/{id}/` | Edit raw_value / raw_unit / kgco2e / analyst_notes |
| PATCH | `/api/rows/{id}/approve/` | Approve a row |
| PATCH | `/api/rows/{id}/flag/` | Flag a row with reason |
| POST | `/api/rows/lock/` | Bulk lock approved rows (body: `{"row_ids": [...]}`) |
| GET | `/api/uploads/` | List upload batches |
| GET | `/api/uploads/{id}/` | Batch detail with ingestion errors |
| GET | `/api/summary/` | Dashboard summary stats |

All endpoints require `Authorization: Bearer <access_token>`.

---

## 6. Project Structure

```
breathe/
├── backend/
│   ├── breathe/          # Django project (settings, urls, wsgi)
│   ├── core/             # Main app
│   │   ├── models.py     # ERD + all models
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── ingestion/
│   │   │   ├── sap.py    # SAP Fuel parser (semicolon-delimited)
│   │   │   ├── utility.py # Electricity parser (comma-delimited)
│   │   │   └── travel.py  # Corporate travel parser (Concur/Navan)
│   │   └── management/commands/seed_analyst.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/
│       ├── App.jsx
│       ├── api/axios.js
│       ├── components/   # Navbar, StatusBadge, SummaryBar
│       └── pages/        # LoginPage, UploadPage, Dashboard, UploadHistory
└── sample_data/          # 3 realistic CSV files for testing
```

---

## Key Design Decisions

- **Client scoping**: every DB query is filtered by `request.user.profile.client` — no cross-tenant data leakage
- **Non-crashing ingestion**: every row error creates an `IngestionError` record; imports never crash mid-file
- **Edit tracking**: `original_raw_value/unit/kgco2e` preserved on first edit for single-level audit trail
- **Status lifecycle**: `PENDING → FLAGGED/APPROVED/NEEDS_DISTANCE → LOCKED` (locked rows are immutable)
- **Per-client grid factor**: `Client.grid_emission_factor_kgco2e_per_kwh` makes Scope 2 factor configurable without code changes

## TODO for Production

- [ ] Replace hardcoded emission factors with Climatiq / BEIS API
- [ ] Replace IATA distance dict with ICAO or OAG great-circle API
- [ ] Add per-region, per-year grid intensity (DEFRA, IEA, EPA eGRID)
- [ ] Use S3/GCS for file storage instead of local media/
- [ ] Add refresh-token rotation and revocation (token blacklist)
- [ ] Add django-simple-history for full audit log (vs single-level edit tracking)
- [ ] Add role-based permissions (Analyst vs Admin)
- [ ] Add celery task queue for async ingestion of large files (>10k rows)
- [ ] Add email notifications on approval/lock
- [ ] Multi-year reporting period support
