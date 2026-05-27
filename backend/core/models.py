"""
==============================================================================
 BREATHE ESG — ENTITY RELATIONSHIP DIAGRAM
==============================================================================

 ┌─────────────────────────────────────────────────────────────────────────┐
 │                           ENTITY RELATIONSHIP DIAGRAM                    │
 └─────────────────────────────────────────────────────────────────────────┘

  [auth.User]
       │ 1
       │ has one
       │ ↓ n
  [UserProfile]──────────────────────────────────────────────────────────────┐
    id (PK)                                                                   │
    user (1-1 → auth.User)                                                    │
    client (FK → Client)   ← multi-tenancy pivot                              │
    role (ANALYST/ADMIN)                                                       │
       │ belongs to                                                            │
       │ n                                                                     │
       │ ↓ 1                                                                   │
  [Client]                                                                     │
    id (PK)                                                                    │
    name                                                                       │
    slug                                                                       │
    grid_emission_factor_kgco2e_per_kwh  ← TODO: per-region lookup in prod    │
    created_at                                                                 │
       │ 1                                                                     │
       │ owns                                                                  │
       ├──────────────────────────────────┐                                    │
       │ n ↓                              │ n ↓                                │
  [UploadBatch]                     [EmissionRow]                              │
    id (PK, UUID)                     id (PK, UUID)                           │
    client (FK → Client)              client (FK → Client)  ← denormalized    │
    source_type (enum)                batch (FK → UploadBatch)                │
    original_filename                 source_type (enum)                       │
    file (FileField)                  scope (1/2/3)                           │
    uploaded_by (FK → User)           activity_date                           │
    uploaded_at                       site_name                               │
    row_count                         location                                │
    error_count                       activity_description                    │
    notes                             raw_value (Decimal)                     │
                                      raw_unit                                │
                                      normalized_value_kwh (nullable)         │
                                      kgco2e (Decimal)                        │
                                      emission_factor_used                    │
                                      status (enum)                           │
                                      flagged_reason                          │
                                      approved_by (FK → User, nullable)       │
                                      approved_at (nullable)                  │
                                      locked_at (nullable)                    │
                                      analyst_notes                           │
                                      original_raw_value (nullable) ← edit    │
                                      original_raw_unit (nullable)  ← edit    │
                                      original_kgco2e (nullable)    ← edit    │
                                      edited_by (FK → User, nullable)         │
                                      edited_at (nullable)                    │
                                      extra_data (JSONField)  ← source cols   │
                                      created_at                              │
                                      updated_at                              │
                                           │ 1                                │
                                           │                                  │
  [IngestionError]                         │                                  │
    id (PK)                                │                                  │
    batch (FK → UploadBatch)              ─┘                                  │
    row_number (int)                                                           │
    raw_line (text)                                                            │
    error_type (enum)                                                          │
    error_message (text)                                                       │
    created_at                                                                 │
                                                                               │
  LEGEND:                                                                      │
   FK  = ForeignKey                                                            │
   1-1 = OneToOneField                                                         │
   n   = many side of relationship                                             │
   1   = one side of relationship                                              │
==============================================================================
"""

import uuid
from django.db import models
from django.contrib.auth.models import User


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class SourceType(models.TextChoices):
    SAP_FUEL_PROCUREMENT = "SAP_FUEL_PROCUREMENT", "SAP Fuel & Procurement"
    UTILITY_ELECTRICITY  = "UTILITY_ELECTRICITY",  "Utility Electricity"
    CORPORATE_TRAVEL     = "CORPORATE_TRAVEL",      "Corporate Travel"


class GHGScope(models.IntegerChoices):
    SCOPE_1 = 1, "Scope 1 — Direct"
    SCOPE_2 = 2, "Scope 2 — Indirect (Energy)"
    SCOPE_3 = 3, "Scope 3 — Value Chain"


class RowStatus(models.TextChoices):
    PENDING         = "PENDING",         "Pending"
    NEEDS_DISTANCE  = "NEEDS_DISTANCE",  "Needs Distance"  # travel rows with unknown pairs
    FLAGGED         = "FLAGGED",         "Flagged"
    APPROVED        = "APPROVED",        "Approved"
    LOCKED          = "LOCKED",          "Locked (Audit)"


class ErrorType(models.TextChoices):
    PARSE_ERROR      = "PARSE_ERROR",      "Parse Error"
    MISSING_FIELD    = "MISSING_FIELD",    "Missing Required Field"
    UNKNOWN_UNIT     = "UNKNOWN_UNIT",     "Unknown Unit of Measure"
    UNKNOWN_MATERIAL = "UNKNOWN_MATERIAL", "Unknown Material / Emission Factor"
    BAD_DATE         = "BAD_DATE",         "Unparseable Date"
    UNKNOWN_ROUTE    = "UNKNOWN_ROUTE",    "Unknown IATA Route"
    VALIDATION       = "VALIDATION",       "Validation Error"


class UserRole(models.TextChoices):
    ANALYST = "ANALYST", "Analyst"
    ADMIN   = "ADMIN",   "Admin"


# ---------------------------------------------------------------------------
# Client — top-level tenant
# ---------------------------------------------------------------------------

class Client(models.Model):
    """
    A company / organisation that owns emission records.
    All data is scoped to a Client; analysts only see their own Client's data.
    """
    name  = models.CharField(max_length=255)
    slug  = models.SlugField(unique=True)

    # TODO: In production, replace this with a lookup per grid region / year
    #       (e.g. DEFRA, EPA, IEA grid intensity tables).
    grid_emission_factor_kgco2e_per_kwh = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0.233,  # UK average 2023 (DEFRA)
        help_text="kgCO2e per kWh consumed from the electricity grid",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# UserProfile — links auth.User → Client, adds role
