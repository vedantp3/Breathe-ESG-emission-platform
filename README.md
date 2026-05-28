# Breathe ESG Carbon Emissions Platform

A full-stack prototype for ingesting, normalizing, and reviewing corporate greenhouse gas emissions data across three operational sources:

- SAP fuel and procurement data for Scope 1
- Utility electricity data for Scope 2
- Corporate travel data for Scope 3

The goal of the project is not just file upload. It is to turn messy operational exports into audit-friendly emission records that analysts can review, correct, approve, and lock before reporting.

## Live Demo

- Frontend: [https://breathe-esg-emission-platform.vercel.app/](https://breathe-esg-emission-platform.vercel.app/)
- Backend: [https://breathe-esg-emission-platform.onrender.com/api/](https://breathe-esg-emission-platform.onrender.com/api/)
- Demo login:
  - Username: `analyst`
  - Password: `analyst123`

Note: the Render free backend may take a short time to wake up after inactivity.

## What This Project Solves

Sustainability teams rarely receive clean, consistent emissions data. Different departments export data from different systems, each with different:

- column names
- units
- date formats
- quality issues
- business rules

This platform solves that by:

1. accepting source-specific CSV uploads
2. parsing each source with dedicated ingestion logic
3. converting records into one normalized emissions model
4. logging row-level errors without failing the whole file
5. giving analysts a review workflow before final audit lock

## Key Features

- JWT-based analyst login
- Multi-tenant data model using `Client` and `UserProfile`
- Separate ingestion pipelines for SAP, utility, and travel
- Row-level error logging through `IngestionError`
- Unified `EmissionRow` review table across all sources
- Edit tracking that preserves original values on first correction
- Status workflow: `PENDING -> FLAGGED / NEEDS_DISTANCE / APPROVED -> LOCKED`
- Upload history with batch-level error visibility
- Summary dashboard for scope totals and review counts

## Tech Stack

### Backend

- Django
- Django REST Framework
- Simple JWT
- PostgreSQL
- Pandas for CSV parsing
- Gunicorn for deployment

### Frontend

- React
- Vite
- React Router
- Axios

## Architecture Overview

### Backend flow

1. Analyst uploads a CSV file.
2. Backend creates an `UploadBatch`.
3. A source-specific parser reads and validates the file.
4. Each valid row becomes an `EmissionRow`.
5. Each invalid row becomes an `IngestionError`.
6. Analysts review rows in the dashboard and decide whether to approve, flag, edit, or lock them.

### Core models

- `Client`: tenant/company boundary
- `UserProfile`: connects a Django user to a client and role
- `UploadBatch`: one uploaded file and its metadata
- `EmissionRow`: one normalized emission event
- `IngestionError`: one non-fatal parsing or validation issue

For the full data model rationale, see [MODEL.md](/D:/Placement/Companies/breathe/MODEL.md).

## Supported Data Sources

### 1. SAP Fuel and Procurement

- Scope: 1
- Format: semicolon-delimited CSV
- Example columns: `BUKRS`, `WERKS`, `BLDAT`, `MENGE`, `MEINS`, `MATNR`, `SGTXT`
- Handles multiple SAP date formats
- Uses material-based emission factor lookup

### 2. Utility Electricity

- Scope: 2
- Format: comma-delimited CSV
- Example columns: `meter_id`, `site_name`, `billing_period_start`, `billing_period_end`, `consumption_kwh`, `consumption_unit`
- Normalizes `MWh` and `GWh` to `kWh`
- Uses a client-specific grid emission factor

### 3. Corporate Travel

- Scope: 3
- Format: comma-delimited CSV
- Example columns: `trip_id`, `traveler_id`, `travel_date`, `origin`, `destination`, `transport_mode`, `distance_km`
- Supports `FLIGHT`, `TRAIN`, `CAR`, and `HOTEL`
- Flags unknown flight routes as `NEEDS_DISTANCE` instead of silently guessing

## Local Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py seed_analyst
python manage.py runserver
```

Backend runs at `http://localhost:8000/api/`

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`

## Required Environment Variables

### Backend

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `ALLOWED_HOSTS`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `FRONTEND_URL`

### Frontend

- `VITE_API_BASE_URL`

## Sample Data and Expected Results

Upload the files in [sample_data](/D:/Placement/Companies/breathe/sample_data):

| File | Source | Expected Result |
|---|---|---|
| `sap_sample.csv` | SAP Fuel | 19 rows created, 1 `UNKNOWN_MATERIAL` warning |
| `utility_sample.csv` | Utility Electricity | 14 rows created, 0 errors |
| `travel_sample.csv` | Corporate Travel | 25 rows created, 2 rows flagged as `NEEDS_DISTANCE` |

## Main API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/auth/token/` | Login and get JWT tokens |
| POST | `/api/auth/token/refresh/` | Refresh access token |
| POST | `/api/ingest/sap/` | Upload SAP CSV |
| POST | `/api/ingest/utility/` | Upload utility CSV |
| POST | `/api/ingest/travel/` | Upload travel CSV |
| GET | `/api/rows/` | List normalized rows with filters |
| PATCH | `/api/rows/{id}/` | Edit row values and notes |
| PATCH | `/api/rows/{id}/approve/` | Approve a row |
| PATCH | `/api/rows/{id}/flag/` | Flag a row |
| POST | `/api/rows/lock/` | Bulk lock approved rows |
| GET | `/api/uploads/` | List upload batches |
| GET | `/api/uploads/{id}/` | View batch details and errors |
| GET | `/api/summary/` | Dashboard summary metrics |

All protected endpoints require:

```text
Authorization: Bearer <access_token>
```

## Frontend Pages

- `/login`: analyst authentication
- `/upload`: upload source files
- `/dashboard`: review, approve, flag, edit, and lock rows
- `/uploads`: upload history and ingestion errors

## Project Structure

```text
breathe/
├── backend/
│   ├── breathe/                  # Django project config
│   ├── core/
│   │   ├── ingestion/            # Source-specific parsers
│   │   ├── management/commands/  # seed_analyst command
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── urls.py
│   │   └── views.py
│   ├── requirements.txt
│   ├── Procfile
│   ├── render.toml
│   └── railway.json
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   └── pages/
│   ├── package.json
│   └── vercel.json
├── sample_data/
├── MODEL.md
├── DECISIONS.md
├── SOURCES.md
└── TRADEOFFS.md
```

## Important Design Decisions

- Every query is scoped by client to avoid cross-tenant leakage.
- Ingestion is resilient: one bad row does not fail the whole upload.
- Raw and normalized values are both stored for auditability.
- The upload batch is stored before parsing begins, so failed imports are still traceable.
- Travel rows with unknown route distance are marked `NEEDS_DISTANCE` instead of being dropped or guessed.
- Edit tracking preserves the original values on the first analyst correction.

## Known Tradeoffs

- Emission factors are hardcoded for the prototype.
- Utility ingestion supports CSV exports, not PDF bills.
- Edit history is single-level, not full version history.
- Flight distance lookup uses a small in-code route map instead of a live aviation dataset or API.

More detail:

- [DECISIONS.md](/D:/Placement/Companies/breathe/DECISIONS.md)
- [TRADEOFFS.md](/D:/Placement/Companies/breathe/TRADEOFFS.md)
- [SOURCES.md](/D:/Placement/Companies/breathe/SOURCES.md)

## Production Improvements

- Replace hardcoded emission factors with versioned external factors
- Add year- and region-specific electricity grid factors
- Replace static flight route lookup with a real distance source
- Add full audit history such as `django-simple-history`
- Move file storage to S3 or GCS
- Add role-based permissions and stronger auth lifecycle management
- Add async ingestion for large files

## Interview Summary

If you need to explain the project quickly:

> This is a Django and React ESG data platform that ingests emissions data from SAP, utility, and travel exports, normalizes them into a unified review model, logs row-level issues without crashing uploads, and gives analysts an approval workflow before audit lock.

