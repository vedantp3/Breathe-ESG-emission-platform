"""
SAP Fuel & Procurement ingestion — Scope 1 emissions.

Handles the SAP MM flat-file CSV export format:
  - Semicolon-delimited
  - Columns: BUKRS, WERKS, BLDAT, MENGE, MEINS, MATNR, SGTXT
  - Date formats: YYYYMMDD or DD.MM.YYYY

Emission factors are hardcoded here.
TODO: Replace with a live emission factor API (e.g. Climatiq) in production.
TODO: Pull plant-to-site mapping from a DB table per client, not a hardcoded dict.
"""

import re
import logging
from decimal import Decimal, InvalidOperation
from io import StringIO

import pandas as pd
from django.utils import timezone

from core.models import (
    EmissionRow, IngestionError, UploadBatch,
    RowStatus, GHGScope, SourceType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static lookups — move to DB / config in production
# ---------------------------------------------------------------------------

WERKS_TO_SITE: dict[str, str] = {
    "1000": "Hamburg HQ",
    "1100": "Hamburg Warehouse",
    "2000": "Frankfurt Plant",
    "2100": "Frankfurt Lab",
    "3000": "Munich Distribution",
    "3100": "Munich Office",
    "4000": "Berlin Site",
    "5000": "Stuttgart Works",
}

# MATNR prefix → (material name, emission factor kgCO2e per base unit)
# Base units after unit normalisation: litres (L) for liquids, kg for solids, m³ for gas
# Sources: BEIS 2023 conversion factors
# TODO: Replace with DEFRA/BEIS API lookup keyed by fuel type + year.
MATERIAL_EMISSION_FACTORS: dict[str, tuple[str, Decimal]] = {
    "DIESEL":    ("Diesel",              Decimal("2.6391")),   # kgCO2e / litre
    "PETROL":    ("Petrol / Gasoline",   Decimal("2.3149")),   # kgCO2e / litre
    "NATGAS":    ("Natural Gas",         Decimal("2.0440")),   # kgCO2e / m³
    "LPG":       ("LPG",                 Decimal("1.5548")),   # kgCO2e / litre
    "HFO":       ("Heavy Fuel Oil",      Decimal("3.1791")),   # kgCO2e / litre
    "COAL":      ("Coal",                Decimal("2.3954")),   # kgCO2e / kg
    "BIOFUEL":   ("Biofuel",             Decimal("0.1715")),   # kgCO2e / litre
    "DEFAULT":   ("Unknown Fuel",        Decimal("2.6391")),   # fallback = diesel
}

# SAP MEINS → canonical unit (internal name used in normalisation)
UNIT_ALIASES: dict[str, str] = {
    "L":   "L",
    "LIT": "L",
    "LTR": "L",
    "KG":  "KG",
    "KGS": "KG",
    "G":   "G",
    "T":   "T",     # metric tonne
    "M3":  "M3",
    "CBM": "M3",
}

# Unit → multiplier to reach base unit (L, KG, or M3 as appropriate)
UNIT_MULTIPLIERS: dict[str, Decimal] = {
    "L":  Decimal("1"),
    "KG": Decimal("1"),
    "G":  Decimal("0.001"),      # grams → kg
    "T":  Decimal("1000"),       # tonnes → kg
    "M3": Decimal("1"),
}


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_DATE_FORMATS = ["%Y%m%d", "%d.%m.%Y", "%Y-%m-%d"]


def _parse_date(raw: str):
    """Try multiple SAP date formats.  Returns datetime.date or None."""
    raw = str(raw).strip()
    for fmt in _DATE_FORMATS:
        try:
            from datetime import datetime
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Material key extraction
# ---------------------------------------------------------------------------

def _classify_material(matnr: str) -> tuple[str, str, Decimal]:
    """
    Map a SAP material number to (key, description, kgCO2e_per_base_unit).
    Checks if the MATNR string starts with or contains any known key.
    """
    matnr_upper = str(matnr).upper().strip()
    for key, (desc, factor) in MATERIAL_EMISSION_FACTORS.items():
        if key in matnr_upper:
            return key, desc, factor
    return "DEFAULT", f"Unknown ({matnr})", MATERIAL_EMISSION_FACTORS["DEFAULT"][1]


# ---------------------------------------------------------------------------
# Main ingestion function
# ---------------------------------------------------------------------------

def ingest_sap_csv(file_obj, batch: UploadBatch) -> tuple[int, int]:
    """
    Parse a SAP fuel procurement CSV and create EmissionRow records.

    Args:
        file_obj: Django InMemoryUploadedFile (or any file-like object).
        batch:    The UploadBatch record already created by the view.

    Returns:
        (rows_created, errors_logged)
    """
    content = file_obj.read().decode("utf-8", errors="replace")

    try:
        df = pd.read_csv(
            StringIO(content),
            sep=";",
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

    # Normalise column names — strip whitespace, uppercase
    df.columns = [c.strip().upper() for c in df.columns]

    required = {"BUKRS", "WERKS", "BLDAT", "MENGE", "MEINS", "MATNR"}
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
        csv_row_num = int(csv_row_idx) + 2  # 1-indexed, +1 for header
        raw_line = ";".join(row.values)

        try:
            # ── Date ──────────────────────────────────────────────────────
            activity_date = _parse_date(row.get("BLDAT", ""))
            if activity_date is None:
                raise ValueError(f"Unparseable date: '{row.get('BLDAT', '')}'")

            # ── Plant / site ───────────────────────────────────────────────
            werks = row.get("WERKS", "").strip()
            site_name = WERKS_TO_SITE.get(werks, f"Plant {werks}")

            # ── Quantity ───────────────────────────────────────────────────
            menge_raw = str(row.get("MENGE", "")).strip().replace(",", ".")
            try:
                raw_value = Decimal(menge_raw)
            except InvalidOperation:
                raise ValueError(f"Cannot parse quantity MENGE='{menge_raw}'")

            if raw_value <= 0:
                raise ValueError(f"Non-positive quantity: {raw_value}")

            # ── Unit normalisation ─────────────────────────────────────────
            meins_raw = str(row.get("MEINS", "")).strip().upper()
            canonical_unit = UNIT_ALIASES.get(meins_raw)
            if canonical_unit is None:
                raise ValueError(f"Unknown unit of measure MEINS='{meins_raw}'")
            multiplier = UNIT_MULTIPLIERS[canonical_unit]
            normalized_qty = raw_value * multiplier

            # ── Emission factor ────────────────────────────────────────────
            matnr = str(row.get("MATNR", "")).strip()
            mat_key, mat_desc, ef = _classify_material(matnr)

            if mat_key == "DEFAULT" and matnr.upper() not in ("", "DEFAULT"):
                # Log a warning but still proceed with the default factor
                errors_logged += 1
                IngestionError.objects.create(
                    batch=batch,
                    row_number=csv_row_num,
                    raw_line=raw_line,
                    error_type="UNKNOWN_MATERIAL",
                    error_message=(
                        f"MATNR '{matnr}' not recognised — used diesel emission "
                        f"factor as fallback."
                    ),
                )

            kgco2e = normalized_qty * ef

            # ── Determine natural base unit label for storage ──────────────
            if canonical_unit in ("L",):
                stored_unit = "L"
            elif canonical_unit in ("KG", "G", "T"):
                stored_unit = "KG"
            elif canonical_unit == "M3":
                stored_unit = "M3"
            else:
                stored_unit = canonical_unit

            # ── Build extra_data from all remaining SAP columns ────────────
            extra = {
                "BUKRS": row.get("BUKRS", ""),
                "WERKS": werks,
                "MATNR": matnr,
                "SGTXT": row.get("SGTXT", ""),
                "material_key": mat_key,
            }

            EmissionRow.objects.create(
                client=batch.client,
                batch=batch,
                source_type=SourceType.SAP_FUEL_PROCUREMENT,
                scope=GHGScope.SCOPE_1,
                activity_date=activity_date,
                site_name=site_name,
                location=f"BUKRS {row.get('BUKRS', '')} / WERKS {werks}",
                activity_description=f"{mat_desc} — {row.get('SGTXT', '')}".strip(" —"),
                raw_value=raw_value,
                raw_unit=meins_raw,
                kgco2e=kgco2e,
                emission_factor_used=ef,
                status=RowStatus.PENDING,
                extra_data=extra,
            )
            rows_created += 1

        except Exception as exc:
            errors_logged += 1
            error_type = "BAD_DATE" if "date" in str(exc).lower() else (
                "UNKNOWN_UNIT" if "unit" in str(exc).lower() else "PARSE_ERROR"
            )
            IngestionError.objects.create(
                batch=batch,
                row_number=csv_row_num,
                raw_line=raw_line,
                error_type=error_type,
                error_message=str(exc),
            )
            logger.warning("SAP ingest row %d error: %s", csv_row_num, exc)

    return rows_created, errors_logged
