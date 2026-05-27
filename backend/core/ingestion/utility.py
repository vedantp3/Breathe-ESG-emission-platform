"""
Utility Electricity ingestion — Scope 2 emissions.

Handles portal CSV export format (comma-delimited):
  - Columns: meter_id, site_name, billing_period_start, billing_period_end,
             consumption_kwh, consumption_unit, tariff_code, supplier_name
  - Normalises MWh → kWh
  - Billing periods are stored exactly as-is (not forced to month boundaries)
  - Grid emission factor is read from the client's profile field

TODO: Per-region, per-year grid intensity lookup (DEFRA, IEA, EPA EGRID).
TODO: Market-based vs location-based accounting (RE certificates, PPAs).
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
# Unit normalisation
# ---------------------------------------------------------------------------

# All consumption normalises to kWh before applying emission factor
CONSUMPTION_UNIT_TO_KWH: dict[str, Decimal] = {
    "KWH": Decimal("1"),
    "MWH": Decimal("1000"),
    "GWH": Decimal("1000000"),
}

_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d"]


def _parse_date(raw: str):
    """Parse a billing period date from multiple possible formats."""
    raw = str(raw).strip()
    from datetime import datetime
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Main ingestion function
# ---------------------------------------------------------------------------

def ingest_utility_csv(file_obj, batch: UploadBatch) -> tuple[int, int]:
    """
    Parse a utility electricity CSV and create EmissionRow records.

    The grid emission factor is taken from batch.client.grid_emission_factor_kgco2e_per_kwh,
    making it configurable per client without code changes.

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

    required = {"meter_id", "site_name", "billing_period_start",
                "billing_period_end", "consumption_kwh", "consumption_unit"}
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

    grid_ef = batch.client.grid_emission_factor_kgco2e_per_kwh
    rows_created = 0
    errors_logged = 0

    for csv_row_idx, row in df.iterrows():
        csv_row_num = int(csv_row_idx) + 2
        raw_line = ",".join(row.values)

        try:
            # ── Dates ──────────────────────────────────────────────────────
            period_start = _parse_date(row.get("billing_period_start", ""))
            period_end   = _parse_date(row.get("billing_period_end", ""))

            if period_start is None:
                raise ValueError(
                    f"Unparseable billing_period_start: '{row.get('billing_period_start')}'"
                )
            if period_end is None:
                raise ValueError(
                    f"Unparseable billing_period_end: '{row.get('billing_period_end')}'"
                )

            if period_end < period_start:
                raise ValueError(
                    f"billing_period_end ({period_end}) is before "
                    f"billing_period_start ({period_start})"
                )

            # ── Consumption ────────────────────────────────────────────────
            raw_consumption_str = str(row.get("consumption_kwh", "")).strip().replace(",", "")
            try:
                raw_consumption = Decimal(raw_consumption_str)
            except InvalidOperation:
                raise ValueError(
                    f"Cannot parse consumption_kwh='{raw_consumption_str}'"
                )

            if raw_consumption < 0:
                raise ValueError(f"Negative consumption: {raw_consumption}")

            # ── Unit normalisation → kWh ───────────────────────────────────
            unit_raw = str(row.get("consumption_unit", "kWh")).strip().upper()
            multiplier = CONSUMPTION_UNIT_TO_KWH.get(unit_raw)
            if multiplier is None:
                raise ValueError(f"Unknown consumption unit: '{unit_raw}'")

            consumption_kwh = raw_consumption * multiplier

            # ── Emission calculation ───────────────────────────────────────
            kgco2e = consumption_kwh * grid_ef

            extra = {
                "meter_id":       row.get("meter_id", ""),
                "tariff_code":    row.get("tariff_code", ""),
                "supplier_name":  row.get("supplier_name", ""),
                "billing_period_start": str(period_start),
                "billing_period_end":   str(period_end),
            }

            EmissionRow.objects.create(
                client=batch.client,
                batch=batch,
                source_type=SourceType.UTILITY_ELECTRICITY,
                scope=GHGScope.SCOPE_2,
                activity_date=period_start,      # use period start as activity date
                site_name=row.get("site_name", ""),
                location=row.get("site_name", ""),
                activity_description=(
                    f"Electricity — {row.get('supplier_name', '')} — "
                    f"Meter {row.get('meter_id', '')} — "
                    f"{period_start} to {period_end}"
                ).strip(" —"),
                raw_value=raw_consumption,
                raw_unit=unit_raw,
                normalized_value_kwh=consumption_kwh,
                kgco2e=kgco2e,
                emission_factor_used=grid_ef,
                status=RowStatus.PENDING,
                extra_data=extra,
            )
            rows_created += 1

        except Exception as exc:
            errors_logged += 1
            raw = str(exc).lower()
            error_type = (
                "BAD_DATE" if "date" in raw or "period" in raw
                else "UNKNOWN_UNIT" if "unit" in raw
                else "PARSE_ERROR"
            )
            IngestionError.objects.create(
                batch=batch,
                row_number=csv_row_num,
                raw_line=raw_line,
                error_type=error_type,
                error_message=str(exc),
            )
            logger.warning("Utility ingest row %d error: %s", csv_row_num, exc)

    return rows_created, errors_logged
