"""
Analysis Module URL Configuration
"""
from django.urls import path

from . import views

app_name = "analysis"

urlpatterns = [
    path("validate/", views.validate_pattaasu, name="validate"),
    path("analyze/<str:ticker>/", views.analyze_stock, name="analyze"),
    path("recommend/<str:ticker>/", views.get_recommendation, name="recommend"),
    path("screen/", views.screen_stocks, name="screen"),
]
