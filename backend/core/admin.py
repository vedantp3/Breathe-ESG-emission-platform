"""
core/admin.py — Register models in Django admin for superuser debugging.
Note: Analysts use the React dashboard, not the admin UI.
"""

from django.contrib import admin
from .models import Client, UserProfile, UploadBatch, EmissionRow, IngestionError


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "grid_emission_factor_kgco2e_per_kwh", "created_at"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "client", "role"]
    list_filter  = ["client", "role"]


@admin.register(UploadBatch)
class UploadBatchAdmin(admin.ModelAdmin):
    list_display  = ["original_filename", "source_type", "client", "uploaded_by", "uploaded_at", "row_count", "error_count"]
    list_filter   = ["source_type", "client"]
    readonly_fields = ["uploaded_at"]


@admin.register(EmissionRow)
class EmissionRowAdmin(admin.ModelAdmin):
    list_display  = ["source_type", "scope", "activity_date", "site_name", "kgco2e", "status", "client"]
    list_filter   = ["source_type", "scope", "status", "client"]
    readonly_fields = ["created_at", "updated_at"]
    search_fields = ["site_name", "activity_description", "location"]


@admin.register(IngestionError)
class IngestionErrorAdmin(admin.ModelAdmin):
    list_display = ["batch", "row_number", "error_type", "created_at"]
    list_filter  = ["error_type"]
    readonly_fields = ["created_at"]
