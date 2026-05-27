# TRADEOFFS.md — What We Deliberately Did Not Build
**Breathe ESG · Carbon Emissions Ingestion Platform**

Three deliberate cuts, each with the reasoning and the cost of the decision.

---

## 1. Live emission factor APIs (Climatiq / DEFRA)

### What we built instead
Hardcoded emission factors from BEIS 2023 Greenhouse Gas Reporting: Conversion Factors, stored as Python `Decimal` constants in each ingestion module. The UK grid factor (0.233 kgCO2e/kWh) is stored on the `Client` model and configurable via a database update without code changes.

### Why we cut it
**Climatiq** (the leading EF API) and the **DEFRA annual publication** both require decisions that belong in a product conversation, not a 4-day prototype:

- **Versioning:** DEFRA publishes new factors every June. If we pull from an API, which year's factors apply to January data ingested in July? The correct answer depends on the client's chosen reporting framework (GHG Protocol says "use factors current at reporting date"; some frameworks say "use factors from the period the activity occurred"). This is a policy decision, not a technical one.
- **Factor granularity:** Climatiq distinguishes diesel for road transport from diesel for off-road machinery (different BEIS categories). Without a product decision on which MATNR codes map to which activity types, we'd be applying the wrong granularity silently.
- **Cost and reliability:** Climatiq is paid. A prototype that fails because an API key expires isn't a useful prototype.

### Cost of this decision
If a client changes jurisdiction (e.g. adding a US office), the emission factors would need a manual update. More critically, when DEFRA publishes updated factors, the system gives no indication that existing rows used outdated factors. A production system needs a `factor_version` field on `EmissionRow` and a re-calculation job.

---

## 2. PDF bill ingestion for utility data

### What we built instead
Portal CSV export from the utility supplier's self-service website. Every major UK supplier (E.ON, EDF, RWE, Octopus Business) provides a downloadable CSV of billing data.

### Why we cut it
PDF ingestion is **disproportionately expensive** relative to its value at prototype stage:

- **Library complexity:** `pdfplumber` or `camelot-py` can extract tables from machine-generated PDFs but fail on scanned bills (requiring Tesseract OCR). The two code paths are entirely different.
- **Layout fragility:** EDF's bill PDF layout is different from E.ON's. E.ON changed their bill layout in Q3 2023. Each supplier requires a separate extraction template, and templates break silently when the supplier redesigns their bill. This is a maintenance burden, not a one-time cost.
- **The portal CSV exists:** Every supplier that produces a PDF bill also offers the same data as a CSV download from their portal. The CSV is structured, reliable, and requires no parsing logic beyond `pd.read_csv()`. A facilities manager who can download a PDF can download a CSV.
- **What PDF ingestion buys us:** Support for clients who have only paper/email bills and no portal access — typically very small sites or legacy commercial contracts. This is edge case volume.

### Cost of this decision
A client whose facilities team receives only emailed PDF bills (no portal access) cannot use this ingestion path. They would need to manually transcribe values into a CSV template. For a prototype demo with a new client, this is acceptable. For a GA product, PDF ingestion is in the roadmap.

---

## 3. Full audit log (django-simple-history / event sourcing)

### What we built instead
Single-level edit tracking: when an analyst edits `raw_value`, `raw_unit`, or `kgco2e` for the first time, the original values are copied to `original_raw_value`, `original_raw_unit`, `original_kgco2e`. Subsequent edits overwrite the corrected value but the original is preserved. The edit is stamped with `edited_by` and `edited_at`.

### Why we cut it
**django-simple-history** (the standard Django audit library) records a full snapshot of every model instance on every save, in a separate `historical_*` table. This is the right solution for production. We chose not to include it because:

- **Storage cost:** A system with 50,000 rows and an average of 3 saves per row (ingest, edit, approve) generates 150,000 history rows. That's fine for PostgreSQL, but the ratio gets worse as approval workflows add more saves.
- **Query complexity:** The dashboard needs to show "was this row edited?" — a boolean. With django-simple-history, answering this requires a JOIN to the history table or a `has_changed()` call. With our `original_raw_value IS NOT NULL` approach, it's a single column check.
- **The prototype use case:** The PM said "review and sign off before it goes to auditors." The auditors want to know: what was the original value, who changed it, and is the current value approved? Our single-level tracking answers exactly those questions. An auditor asking "show me all 12 versions of this row" is not a prototype-stage requirement.

### Cost of this decision
If an analyst edits a row twice, we lose the intermediate value — only the first original and the final corrected value are visible. For a GHG data auditor following GHG Protocol verification guidance, this is a gap: the standard requires "a complete record of all adjustments." For a prototype review with a PM, it is not.

**What we'd add for production:** `django-simple-history` on `EmissionRow` only (not on `UploadBatch` or `IngestionError`), with a UI drawer on each row showing the full change timeline.
