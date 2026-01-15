"""
WebSocket Routing for Dashboard

Defines URL patterns for WebSocket connections.
"""
from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/market/", consumers.MarketDataConsumer.as_asgi()),
    path("ws/analysis/", consumers.AnalysisConsumer.as_asgi()),
]
