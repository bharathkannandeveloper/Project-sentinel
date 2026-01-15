"""
Dashboard URL Configuration - India Only
"""
from django.urls import path

from . import views
from . import api

app_name = "dashboard"

urlpatterns = [
    # Pages
    path("", views.index, name="index"),
    path("monitor/", views.monitor, name="monitor"),
    path("chat/", views.chat_page, name="chat"),
    
    # Status APIs
    path("api/status/", views.api_status, name="api_status"),
    path("api/providers/", views.api_providers, name="api_providers"),
    path("api/market-status/", api.api_market_status, name="market_status"),
    
    # V2 APIs (India Only)
    path("api/v2/test-llm/", api.api_test_llm, name="test_llm"),
    path("api/v2/search/", api.api_search, name="search_stocks"),
    path("api/v2/chat/", api.api_chat, name="chat_api"),
    path("api/v2/analyze/", api.api_analyze_stock, name="analyze_stock"),
    path("api/v2/clear-memory/", api.api_clear_memory, name="clear_memory"),
    path("api/v2/analyze-event/", api.api_analyze_event, name="analyze_event"),
    
    # Market Data
    path("api/indices/", api.api_market_indices, name="market_indices"),
    path("api/top-gainers/", api.api_top_gainers, name="top_gainers"),
    path("api/monitor/quotes/", api.api_monitor_quotes, name="monitor_quotes"),
    
    # Configuration
    path("api/config/llm/models/", api.api_get_llm_models, name="get_llm_models"),
    path("api/config/llm/save/", api.api_save_llm_config, name="save_llm_config"),
]
