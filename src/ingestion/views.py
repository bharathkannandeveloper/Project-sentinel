"""
Ingestion Module Views

Async Django views for data ingestion endpoints.
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .handlers import get_failure_handler


@csrf_exempt
@require_http_methods(["POST", "GET"])
async def fetch_single(request, ticker: str) -> JsonResponse:
    """
    Trigger data fetch for a single ticker.
    
    Returns task ID for status polling.
    """
    ticker = ticker.upper()
    
    try:
        # Import here to avoid circular imports
        from .tasks import fetch_company_metrics
        
        # Submit async task
        result = fetch_company_metrics.delay(ticker)
        
        return JsonResponse({
            "ticker": ticker,
            "task_id": result.id,
            "status": "submitted",
        })
    except Exception as e:
        return JsonResponse({
            "ticker": ticker,
            "error": str(e),
            "status": "failed",
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
async def analyze_sector_view(request, sector: str) -> JsonResponse:
    """
    Trigger sector analysis workflow.
    
    Request body should contain:
    - tickers: List of ticker symbols
    """
    import json
    from .tasks import analyze_sector
    
    try:
        data = json.loads(request.body)
        tickers = data.get("tickers", [])
        
        if not tickers:
            return JsonResponse({"error": "No tickers provided"}, status=400)
        
        # Submit sector analysis
        result = analyze_sector.delay(sector, tickers)
        
        return JsonResponse({
            "sector": sector,
            "task_id": result.id,
            "companies": len(tickers),
            "status": "submitted",
        })
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)


@require_http_methods(["GET"])
async def task_status(request, task_id: str) -> JsonResponse:
    """
    Get status of an async task.
    """
    from celery.result import AsyncResult
    
    result = AsyncResult(task_id)
    
    response = {
        "task_id": task_id,
        "status": result.status,
        "ready": result.ready(),
    }
    
    if result.ready():
        if result.successful():
            response["result"] = result.result
        else:
            response["error"] = str(result.result)
    
    return JsonResponse(response)


@require_http_methods(["GET"])
async def get_failures(request) -> JsonResponse:
    """
    Get recent ingestion failures.
    
    Query parameters:
    - ticker: Filter by ticker
    - limit: Max results (default 100)
    """
    ticker = request.GET.get("ticker")
    limit = int(request.GET.get("limit", "100"))
    
    handler = get_failure_handler()
    
    return JsonResponse({
        "stats": handler.get_failure_stats(),
        "failures": handler.get_recent_failures(limit=limit, ticker=ticker),
    })
