"""
Serializers for Breathe ESG REST API.

Design decisions:
- EmissionRowSerializer exposes all analyst-visible fields including edit history.
- UploadBatchSerializer includes nested error counts.
- IngestionErrorSerializer is read-only (errors are created by ingestion, not the API).
- We use SerializerMethodField for computed values (was_edited, scope_display).
"""

from rest_framework import serializers
from django.contrib.auth.models import User

from .models import (
    Client, UserProfile, UploadBatch, EmissionRow,
    IngestionError, RowStatus,
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email"]


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ["id", "name", "slug", "grid_emission_factor_kgco2e_per_kwh"]


class IngestionErrorSerializer(serializers.ModelSerializer):
    class Meta:
        model  = IngestionError
        fields = [
            "id", "batch", "row_number", "raw_line",
            "error_type", "error_message", "created_at",
        ]
        read_only_fields = fields


class UploadBatchSerializer(serializers.ModelSerializer):
    uploaded_by_username = serializers.CharField(
        source="uploaded_by.username", read_only=True
    )
    source_type_display = serializers.CharField(
        source="get_source_type_display", read_only=True
    )
    errors = IngestionErrorSerializer(many=True, read_only=True)

    class Meta:
        model  = UploadBatch
        fields = [
            "id", "client", "source_type", "source_type_display",
            "original_filename", "uploaded_by", "uploaded_by_username",
            "uploaded_at", "row_count", "error_count", "notes", "errors",
        ]
        read_only_fields = [
            "id", "uploaded_at", "row_count", "error_count", "errors",
        ]


class UploadBatchListSerializer(serializers.ModelSerializer):
    """Lightweight version without nested errors — used in list views."""
    uploaded_by_username = serializers.CharField(
        source="uploaded_by.username", read_only=True
    )
    source_type_display = serializers.CharField(
        source="get_source_type_display", read_only=True
    )

    class Meta:
        model  = UploadBatch
        fields = [
            "id", "source_type", "source_type_display",
            "original_filename", "uploaded_by_username",
            "uploaded_at", "row_count", "error_count",
        ]


class EmissionRowSerializer(serializers.ModelSerializer):
    was_edited          = serializers.BooleanField(read_only=True)
    scope_display       = serializers.CharField(source="get_scope_display", read_only=True)
    status_display      = serializers.CharField(source="get_status_display", read_only=True)
    source_type_display = serializers.CharField(source="get_source_type_display", read_only=True)
    approved_by_username = serializers.CharField(
        source="approved_by.username", read_only=True, default=None
    )
    edited_by_username = serializers.CharField(
        source="edited_by.username", read_only=True, default=None
    )
    batch_filename = serializers.CharField(
        source="batch.original_filename", read_only=True
    )

    class Meta:
        model  = EmissionRow
        fields = [
            "id", "client", "batch", "batch_filename",
            "source_type", "source_type_display",
            "scope", "scope_display",
            "activity_date", "site_name", "location", "activity_description",
            "raw_value", "raw_unit",
            "normalized_value_kwh",
            "kgco2e", "emission_factor_used",
            "status", "status_display", "flagged_reason",
            "approved_by", "approved_by_username", "approved_at",
            "locked_at",
            "analyst_notes",
            "original_raw_value", "original_raw_unit", "original_kgco2e",
            "edited_by", "edited_by_username", "edited_at",
            "was_edited",
            "extra_data",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "client", "batch", "batch_filename",
            "source_type", "source_type_display",
            "scope", "scope_display",
            "status_display", "source_type_display",
            "approved_by", "approved_by_username", "approved_at",
            "locked_at",
            "original_raw_value", "original_raw_unit", "original_kgco2e",
            "edited_by", "edited_by_username", "edited_at",
            "was_edited",
            "extra_data",
            "created_at", "updated_at",
        ]


class EmissionRowEditSerializer(serializers.ModelSerializer):
    """
    Used for PATCH /api/rows/{id}/ — allows analyst to correct raw_value / raw_unit / kgco2e.
    Edit tracking (original_* fields) is applied in the view, not here.
    """
    class Meta:
        model  = EmissionRow
        fields = ["raw_value", "raw_unit", "kgco2e", "analyst_notes"]


class FlagRowSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000, required=True)
    analyst_notes = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class ApproveRowSerializer(serializers.Serializer):
    analyst_notes = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class BulkLockSerializer(serializers.Serializer):
    row_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text="List of EmissionRow UUIDs to lock. All must be in APPROVED status.",
    )


class SummarySerializer(serializers.Serializer):
    """Read-only summary stats for the dashboard top bar."""
    scope_1_kgco2e  = serializers.DecimalField(max_digits=18, decimal_places=2)
    scope_2_kgco2e  = serializers.DecimalField(max_digits=18, decimal_places=2)
    scope_3_kgco2e  = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_kgco2e    = serializers.DecimalField(max_digits=18, decimal_places=2)
    pending_count   = serializers.IntegerField()
    flagged_count   = serializers.IntegerField()
    approved_count  = serializers.IntegerField()
    locked_count    = serializers.IntegerField()
    needs_dist_count = serializers.IntegerField()
