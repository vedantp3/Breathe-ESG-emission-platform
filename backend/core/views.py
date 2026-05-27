"""
Views for Breathe ESG REST API.

All views enforce client scoping — analysts only see and modify data
belonging to the client attached to their UserProfile.

View groups:
  1. Ingestion views (SAP, Utility, Travel)
  2. EmissionRow CRUD + lifecycle actions (approve, flag, lock)
  3. UploadBatch list (upload history)
  4. Summary stats endpoint
"""

import logging
from decimal import Decimal
from io import BytesIO
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Count, Q

from rest_framework import generics, status, views
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated

from .models import (
    UploadBatch, EmissionRow, IngestionError,
    RowStatus, SourceType, GHGScope,
)
from .serializers import (
    UploadBatchSerializer, UploadBatchListSerializer,
    EmissionRowSerializer, EmissionRowEditSerializer,
    FlagRowSerializer, ApproveRowSerializer, BulkLockSerializer,
    SummarySerializer, IngestionErrorSerializer,
)
from .ingestion.sap     import ingest_sap_csv
from .ingestion.utility import ingest_utility_csv
from .ingestion.travel  import ingest_travel_csv

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_client(request):
    """Return the Client for the authenticated user. Raises AttributeError if no profile."""
    return request.user.profile.client


def _client_rows(request):
    """Return a scoped EmissionRow queryset for the authenticated user's client."""
    return EmissionRow.objects.filter(client=_get_client(request))


# ---------------------------------------------------------------------------
# Ingestion views
# ---------------------------------------------------------------------------

