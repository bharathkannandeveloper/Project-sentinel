"""
Knowledge Module URL Configuration
"""
from django.urls import path

from . import views

app_name = "knowledge"

urlpatterns = [
    path("status/", views.graph_status, name="status"),
]
