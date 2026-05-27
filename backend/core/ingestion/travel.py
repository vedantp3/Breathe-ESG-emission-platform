"""
Corporate Travel ingestion — Scope 3 emissions.

Handles Concur/Navan-style CSV export (comma-delimited):
  - Columns: trip_id, traveler_id, travel_date, origin, destination,
             transport_mode, distance_km, nights, cabin_class, cost_usd
  - Emission factors by mode (BEIS 2023):
      FLIGHT ECONOMY:  0.255 kgCO2e/km (includes RFI = 2x)
      FLIGHT BUSINESS: 0.510 kgCO2e/km
      FLIGHT FIRST:    0.765 kgCO2e/km
      TRAIN:           0.041 kgCO2e/km
      CAR:             0.171 kgCO2e/km
      HOTEL:           31.0  kgCO2e/night
  - If distance_km is null and mode is FLIGHT, attempts IATA city-pair lookup.
    If route is unknown, sets status=NEEDS_DISTANCE.

TODO: Replace IATA distance lookup with a real great-circle / OAG API.
TODO: Add rail-specific factors per country (e.g. Eurostar vs domestic).
TODO: Store actual spend for spend-based emission fallback.
"""

import logging
from decimal import Decimal, InvalidOperation
from io import StringIO

import pandas as pd