class BaseIngestView(views.APIView):
    """
    Common upload logic for all three source types.
    Subclasses set source_type and ingest_fn.
    """
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    source_type: str = ""
    ingest_fn = None  # callable(file_obj, batch) → (rows_created, errors_logged)

    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response(
                {"error": "No file provided. Send a CSV as multipart/form-data with key 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = _get_client(request)

        # ── Snapshot file bytes BEFORE Django saves the FileField ────────────
        # Django's FileField.save() reads the entire InMemoryUploadedFile,
        # leaving the pointer at EOF. If we let it run first, the parser gets
        # an empty stream and raises "No columns to parse from file".
        raw_bytes = file_obj.read()
        file_obj.seek(0)           # reset so Django can read it for storage

        with transaction.atomic():
            batch = UploadBatch.objects.create(
                client=client,
                source_type=self.source_type,
                original_filename=file_obj.name,
                file=file_obj,         # Django reads & saves the file here
                uploaded_by=request.user,
            )

            # Give the parser a fresh, fully-rewound buffer
            parse_buf = BytesIO(raw_bytes)
            parse_buf.name = file_obj.name   # some parsers check .name

            rows_created, errors_logged = self.ingest_fn(parse_buf, batch)

            batch.row_count   = rows_created
            batch.error_count = errors_logged
            batch.save(update_fields=["row_count", "error_count"])

        errors = IngestionErrorSerializer(
            batch.errors.all(), many=True
        ).data

        return Response(
            {
                "batch_id":      str(batch.id),
                "filename":      batch.original_filename,
                "source_type":   batch.source_type,
                "rows_created":  rows_created,
                "errors_logged": errors_logged,
                "errors":        errors,
            },
            status=status.HTTP_201_CREATED,
        )


class SAPIngestView(BaseIngestView):
    source_type = SourceType.SAP_FUEL_PROCUREMENT
    ingest_fn   = staticmethod(ingest_sap_csv)


class UtilityIngestView(BaseIngestView):
    source_type = SourceType.UTILITY_ELECTRICITY
    ingest_fn   = staticmethod(ingest_utility_csv)


class TravelIngestView(BaseIngestView):
    source_type = SourceType.CORPORATE_TRAVEL
    ingest_fn   = staticmethod(ingest_travel_csv)


# ---------------------------------------------------------------------------
# EmissionRow — list + filter
# ---------------------------------------------------------------------------

class EmissionRowListView(generics.ListAPIView):
    """
    GET /api/rows/

    Query params (all optional):
      source      — SAP_FUEL_PROCUREMENT | UTILITY_ELECTRICITY | CORPORATE_TRAVEL
      status      — PENDING | FLAGGED | APPROVED | LOCKED | NEEDS_DISTANCE
      scope       — 1 | 2 | 3
      date_from   — YYYY-MM-DD
      date_to     — YYYY-MM-DD
      search      — text search on site_name, activity_description, location
      ordering    — any field, prefix with - for descending
    """
    serializer_class   = EmissionRowSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = _client_rows(self.request).select_related(
            "batch", "approved_by", "edited_by"
        )

        p = self.request.query_params

        source    = p.get("source")
        row_status = p.get("status")
        scope     = p.get("scope")
        date_from = p.get("date_from")
        date_to   = p.get("date_to")
        search    = p.get("search")

        if source:
            qs = qs.filter(source_type=source)
        if row_status:
            qs = qs.filter(status=row_status)
        if scope:
            try:
                qs = qs.filter(scope=int(scope))
            except ValueError:
                pass
        if date_from:
            qs = qs.filter(activity_date__gte=date_from)
        if date_to:
            qs = qs.filter(activity_date__lte=date_to)
        if search:
            qs = qs.filter(
                Q(site_name__icontains=search)
                | Q(activity_description__icontains=search)
                | Q(location__icontains=search)
            )

        ordering = p.get("ordering", "-activity_date")
        allowed_orderings = {
            "activity_date", "-activity_date",
            "kgco2e", "-kgco2e",
            "status", "-status",
            "scope", "-scope",
            "created_at", "-created_at",
        }
        if ordering in allowed_orderings:
            qs = qs.order_by(ordering)

        return qs


# ---------------------------------------------------------------------------
# EmissionRow — retrieve + edit (PATCH)
# ---------------------------------------------------------------------------

class EmissionRowDetailView(generics.RetrieveUpdateAPIView):
    """
    GET  /api/rows/{id}/  — retrieve a single row
    PATCH /api/rows/{id}/ — analyst edits raw_value / raw_unit / kgco2e / analyst_notes

    Edit tracking: before applying changes, original values are saved
    to original_raw_value / original_raw_unit / original_kgco2e.
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _client_rows(self.request)

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return EmissionRowEditSerializer
        return EmissionRowSerializer

    def partial_update(self, request, *args, **kwargs):
        row = self.get_object()

        if row.status == RowStatus.LOCKED:
            return Response(
                {"error": "Cannot edit a LOCKED row."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Store originals before overwriting
        if row.original_raw_value is None:  # first edit only
            row.original_raw_value = row.raw_value
            row.original_raw_unit  = row.raw_unit
            row.original_kgco2e    = row.kgco2e

        serializer = self.get_serializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            edited_by=request.user,
            edited_at=timezone.now(),
        )

        return Response(EmissionRowSerializer(row).data)


# ---------------------------------------------------------------------------
# Row lifecycle action views
# ---------------------------------------------------------------------------

class ApproveRowView(views.APIView):
    """PATCH /api/rows/{id}/approve/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, *args, **kwargs):
        try:
            row = _client_rows(request).get(pk=pk)
        except EmissionRow.DoesNotExist:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if row.status == RowStatus.LOCKED:
            return Response(
                {"error": "Row is already LOCKED and cannot be modified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ApproveRowSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        row.status      = RowStatus.APPROVED
        row.approved_by = request.user
        row.approved_at = timezone.now()
        if serializer.validated_data.get("analyst_notes"):
            row.analyst_notes = serializer.validated_data["analyst_notes"]
        row.flagged_reason = ""  # clear any previous flag
        row.save()

        return Response(EmissionRowSerializer(row).data)


class FlagRowView(views.APIView):
    """PATCH /api/rows/{id}/flag/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, *args, **kwargs):
        try:
            row = _client_rows(request).get(pk=pk)
        except EmissionRow.DoesNotExist:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if row.status == RowStatus.LOCKED:
            return Response(
                {"error": "Row is LOCKED and cannot be flagged."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = FlagRowSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        row.status         = RowStatus.FLAGGED
        row.flagged_reason = serializer.validated_data["reason"]
        if serializer.validated_data.get("analyst_notes"):
            row.analyst_notes = serializer.validated_data["analyst_notes"]
        row.approved_by = None
        row.approved_at = None
        row.save()

        return Response(EmissionRowSerializer(row).data)


class LockRowsView(views.APIView):
    """
    POST /api/rows/lock/

    Bulk-locks a list of APPROVED rows. Only approved rows can be locked.
    Locked rows cannot be edited, approved, or flagged.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = BulkLockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        row_ids   = serializer.validated_data["row_ids"]
        client    = _get_client(request)
        now       = timezone.now()

        rows = EmissionRow.objects.filter(
            client=client,
            id__in=row_ids,
            status=RowStatus.APPROVED,
        )

        locked_count = rows.update(status=RowStatus.LOCKED, locked_at=now)
        skipped      = len(row_ids) - locked_count

        return Response({
            "locked":  locked_count,
            "skipped": skipped,
            "message": (
                f"{locked_count} row(s) locked. "
                f"{skipped} row(s) skipped (not found or not in APPROVED status)."
            ),
        })


# ---------------------------------------------------------------------------
# Upload history
# ---------------------------------------------------------------------------

class UploadBatchListView(generics.ListAPIView):
    """
    GET /api/uploads/
    Lists all upload batches for the authenticated user's client.
    """
    serializer_class   = UploadBatchListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        client = _get_client(self.request)
        return UploadBatch.objects.filter(client=client).order_by("-uploaded_at")


class UploadBatchDetailView(generics.RetrieveAPIView):
    """
    GET /api/uploads/{id}/
    Full detail including nested ingestion errors.
    """
    serializer_class   = UploadBatchSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        client = _get_client(self.request)
        return UploadBatch.objects.filter(client=client).prefetch_related("errors")


# ---------------------------------------------------------------------------
# Summary stats
# ---------------------------------------------------------------------------

class SummaryStatsView(views.APIView):
    """
    GET /api/summary/
    Returns aggregated kgCO2e by scope and row counts by status.
    Used to populate the dashboard summary bar.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        qs = _client_rows(request)

        # kgCO2e by scope (only non-locked-out statuses in active reporting)
        scope_agg = (
            qs.values("scope")
            .annotate(total=Sum("kgco2e"))
        )
        scope_map = {row["scope"]: row["total"] or Decimal("0") for row in scope_agg}

        total_kgco2e = qs.aggregate(t=Sum("kgco2e"))["t"] or Decimal("0")

        status_agg = (
            qs.values("status")
            .annotate(cnt=Count("id"))
        )
        status_map = {row["status"]: row["cnt"] for row in status_agg}

        data = {
            "scope_1_kgco2e":  scope_map.get(GHGScope.SCOPE_1, Decimal("0")),
            "scope_2_kgco2e":  scope_map.get(GHGScope.SCOPE_2, Decimal("0")),
            "scope_3_kgco2e":  scope_map.get(GHGScope.SCOPE_3, Decimal("0")),
            "total_kgco2e":    total_kgco2e,
            "pending_count":   status_map.get(RowStatus.PENDING, 0),
            "flagged_count":   status_map.get(RowStatus.FLAGGED, 0),
            "approved_count":  status_map.get(RowStatus.APPROVED, 0),
            "locked_count":    status_map.get(RowStatus.LOCKED, 0),
            "needs_dist_count": status_map.get(RowStatus.NEEDS_DISTANCE, 0),
        }

        serializer = SummarySerializer(data)
        return Response(serializer.data)
