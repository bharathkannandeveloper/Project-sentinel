"""
Dashboard Views

Async Django views for the Sentinel dashboard.
"""
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods


def index(request):
    """Render the main dashboard page."""
    return render(request, "dashboard/index.html", {
        "title": "Project Sentinel V2 - Financial Analyst Dashboard",
    })


def monitor(request):
    """Render the real-time market monitor page."""
    return render(request, "dashboard/monitor.html", {
        "title": "Real-Time Market Monitor",
    })


def chat_page(request):
    """Render the AI chatbot page."""
    return render(request, "dashboard/chat.html", {
        "title": "Sentinel AI - Financial Advisor Chat",
    })


@require_http_methods(["GET"])
async def api_status(request) -> JsonResponse:
    """API endpoint for system status."""
    return JsonResponse({
        "status": "operational",
        "version": "2.0.0",
        "modules": {
            "llm": "ready",
            "analysis": "ready",
            "ingestion": "ready",
            "knowledge": "ready",
            "chatbot": "ready",
        }
    })


@require_http_methods(["GET"])
async def api_providers(request) -> JsonResponse:
    """Get available LLM providers."""
    import os
    
    return JsonResponse({
        "providers": {
            "groq": {"available": bool(os.getenv("GROQ_API_KEY"))},
            "openai": {"available": bool(os.getenv("OPENAI_API_KEY"))},
            "anthropic": {"available": bool(os.getenv("ANTHROPIC_API_KEY"))},
        }
    })