# ---------------------------------------------------------------------------

class UserProfile(models.Model):
    """
    Extends auth.User with multi-tenancy (client) and role information.
    Created automatically via a post_save signal in apps.py.
    """
    user   = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="users")
    role   = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.ANALYST)

    def __str__(self):
        return f"{self.user.username} @ {self.client.name}"


# ---------------------------------------------------------------------------
# UploadBatch — one file upload event
# ---------------------------------------------------------------------------

class UploadBatch(models.Model):
    """
    Tracks a single CSV upload action.  Every EmissionRow is linked to the batch
    that created it, giving a complete chain of custody for each data point.
    """
    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client            = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="batches")
    source_type       = models.CharField(max_length=40, choices=SourceType.choices)
    original_filename = models.CharField(max_length=512)
    file              = models.FileField(upload_to="uploads/%Y/%m/", null=True, blank=True)
    uploaded_by       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="uploads")
    uploaded_at       = models.DateTimeField(auto_now_add=True)
    row_count         = models.IntegerField(default=0)
    error_count       = models.IntegerField(default=0)
    notes             = models.TextField(blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.source_type} — {self.original_filename} ({self.uploaded_at:%Y-%m-%d})"


# ---------------------------------------------------------------------------
# EmissionRow — the normalised, auditable record of a single emission event
# ---------------------------------------------------------------------------

class EmissionRow(models.Model):
    """
    One normalised emission data point.  Maps to a single row in a source CSV.

    Lifecycle:  PENDING → FLAGGED / NEEDS_DISTANCE → APPROVED → LOCKED

    Edit tracking: when an analyst edits raw_value or kgco2e, the original values
    are copied to original_raw_value / original_kgco2e before the edit is applied.
    This gives a single-level undo / audit trail without a full event-sourcing setup.
    TODO: For a production system, implement a full audit log table (or django-simple-history).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Tenancy & provenance ──────────────────────────────────────────────
    client      = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="rows")
    batch       = models.ForeignKey(UploadBatch, on_delete=models.PROTECT, related_name="rows")
    source_type = models.CharField(max_length=40, choices=SourceType.choices)
    scope       = models.IntegerField(choices=GHGScope.choices)

    # ── Activity fields ───────────────────────────────────────────────────
    activity_date        = models.DateField(null=True, blank=True)
    site_name            = models.CharField(max_length=255, blank=True)
    location             = models.CharField(max_length=255, blank=True)
    activity_description = models.CharField(max_length=512, blank=True)

    # ── Raw source values (stored as-is from CSV) ─────────────────────────
    raw_value = models.DecimalField(max_digits=18, decimal_places=4)
    raw_unit  = models.CharField(max_length=50)

    # ── Normalised values ─────────────────────────────────────────────────
    # normalized_value_kwh only applies to electricity rows
    normalized_value_kwh = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    kgco2e               = models.DecimalField(max_digits=18, decimal_places=4)
    emission_factor_used = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)

    # ── Status lifecycle ──────────────────────────────────────────────────
    status         = models.CharField(max_length=20, choices=RowStatus.choices, default=RowStatus.PENDING)
    flagged_reason = models.TextField(blank=True)

    # ── Audit trail ───────────────────────────────────────────────────────
    approved_by   = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_rows"
    )
    approved_at   = models.DateTimeField(null=True, blank=True)
    locked_at     = models.DateTimeField(null=True, blank=True)
    analyst_notes = models.TextField(blank=True)

    # ── Edit tracking ─────────────────────────────────────────────────────
    original_raw_value = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    original_raw_unit  = models.CharField(max_length=50, blank=True)
    original_kgco2e    = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    edited_by          = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="edited_rows"
    )
    edited_at = models.DateTimeField(null=True, blank=True)

    # ── Source-specific extra columns (raw SAP/travel fields, etc.) ───────
    extra_data = models.JSONField(default=dict, blank=True)

    # ── Timestamps ────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-activity_date", "site_name"]
        indexes = [
            models.Index(fields=["client", "status"]),
            models.Index(fields=["client", "source_type"]),
            models.Index(fields=["client", "scope"]),
            models.Index(fields=["batch"]),
            models.Index(fields=["activity_date"]),
        ]

    def __str__(self):
        return f"{self.source_type} | {self.activity_date} | {self.kgco2e} kgCO2e | {self.status}"

    @property
    def was_edited(self) -> bool:
        return self.original_raw_value is not None


# ---------------------------------------------------------------------------
# IngestionError — per-row parse / validation errors during CSV import
# ---------------------------------------------------------------------------

class IngestionError(models.Model):
    """
    Records a non-fatal error encountered while parsing a specific row in a CSV.
    The import continues; this row is skipped and logged here.
    Analysts can review ingestion errors in the upload history view.
    """
    batch       = models.ForeignKey(UploadBatch, on_delete=models.CASCADE, related_name="errors")
    row_number  = models.IntegerField(help_text="1-indexed CSV row number")
    raw_line    = models.TextField(blank=True, help_text="The raw CSV line content")
    error_type  = models.CharField(max_length=30, choices=ErrorType.choices)
    error_message = models.TextField()
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["batch", "row_number"]

    def __str__(self):
        return f"Batch {self.batch_id} row {self.row_number}: {self.error_type}"
