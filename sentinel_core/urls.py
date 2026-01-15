"""
URL Configuration for Project Sentinel

This module defines the root URL patterns, delegating to app-specific
URL configurations.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Admin interface
    path("admin/", admin.site.urls),
    
    # Allauth Accounts
    path("accounts/", include("allauth.urls")),
    
    # Dashboard - main application interface
    path("", include("src.dashboard.urls")),
    
    # API endpoints for different modules
    path("api/analysis/", include("src.analysis.urls")),
    path("api/ingestion/", include("src.ingestion.urls")),
    path("api/knowledge/", include("src.knowledge.urls")),
]
