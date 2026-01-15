"""
Ingestion Module URL Configuration
"""
from django.urls import path

from . import views

app_name = "ingestion"

urlpatterns = [
    path("fetch/<str:ticker>/", views.fetch_single, name="fetch_single"),
    path("sector/<str:sector>/", views.analyze_sector_view, name="analyze_sector"),
    path("status/<str:task_id>/", views.task_status, name="task_status"),
    path("failures/", views.get_failures, name="failures"),
]
