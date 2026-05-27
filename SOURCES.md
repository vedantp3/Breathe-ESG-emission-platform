# SOURCES.md — Research Notes Per Data Source
**Breathe ESG · Carbon Emissions Ingestion Platform**

For each of the three sources: what real-world format we researched, what we learned, what our sample data looks like and why, and what would break in a real deployment.

---

## Source 1 — SAP Fuel & Procurement

### What we researched

SAP's Materials Management (MM) module is the system of record for fuel and direct material procurement in manufacturing-heavy enterprises. The relevant data sits in tables:

- **EKKO / EKPO** — Purchase order header / line items (what was ordered)
- **MIGO / MSEG** — Goods movement / material document segment (what was actually received)
- **MBEW** — Material valuation (price, but not physical quantity)

A typical client export comes from **transaction MB51** (Material Documents List) or a custom ABAP report using SE16/SE16N on table MSEG. The relevant columns in a real MSEG-based export are:

| SAP Field | Meaning | Example |
|-----------|---------|---------|
| BUKRS | Company code | 1000 |
| WERKS | Plant code | 2000 |
| BLDAT | Document date | 20240315 or 15.03.2024 |
| MENGE | Quantity | 450.000 |
| MEINS | Unit of measure | L, KG, M3 |
| MATNR | Material number | DIESEL-001, 000000000000100345 |
| SGTXT | Short text / line item description | "Diesellieferung Halle 3" |
| BWART | Movement type | 101 (goods receipt), 201 (consumption) |
| LGORT | Storage location | 0001 |

**What we learned:**
- MATNR is the critical field. In a well-configured SAP system, MATNR is an 18-character padded string like `000000000000100345`. The material text lives in table MARA (material master) — not in the flat export. Without the MARA join, you're left guessing material type from the MATNR number or the SGTXT text.
- German locale decimal separators: MENGE often comes as `1.200,500` (period = thousands, comma = decimal) in German locale exports. We handle this by replacing commas with periods for `Decimal()` parsing.
- Date formats: SE16 exports use YYYYMMDD (raw database format). Custom ABAP reports formatted for display use DD.MM.YYYY. Both appear in the wild.
- MEINS is standardised within each SAP system but not across systems. "LIT" (litres) is common in German configs; "L" in English configs. We handle known aliases.

### What our sample data looks like

`sap_sample.csv` — 20 rows, semicolon-delimited, representing 5 months of fuel procurement across 6 plant codes (WERKS 1000–5000). Includes:
- Mixed date formats: rows 1–9 use YYYYMMDD, rows 10–20 use DD.MM.YYYY
- Mixed units: diesel in L (most rows), natural gas in M3, coal in KG
- MATNR values like `DIESEL-001`, `NATGAS-004` (simplified for readability — in a real export these would be padded numbers)
- One row with `BIOFUEL-007` (an unusual material) to trigger the UNKNOWN_MATERIAL warning path
- All 6 WERKS codes mapped to realistic German site names

### What would break in a real deployment