from core.models import (
    EmissionRow, IngestionError, UploadBatch,
    RowStatus, GHGScope, SourceType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Emission factors (kgCO2e per km, or per night for hotels)
# Source: BEIS Greenhouse Gas Reporting: Conversion Factors 2023
# TODO: Replace with API call to Climatiq or ICAO Carbon Emissions Calculator
# ---------------------------------------------------------------------------

FLIGHT_EF: dict[str, Decimal] = {
    "ECONOMY":  Decimal("0.255"),
    "BUSINESS": Decimal("0.510"),
    "FIRST":    Decimal("0.765"),
    "":         Decimal("0.255"),  # default to economy if unknown
}

MODE_EF: dict[str, Decimal] = {
    "TRAIN": Decimal("0.041"),
    "CAR":   Decimal("0.171"),
    "HOTEL": Decimal("31.0"),   # per night
}

# ---------------------------------------------------------------------------
# IATA city-pair lookup (one-way distances in km, bidirectional)
# TODO: Replace with ICAO or OAG real distance API.
# ---------------------------------------------------------------------------

IATA_DISTANCES: dict[frozenset, int] = {
    frozenset({"BOM", "LHR"}): 7200,   # Mumbai ↔ London Heathrow
    frozenset({"DEL", "DXB"}): 2200,   # Delhi ↔ Dubai
    frozenset({"DEL", "LHR"}): 6700,   # Delhi ↔ London Heathrow
    frozenset({"SIN", "LHR"}): 10840,  # Singapore ↔ London Heathrow
    frozenset({"JFK", "LHR"}): 5541,   # New York ↔ London Heathrow
    frozenset({"SYD", "LHR"}): 16993,  # Sydney ↔ London Heathrow
    frozenset({"DXB", "LHR"}): 5500,   # Dubai ↔ London Heathrow
    frozenset({"CDG", "LHR"}): 344,    # Paris CDG ↔ London Heathrow
    frozenset({"FRA", "LHR"}): 631,    # Frankfurt ↔ London Heathrow
    frozenset({"AMS", "LHR"}): 356,    # Amsterdam ↔ London Heathrow
    frozenset({"BOM", "DXB"}): 1939,   # Mumbai ↔ Dubai
    frozenset({"DEL", "BOM"}): 1148,   # Delhi ↔ Mumbai (domestic)
    frozenset({"JFK", "CDG"}): 5837,   # New York ↔ Paris
    frozenset({"LAX", "JFK"}): 3983,   # LA ↔ New York (domestic US)
    frozenset({"SIN", "SYD"}): 6291,   # Singapore ↔ Sydney
    frozenset({"HKG", "LHR"}): 9630,   # Hong Kong ↔ London
    frozenset({"NRT", "LHR"}): 9554,   # Tokyo Narita ↔ London
}

_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d"]


def _parse_date(raw: str):
    from datetime import datetime
    raw = str(raw).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _lookup_distance(origin: str, destination: str) -> tuple[int | None, bool]:
    """
    Returns (distance_km, found).
    Pair is looked up bidirectionally (A→B == B→A).
    """
    key = frozenset({origin.strip().upper(), destination.strip().upper()})
    distance = IATA_DISTANCES.get(key)
    return distance, distance is not None


# ---------------------------------------------------------------------------
# Main ingestion function
# ---------------------------------------------------------------------------

def ingest_travel_csv(file_obj, batch: UploadBatch) -> tuple[int, int]:
    """
    Parse a corporate travel CSV and create EmissionRow records.

    Rows with unknown flight routes are flagged with status=NEEDS_DISTANCE
    rather than failing outright — analysts can fill in the distance manually.

    Args:
        file_obj: Django InMemoryUploadedFile or file-like object.
        batch:    The UploadBatch record already created by the view.

    Returns:
        (rows_created, errors_logged)
    """
    content = file_obj.read().decode("utf-8", errors="replace")

    try:
        df = pd.read_csv(
            StringIO(content),
            sep=",",
            dtype=str,
            keep_default_na=False,
        )
    except Exception as exc:
        IngestionError.objects.create(
            batch=batch,
            row_number=0,
            raw_line="",
            error_type="PARSE_ERROR",
            error_message=f"Could not parse CSV: {exc}",
        )
        return 0, 1

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    required = {"trip_id", "traveler_id", "travel_date", "origin",
                "destination", "transport_mode"}
    missing = required - set(df.columns)
    if missing:
        IngestionError.objects.create(
            batch=batch,
            row_number=0,
            raw_line=",".join(df.columns),
            error_type="MISSING_FIELD",
            error_message=f"Required columns missing: {missing}",
        )
        return 0, 1

    rows_created = 0
    errors_logged = 0

    for csv_row_idx, row in df.iterrows():
        csv_row_num = int(csv_row_idx) + 2
        raw_line = ",".join(row.values)

        try:
            # ── Date ──────────────────────────────────────────────────────
            activity_date = _parse_date(row.get("travel_date", ""))
            if activity_date is None:
                raise ValueError(f"Unparseable travel_date: '{row.get('travel_date')}'")

            # ── Mode ───────────────────────────────────────────────────────
            mode = str(row.get("transport_mode", "")).strip().upper()
            if mode not in {"FLIGHT", "TRAIN", "CAR", "HOTEL"}:
                raise ValueError(f"Unknown transport_mode: '{mode}'")

            origin      = str(row.get("origin", "")).strip().upper()
            destination = str(row.get("destination", "")).strip().upper()
            cabin_class = str(row.get("cabin_class", "")).strip().upper()

            # ── Cost in USD ────────────────────────────────────────────────
            cost_str = str(row.get("cost_usd", "0")).strip().replace(",", "")
            try:
                cost_usd = Decimal(cost_str) if cost_str else Decimal("0")
            except InvalidOperation:
                cost_usd = Decimal("0")

            # ── Calculation per mode ───────────────────────────────────────
            status        = RowStatus.PENDING
            flagged_reason = ""
            kgco2e        = Decimal("0")
            raw_value     = Decimal("0")
            raw_unit      = ""
            ef            = None

            if mode == "FLIGHT":
                # 1. Try distance from CSV
                dist_str = str(row.get("distance_km", "")).strip()
                if dist_str and dist_str.replace(".", "").isdigit():
                    distance_km = Decimal(dist_str)
                    found_in_lookup = False
                else:
                    # 2. Try IATA lookup
                    distance_km_int, found_in_lookup = _lookup_distance(origin, destination)
                    if distance_km_int is not None:
                        distance_km = Decimal(distance_km_int)
                    else:
                        # Unknown route — create row but flag it
                        distance_km = Decimal("0")
                        status = RowStatus.NEEDS_DISTANCE
                        flagged_reason = (
                            f"Unknown IATA route: {origin} → {destination}. "
                            "Distance required to calculate emissions."
                        )
                        errors_logged += 1
                        IngestionError.objects.create(
                            batch=batch,
                            row_number=csv_row_num,
                            raw_line=raw_line,
                            error_type="UNKNOWN_ROUTE",
                            error_message=flagged_reason,
                        )

                ef_key = cabin_class if cabin_class in FLIGHT_EF else ""
                ef = FLIGHT_EF[ef_key]
                kgco2e    = distance_km * ef
                raw_value = distance_km
                raw_unit  = "km"

            elif mode == "HOTEL":
                nights_str = str(row.get("nights", "")).strip()
                try:
                    nights = Decimal(nights_str) if nights_str else Decimal("1")
                except InvalidOperation:
                    nights = Decimal("1")
                ef        = MODE_EF["HOTEL"]
                kgco2e    = nights * ef
                raw_value = nights
                raw_unit  = "nights"

            else:  # TRAIN / CAR
                dist_str = str(row.get("distance_km", "")).strip()
                try:
                    distance_km = Decimal(dist_str) if dist_str else Decimal("0")
                except InvalidOperation:
                    distance_km = Decimal("0")
                if distance_km <= 0 and mode != "HOTEL":
                    raise ValueError(
                        f"distance_km is required for mode={mode} but is missing/zero"
                    )
                ef        = MODE_EF[mode]
                kgco2e    = distance_km * ef
                raw_value = distance_km
                raw_unit  = "km"

            extra = {
                "trip_id":       row.get("trip_id", ""),
                "traveler_id":   row.get("traveler_id", ""),
                "origin":        origin,
                "destination":   destination,
                "transport_mode": mode,
                "cabin_class":   cabin_class,
                "cost_usd":      str(cost_usd),
                "nights":        row.get("nights", ""),
            }

            EmissionRow.objects.create(
                client=batch.client,
                batch=batch,
                source_type=SourceType.CORPORATE_TRAVEL,
                scope=GHGScope.SCOPE_3,
                activity_date=activity_date,
                site_name=origin,
                location=f"{origin} → {destination}",
                activity_description=(
                    f"{mode.title()} — {origin} → {destination}"
                    + (f" ({cabin_class})" if cabin_class else "")
                ),
                raw_value=raw_value,
                raw_unit=raw_unit,
                kgco2e=kgco2e,
                emission_factor_used=ef,
                status=status,
                flagged_reason=flagged_reason,
                extra_data=extra,
            )
            rows_created += 1

        except Exception as exc:
            errors_logged += 1
            raw = str(exc).lower()
            error_type = (
                "BAD_DATE" if "date" in raw
                else "MISSING_FIELD" if "required" in raw
                else "PARSE_ERROR"
            )
            IngestionError.objects.create(
                batch=batch,
                row_number=csv_row_num,
                raw_line=raw_line,
                error_type=error_type,
                error_message=str(exc),
            )
            logger.warning("Travel ingest row %d error: %s", csv_row_num, exc)

    return rows_created, errors_logged
