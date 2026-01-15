"""
Analysis Module Views

Async Django views for stock analysis endpoints.
"""
import json
from decimal import Decimal

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import PattaasuMetrics
from .pattaasu import PattaasuAnalyzer


# Initialize analyzer (without LLM for now)
analyzer = PattaasuAnalyzer()


@csrf_exempt
@require_http_methods(["POST"])
async def validate_pattaasu(request) -> JsonResponse:
    """
    Validate stock metrics against Pattaasu criteria.
    
    Request body should contain:
    - ticker: str
    - debt_to_equity: float
    - promoter_pledging_pct: float
    - free_cash_flow_year1: float
    - free_cash_flow_year2: float
    - free_cash_flow_year3: float
    """
    try:
        data = json.loads(request.body)
        
        # Convert to Decimal
        for key in ["debt_to_equity", "promoter_pledging_pct", 
                    "free_cash_flow_year1", "free_cash_flow_year2", "free_cash_flow_year3"]:
            if key in data:
                data[key] = Decimal(str(data[key]))
        
        is_valid, errors = analyzer.quick_validate(data)
        
        return JsonResponse({
            "ticker": data.get("ticker", "UNKNOWN"),
            "is_pattaasu_compliant": is_valid,
            "errors": errors,
        })
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_http_methods(["GET"])
async def analyze_stock(request, ticker: str) -> JsonResponse:
    """
    Perform full Pattaasu analysis on a stock.
    
    This is a placeholder - actual implementation would fetch
    data from the ingestion module and perform analysis.
    """
    # TODO: Integrate with data ingestion
    return JsonResponse({
        "ticker": ticker.upper(),
        "status": "pending",
        "message": "Analysis requires data ingestion. Use POST /api/ingestion/fetch/ first.",
    })


@require_http_methods(["GET"])
async def get_recommendation(request, ticker: str) -> JsonResponse:
    """
    Get investment recommendation for a stock.
    
    Requires prior analysis to be completed.
    """
    # TODO: Implement with cached analysis results
    return JsonResponse({
        "ticker": ticker.upper(),
        "status": "pending",
        "message": "Run analysis first via /api/analysis/analyze/",
    })


@require_http_methods(["GET"])
async def screen_stocks(request) -> JsonResponse:
    """
    Screen stocks based on Pattaasu criteria.
    
    Query parameters:
    - sector: Filter by sector
    - min_score: Minimum Pattaasu score
    - limit: Max results (default 50)
    """
    sector = request.GET.get("sector")
    min_score = request.GET.get("min_score", "60")
    limit = int(request.GET.get("limit", "50"))
    
    # TODO: Implement with database
    return JsonResponse({
        "filters": {
            "sector": sector,
            "min_score": min_score,
        },
        "limit": limit,
        "results": [],
        "message": "Stock screening requires database. Run data ingestion first.",
    })
