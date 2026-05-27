# DECISIONS.md — Ambiguity Resolution Log
**Breathe ESG · Carbon Emissions Ingestion Platform**

Every non-obvious decision made during implementation, with the reasoning and what we'd ask the PM before going to production.

---

## Source 1 — SAP Fuel & Procurement

### Decision: Flat-file CSV export, not OData or IDoc

**The ambiguity:** SAP exposes data in at least four ways — OData services (SAP Gateway), IDocs (batch integration), BAPI function modules (direct RFC), and flat-file CSV/Excel exports from transactions like SE16, MB52, or custom reports. Each has different column names, encoding, and frequency guarantees.

**What we chose:** Semicolon-delimited flat-file CSV, SAP MM module output (transaction MB51 / ME2M style). This is the most common format sent by a client's SAP team when they don't have an integration set up — they run a report, export to file, send it over.

**Why:**
- OData requires the client's SAP system to expose a Gateway endpoint, which requires Basis team involvement and firewall rules. A new enterprise client in a 4-day prototype window will not have this ready.
- IDocs are designed for system-to-system automated transfer. Setting up an IDoc partner profile requires SAP admin access on both sides.
- Flat-file is what a facilities manager or SAP power user will email you with zero IT involvement — realistic for prototype onboarding.

**What we'd ask the PM:**
> "Does the client have a dedicated SAP integration team? Are they willing to expose an OData service, or will the initial data transfer be a manual CSV export from their SAP team? What transaction are they running to generate the export — this determines which columns we'll actually receive."

### Decision: SAP MM module (Materials Management), not FI or CO

**The ambiguity:** Fuel and procurement data could come from MM (goods movements, purchase orders), FI (financial accounting), or CO (controlling / cost centres). Each has different table structures and column semantics.

**What we chose:** MM module output. Columns: BUKRS (company code), WERKS (plant), BLDAT (document date), MENGE (quantity), MEINS (unit of measure), MATNR (material number), SGTXT (line item text).

**Why:** Fuel procurement in SAP is most naturally represented as a goods movement (MIGO transaction, table MSEG). The MM module tracks what was received (diesel, gas, etc.) at a plant level. FI would give you the invoice amount but not the physical quantity and unit — you'd need to back-calculate quantity from price, which introduces exchange rate and price variance noise.

**What we ignored:** WBS elements (project cost structures from PS module), batch management (CHARG field for fuel quality tracking), and valuation type. These are real SAP fields that a more complete integration would need.

### Decision: Handle YYYYMMDD and DD.MM.YYYY date formats

**The ambiguity:** SAP stores dates as YYYYMMDD internally but displays them in the user's locale format. Exports can come out in either format depending on whether the user exported via SE16 (raw), ME2M (formatted), or a custom ABAP report.

**What we chose:** Try both formats per cell. If neither parses, log a `BAD_DATE` error and skip the row.

**What we'd ask the PM:** "Can you confirm which SAP transaction the client's team uses to export this report? That determines the date format and we can hardcode it rather than guessing."

### Decision: Plant code → site name via hardcoded dict

**The ambiguity:** WERKS is a 4-character code meaningful only inside the client's SAP configuration. "1000" means nothing without the plant master data.

**What we chose:** A hardcoded dict mapping common WERKS codes to human-readable names, with a fallback of "Plant {WERKS}" for unknown codes.

**What we'd ask the PM:** "Can you get us a dump of the client's T001W table? That's the plant master — it maps every WERKS code to a name and address. We need this before go-live or analysts will see 'Plant 3200' and not know what site that is."

---

## Source 2 — Utility Electricity

### Decision: Portal CSV export, not PDF bill or API

**The ambiguity:** The PM said "utility bills as PDFs or portal scrapes." A facilities team gets electricity data in three ways: (1) download CSV from the utility supplier's self-service portal, (2) receive a paper/PDF bill, (3) use the supplier's API (rare, usually only large commercial accounts).

**What we chose:** Portal CSV export.

**Why:**
- **PDF bills:** Require OCR or a PDF parsing library (pdfplumber, Camelot). Table extraction from PDFs is fragile — bill layouts change between suppliers and between billing periods. A robust PDF parser is a 2-week project on its own.
- **APIs:** UK utility suppliers (E.ON, British Gas, EDF) do not expose self-service data APIs to SME customers. Enterprise accounts with half-hourly metering (HH data) get AMR feeds, but that's a different ingestion problem (time-series, not billing summaries).
- **Portal CSV:** Every major UK supplier (E.ON, RWE, EDF, Octopus Business) offers a "Download billing data" CSV. This is what a facilities manager actually does each month. It's a realistic, zero-IT-involvement ingestion path.

**What we ignored:** Half-hourly (HH) AMR metering data — this is 48 readings per day per meter, which is a time-series ingestion problem requiring aggregation logic. Out of scope for MVP.

**What we'd ask the PM:** "Which utility suppliers does the client use, and do they have a self-service portal login we can use to verify the actual CSV column names? Supplier portal CSV formats vary significantly."

