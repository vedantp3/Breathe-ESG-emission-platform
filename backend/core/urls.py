"""
URL patterns for the core app.
All routes are mounted under /api/ in breathe/urls.py.
"""

from django.urls import path
from . import views

urlpatterns = [
    # ── Ingestion ──────────────────────────────────────────────────────────
    path("ingest/sap/",     views.SAPIngestView.as_view(),     name="ingest-sap"),
    path("ingest/utility/", views.UtilityIngestView.as_view(), name="ingest-utility"),
    path("ingest/travel/",  views.TravelIngestView.as_view(),  name="ingest-travel"),

    # ── Emission rows ──────────────────────────────────────────────────────
    path("rows/",                views.EmissionRowListView.as_view(),   name="row-list"),
    path("rows/<uuid:pk>/",      views.EmissionRowDetailView.as_view(), name="row-detail"),
    path("rows/<uuid:pk>/approve/", views.ApproveRowView.as_view(),    name="row-approve"),
    path("rows/<uuid:pk>/flag/",    views.FlagRowView.as_view(),       name="row-flag"),
    path("rows/lock/",           views.LockRowsView.as_view(),          name="rows-lock"),

    # ── Upload history ─────────────────────────────────────────────────────
    path("uploads/",          views.UploadBatchListView.as_view(),   name="upload-list"),
    path("uploads/<uuid:pk>/", views.UploadBatchDetailView.as_view(), name="upload-detail"),

    # ── Dashboard summary ──────────────────────────────────────────────────
    path("summary/", views.SummaryStatsView.as_view(), name="summary-stats"),
]