1. **MATNR resolution without MARA:** Our parser uses substring matching on MATNR (looking for "DIESEL", "NATGAS" etc). A real SAP export has MATNR like `000000000000102847` — you get no fuel type from the number alone. You need a join to MARA (or the client's material classification) to know what the material is.

2. **German decimal separators:** A real German-locale SAP export of MENGE `1.450,500` (one thousand four hundred fifty point five) would be misread as `1.450` by our current parser. We replace commas with periods but don't handle the thousands-separator period. Fix: `menge_str.replace('.', '').replace(',', '.')` applied in the right order.

3. **BWART (movement type) filtering:** Table MSEG contains goods receipts (101), goods issues (201), returns (122), and reversals (102). An emission calculation should only include consumption movements (201, 261) and receipts (101). Without filtering on BWART, you'd double-count goods that are received and then issued.

4. **Multi-currency valuation:** If the client operates across EUR/USD, the DMBTR (local currency amount) field mixes currencies. Our model ignores financial amounts, but a spend-based Scope 3 calculation would need this.

---

## Source 2 — Utility Electricity

### What we researched

UK utility supplier CSV formats were reviewed for three major suppliers:

**E.ON Business Energy** portal export:
- Comma-delimited, UTF-8
- Columns: `Account Number`, `MPAN`, `Site Name`, `Billing Period From`, `Billing Period To`, `kWh`, `Unit Rate (p/kWh)`, `Standing Charge (£)`, `VAT`, `Total (£)`
- Billing periods: typically 28-35 days, never calendar months
- Note: "kWh" in their export header is the column name for consumption; the unit column is absent (unit is always kWh for standard meters)

**RWE/npower Business Solutions** portal export:
- Columns: `Meter Reference`, `Site`, `Period Start`, `Period End`, `Consumption`, `Unit`, `Tariff`, `Supplier`
- Includes a `Unit` column — sometimes `MWh` for large industrial meters (>100kW peak demand), sometimes `kWh` for SME meters
- Half-hourly meters get a separate export format (48 readings per day — not handled by us)

**Octopus Energy for Business**:
- Similar structure to E.ON, consumption always in kWh
- HH meter data is available via their API only (not portal CSV)

**What we learned:**
- The `consumption_unit` column only exists if the supplier exports industrial data. SME portal exports assume kWh and omit it. Our parser handles both cases.
- Billing periods straddling month boundaries are universal — we've never seen a UK electricity bill that aligns to a calendar month.
- MPAN (Meter Point Administration Number) is the UK standard meter identifier (13 digits). Our `meter_id` field corresponds to this.
- Tariff codes are supplier-specific and opaque (`TRF-HH-01` means nothing without the supplier's rate card).

### What our sample data looks like

`utility_sample.csv` — 14 rows, 4 meters across 4 sites. Includes:
- MTR-001 (Hamburg HQ) — kWh, ~5 week billing periods
- MTR-002 (Frankfurt Plant) — **MWh** (industrial meter), requires MWh→kWh normalisation
- MTR-003 (Munich Distribution) — kWh, ~5 week billing periods
- MTR-004 (Berlin Site) — kWh, shorter billing cycles
- All billing periods straddle month boundaries deliberately (e.g. 2024-01-15 to 2024-02-18)
- Realistic German utility suppliers: E.ON Energie Deutschland, RWE AG, Stadtwerke München, Vattenfall Wärme Berlin

### What would break in a real deployment

1. **Half-hourly (HH) metering data:** Sites with peak demand >100kW use HH meters. These export as 48 rows per day per meter — 17,520 rows per meter per year. Our CSV ingestion would technically work but the `activity_date` logic (using `billing_period_start`) doesn't make sense for sub-daily data. HH data needs aggregation before it can be treated as a billing period.

2. **Multi-fuel bills:** Some utility suppliers include gas and electricity on the same bill. Our parser assumes every row is electricity. A row with `consumption_unit=MWh` of gas would be processed as electricity and get the wrong emission factor.

3. **Reactive power charges:** UK industrial sites are billed for both active (kWh) and reactive (kVArh) power. The reactive component is a power quality charge, not an energy consumption — it should not be included in emission calculations. Some exports mix both on the same row.

4. **Net metering / solar export:** A site with rooftop solar may have negative consumption values for periods when they export to the grid. Our parser raises a validation error for negative values (`raw_consumption < 0`). In reality, these are legitimate and should either be subtracted from Scope 2 (location-based method allows this with limitations) or flagged for analyst review.

---

## Source 3 — Corporate Travel

### What we researched

**SAP Concur** is the dominant corporate travel platform for enterprises above 1,000 employees (~65% market share in Europe). **Navan** (formerly TripActions) is the fast-growing challenger for scale-ups.

**Concur Expense Report CSV export** (actual column names from SAP Concur documentation):
- `ReportId`, `EmployeeId`, `TransactionDate`, `ExpenseType`, `MerchantName`
- `Amount`, `Currency`, `Distance`, `DistanceUnit`, `AirfareClass`
- `DepartureCity`, `ArrivalCity` (IATA code or free-text city name)
- `HotelCheckIn`, `HotelCheckOut`, `HotelCity`

**Navan Travel Export** (from Navan admin portal CSV):
- `trip_id`, `traveler_email`, `booking_date`, `departure_date`
- `origin_iata`, `destination_iata`, `airline`, `fare_class`
- `distance_km` (not always populated), `total_cost_usd`, `transport_type`

**What we learned:**
- IATA airport codes are used for flights, but **hotel rows use city names**, not IATA codes. Origin/destination for hotels is meaningless for distance calculation.
- `distance_km` is populated by Navan for bookings where the airline provides it, but is blank for ~30% of flight rows and nearly all rail rows.
- Cabin class mapping varies: Concur uses `"First Class"`, `"Business"`, `"Economy"`, `"Coach"`. Navan uses `"F"`, `"J"`, `"Y"`. We normalise to uppercase ECONOMY/BUSINESS/FIRST.
- Hotel stays in Concur are separate `ExpenseType` rows (`"Hotel"`) with a nightly rate, not a distance.
- Ground transport in Concur includes `"Taxi"`, `"Car Rental"`, `"Personal Car"`, `"Mileage"` — the last two have different emission factors than a hire car. We simplify to CAR.
- The GHG Protocol for Scope 3 Category 6 recommends DEFRA's EFs for UK-domiciled companies. The ICAO Carbon Emissions Calculator (CEC) is used by airlines for CORSIA compliance and gives slightly different per-km values.

### What our sample data looks like

`travel_sample.csv` — 25 rows across January–April 2024, including:
- **FLIGHT rows:** Mix of known routes (BOM↔LHR, DEL↔DXB, CDG↔JFK etc.) and unknown routes (`BOM→SIN`, `LHR→MCT`) that trigger NEEDS_DISTANCE
- **Known routes with distance:** FRA↔LHR (631km), CDG↔JFK (5837km), HKG↔SIN (2659km) — these have `distance_km` populated
- **Known routes without distance:** LHR↔DXB — uses IATA dict lookup (5500km)
- **TRAIN rows:** LHR↔CDG (344km, Eurostar), LHR↔FRA (631km)
- **HOTEL rows:** 3 hotel stays in LHR with 2, 3, 4 nights respectively
- **CAR rows:** UK mileage claims (185km, 240km, 310km)
- **Mixed cabin classes:** ECONOMY (majority), BUSINESS (senior staff long-haul), FIRST (one HKG trip)
- **EMP-042** is a frequent flyer (BOM-LHR base route) — realistic for an employee commuting between offices

### What would break in a real deployment

1. **IATA dict coverage:** Our dict has 17 city pairs. A real enterprise with 500 employees across 20 countries will have hundreds of unique routes. We estimate the dict covers ~60% of a typical UK-HQ corporate travel programme. The NEEDS_DISTANCE flag is the safety net — nothing is silently wrong — but analysts would have a lot of rows to fill in.

2. **Hotel location vs emission factor:** Our hotel EF (31.0 kgCO2e/night) is the UK average (BEIS). A hotel in Singapore has a different grid intensity than one in Norway. A production system needs the hotel's country to apply the right EF. Our sample data only stores origin/destination as IATA codes, not hotel country.

3. **Concur free-text city names:** Many Concur exports use city names (`"London Heathrow"`, `"Mumbai"`) instead of IATA codes. Our IATA lookup fails silently on these. A production parser needs a city→IATA mapping table (OpenFlights has ~7,000 airports).

4. **Multileg itineraries:** A trip from Mumbai to London with a stop in Dubai is one `trip_id` in Concur but two flight legs with different distances. Concur exports this as either one row (total distance, if calculated) or two rows (one per leg). Our parser handles one row per leg; a multileg trip as a single row would get the wrong distance applied.

5. **Expense vs booking data:** Concur has two data sources: booking data (from the GDS/airline at time of booking) and expense reports (submitted by the employee after travel). Distances in booking data are more reliable; expense report distances are sometimes manually entered and unreliable. A production system should prefer booking data.
