"""
Sentinel V2 API - India Only

Features:
- NSE/BSE stocks only (no US)
- Market status (open/close)
- Focused AI responses
- Perplexity-style data
"""
import asyncio
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from asgiref.sync import async_to_sync

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

import httpx
from src.llm.base import ProviderType
from src.llm.config import get_llm_config
from src.llm.manager import LLMManager

from src.ingestion.multi_source import search_stocks, fetch_stock, get_market_status, get_market_indices, get_top_gainers
from src.chatbot.anand_bot import get_chatbot, analyze_butterfly

IST = ZoneInfo("Asia/Kolkata")

# =============================================================================
# API VIEWS
# =============================================================================

@csrf_exempt
@require_http_methods(["POST"])
def api_monitor_quotes(request):
    """Fetch live data for multiple tickers (Monitor)."""
    try:
        data = json.loads(request.body)
        tickers = data.get("tickers", [])
        
        if not tickers:
            return JsonResponse({"success": True, "data": []})
        
        # Parallel fetch wrapper
        async def fetch_all(symbols):
            tasks = [fetch_stock(s) for s in symbols]
            return await asyncio.gather(*tasks)
            
        results = async_to_sync(fetch_all)(tickers)
        
        # Format for monitor
        response_data = []
        for r in results:
            if r.get("success"):
               response_data.append({
                   "symbol": r["symbol"],
                   "price": r["price"],
                   "change": r.get("change", 0),
                   "change_percent": r.get("change_percent", 0),
                   "volume": r.get("volume", 0),
                   "sector": r.get("sector", "")
               })
            else:
                response_data.append({
                    "symbol": r.get("symbol", "UNKNOWN"),
                    "price": 0,
                    "change": 0,
                    "change_percent": 0,
                    "error": True
                })
               
        return JsonResponse({"success": True, "data": response_data})
        
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@require_http_methods(["GET"])
def api_search(request):
    """Search for Indian stocks."""
    query = request.GET.get("q", "").strip()
    if not query:
        return JsonResponse({"results": []})
    
    # search_stocks is sync
    results = search_stocks(query, limit=10)
    return JsonResponse({"results": results})


@csrf_exempt
@require_http_methods(["POST"])
def api_analyze_stock(request):
    """Deep analysis of a stock."""
    try:
        data = json.loads(request.body)
        ticker = data.get("ticker", "").strip().upper()
        
        if not ticker:
            return JsonResponse({"success": False, "error": "Ticker is required"})
        
        # Use Chatbot for analysis (async_to_sync)
        bot = get_chatbot()
        result = async_to_sync(bot.analyze)(ticker)
        
        return JsonResponse(result)
        
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_chat(request):
    """Chat with Sentinel."""
    try:
        data = json.loads(request.body)
        message = data.get("message", "").strip()
        
        if not message:
            return JsonResponse({"success": False, "error": "Message is required"})
        
        bot = get_chatbot()
        result = async_to_sync(bot.chat)(message)
        
        return JsonResponse(result)

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_clear_memory(request):
    """Clear chat memory."""
    try:
        bot = get_chatbot()
        bot.clear_memory()
        return JsonResponse({"success": True, "message": "Memory cleared"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_http_methods(["GET"])
def api_market_status(request):
    """Get NSE market status."""
    status = get_market_status()
    return JsonResponse(status)


@csrf_exempt
@require_http_methods(["POST"])
def api_analyze_event(request):
    """Analyze geopolitical event."""
    try:
        data = json.loads(request.body)
        event = data.get("event", "").strip()
        
        if not event:
            return JsonResponse({"success": False, "error": "Event is required"})
            
        bot = get_chatbot()
        impacts = analyze_butterfly(event) # This returns impacts list
        return JsonResponse({"success": True, "impacts": impacts})
        
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_http_methods(["GET"])
def api_test_llm(request):
    """Test LLM connection using active provider."""
    try:
        manager = LLMManager()
        start = datetime.now()
        
        # Use manager to test connection
        resp = async_to_sync(manager.complete)(
            prompt="Hi", 
            max_tokens=5
        )
        
        latency = (datetime.now() - start).total_seconds() * 1000
        
        return JsonResponse({
            "success": True,
            "provider": resp.provider.value,
            "test_response": {
                "latency_ms": int(latency),
                "status": 200,
                "model": resp.model
            }
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@require_http_methods(["GET"])
def api_market_indices(request):
    """Get major market indices."""
    try:
        indices = async_to_sync(get_market_indices)()
        return JsonResponse({"success": True, "indices": indices})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@require_http_methods(["GET"])
def api_top_gainers(request):
    """Get top gainers."""
    try:
        gainers = async_to_sync(get_top_gainers)()
        return JsonResponse({"success": True, "gainers": gainers})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@require_http_methods(["GET"])
def api_get_llm_models(request):
    """Get available models for a provider."""
    provider_str = request.GET.get("provider", "groq").lower()
    try:
        try:
            provider_type = ProviderType(provider_str)
        except ValueError:
            return JsonResponse({"success": False, "error": "Invalid provider"})
            
        manager = LLMManager()
        models = async_to_sync(manager.get_models_for_provider)(provider_type)
        
        return JsonResponse({
            "success": True, 
            "models": [
                {"id": m.id, "name": m.name} for m in models
            ]
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@csrf_exempt
@require_http_methods(["POST"])
def api_save_llm_config(request):
    """Save LLM configuration (In-Memory)."""
    try:
        data = json.loads(request.body)
        provider_str = data.get("provider", "groq").lower()
        model_id = data.get("model")
        
        try:
            provider_type = ProviderType(provider_str)
        except ValueError:
            return JsonResponse({"success": False, "error": "Invalid provider"})
            
        config = get_llm_config()
        config.default_provider = provider_type
        
        if model_id:
            provider_config = config.get_provider_config(provider_type)
            provider_config.default_model = model_id
            if not provider_config.enabled and provider_type == ProviderType.OLLAMA:
                 provider_config.enabled = True
            
        bot = get_chatbot()
        if hasattr(bot, "reload_config"):
            bot.reload_config()
        
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})