### Decision: Store billing periods exactly as-is (no month alignment)

**The ambiguity:** Electricity bills don't align to calendar months. A billing period might be 2024-01-15 to 2024-02-18. Should we split this across months for monthly reporting?

**What we chose:** Store `billing_period_start` and `billing_period_end` exactly as received. The `activity_date` on the row is set to `billing_period_start`. No proration.

**Why:** Proration (splitting a 35-day bill across two months proportionally) requires assumptions about daily consumption patterns that we don't have. It also creates phantom rows that aren't in the source data, muddying the audit trail. The right place to do time-period allocation is in the reporting/analytics layer, not the ingestion layer.

### Decision: Grid emission factor on the Client model (location-based)

**The ambiguity:** Scope 2 can be calculated as location-based (grid average EF) or market-based (supplier-specific EF, adjusted for REGOs/PPAs). These give materially different results for clients with renewable energy contracts.

**What we chose:** Location-based only, using UK DEFRA 2023 average (0.233 kgCO2e/kWh), stored on the Client record so it's configurable per tenant.

**What we'd ask the PM:** "Does the client have any renewable energy certificates (REGOs) or Power Purchase Agreements? If yes, we need supplier-specific emission factors and a separate market-based calculation pathway — that's a significant scope addition."

---

## Source 3 — Corporate Travel

### Decision: CSV export format (Concur/Navan-style), not expense report API

**The ambiguity:** Travel data can come from Concur SAP (dominant in enterprise), Navan/TripActions (growing in scale-ups), Cytric, Amadeus, or manual expense submissions in Excel.

**What we chose:** CSV export in Concur/Navan format. Columns: trip_id, traveler_id, travel_date, origin, destination, transport_mode, distance_km, nights, cabin_class, cost_usd.

**Why:** Concur's "Expense Report" CSV export is downloadable by any admin without API credentials. Navan/TripActions has an identical export format for travel spend data. The column names we used are directly from Concur's standard export — not invented. An API integration would require OAuth setup with the client's Concur instance, which is a multi-day IT engagement.

### Decision: IATA code lookup dict, not great-circle distance API

**The ambiguity:** Flight rows often have only origin/destination airport codes, no distance. ICAO's Carbon Emissions Calculator and the OAG API can return great-circle distances but require registration and API keys.

**What we chose:** A hardcoded dict of 17 common city pairs. If the route is unknown, the row is created with `status=NEEDS_DISTANCE` — it appears in the dashboard but doesn't contribute to totals until an analyst fills in the distance.

**Why:** For a 4-day prototype, the dict covers the routes that will appear in a typical UK-headquartered enterprise's travel data (LHR, FRA, AMS, CDG, DXB, BOM, DEL, SIN, NRT, JFK). The NEEDS_DISTANCE status is honest — it tells the analyst exactly what's missing rather than silently using a wrong value.

**What we'd ask the PM:** "What's the client's primary office location and their top 10 travel routes? We can prioritise the lookup dict to cover 90% of their volume before go-live. For production, should we integrate the ICAO API or the OpenFlights dataset?"

### Decision: Emission factors by cabin class for flights

**The ambiguity:** The BEIS 2023 guidance provides per-km emission factors for economy, business, and first class on long-haul flights (business class is 2x economy due to seat footprint). Some frameworks use a single average factor.

**What we chose:** Differentiated factors: Economy 0.255, Business 0.510, First 0.765 kgCO2e/km. If cabin_class is missing, we default to economy and log nothing (most conservative choice for Scope 3).

**Why:** For a consulting firm or financial services company, senior staff flying business class represents a disproportionate share of travel emissions. Using a single average factor would significantly undercount Scope 3 Category 6. The differentiated approach is more defensible to auditors.

### Decision: HOTEL as a separate transport_mode with per-night EF

**The ambiguity:** Hotel stays are Scope 3 Category 6 (business travel) but are often listed as separate line items in Concur alongside flights. Should they be in the same table?

**What we chose:** Yes — same `EmissionRow` table, `transport_mode=HOTEL`, `raw_value=nights`, emission factor 31.0 kgCO2e/night (BEIS 2023, UK average hotel).

**Why:** A Concur expense report mixes flights, hotels, trains, and car hire in one export. Separating them into different tables would require splitting a single source file into multiple ingest calls, which adds complexity without benefit. The `extra_data` JSON field preserves all hotel-specific fields.

---

## Authentication & access

### Decision: Simple JWT, one hardcoded analyst user

**The ambiguity:** A real system needs invite-based onboarding, password reset, MFA, and session management.

**What we chose:** JWT with an 8-hour access token lifetime, one pre-seeded analyst user (`analyst / analyst123`), and a management command to create them.

**Why:** The PM said "let our analysts review and sign off" — plural analysts, but for a 4-day prototype with one client, one user is demonstrably sufficient. The UserProfile → Client link is already in the model, so adding users is a Django admin operation, not a code change.

**What we'd ask the PM:** "How many analysts will use this per client? Do we need role-based access (some analysts can only view, others can approve)? Does the client use SSO (SAML/OIDC)?"
