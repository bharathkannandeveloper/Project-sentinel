"""
Knowledge Module Views
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET"])
async def graph_status(request) -> JsonResponse:
    """Get Neo4j graph database status."""
    # TODO: Implement actual Neo4j connection check
    return JsonResponse({
        "status": "pending",
        "message": "Neo4j connection not yet configured",
        "node_counts": {},
    })
