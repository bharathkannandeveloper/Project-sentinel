"""
Celery Tasks for Data Ingestion

Implements distributed data fetching using Celery Canvas patterns.
Uses Chord workflows for sector-level aggregation.
"""
import asyncio
import logging
from decimal import Decimal
from typing import Any

from celery import shared_task, chord, group
from celery.exceptions import SoftTimeLimitExceeded

from .handlers import FailureObject, FailureType, get_failure_handler

logger = logging.getLogger("sentinel.ingestion.tasks")


# =============================================================================
# INDIVIDUAL COMPANY TASKS
# =============================================================================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=30,
    time_limit=60,
    queue="ingestion",
)
def fetch_company_metrics(self, ticker: str) -> dict[str, Any] | dict[str, str]:
    """
    Fetch financial metrics for a single company.
    
    This task is designed to be used in a Celery Chord. On failure,
    it returns a FailureObject dict instead of raising an exception,
    allowing the Chord callback to proceed with partial data.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        Dictionary with financial metrics or failure object
    """
    logger.info(f"Fetching metrics for {ticker}")
    
    try:
        # TODO: Implement actual data fetching from APIs
        # For now, return mock data structure
        
        # Simulate API call (replace with actual implementation)
        metrics = _fetch_from_api(ticker)
        
        return {
            "ticker": ticker,
            "success": True,
            "data": metrics,
        }
        
    except SoftTimeLimitExceeded:
        failure = FailureObject(
            ticker=ticker,
            failure_type=FailureType.TIMEOUT,
            message="Task timeout exceeded",
            retry_count=self.request.retries,
        )
        get_failure_handler().log_failure(failure)
        return {"ticker": ticker, "success": False, "failure": failure.to_dict()}
        
    except Exception as e:
        # Determine failure type
        failure_type = _classify_error(e)
        
        failure = FailureObject(
            ticker=ticker,
            failure_type=failure_type,
            message=str(e),
            retry_count=self.request.retries,
            raw_error=repr(e),
        )
        
        # Log to Redis
        get_failure_handler().log_failure(failure)
        
        # Retry if appropriate
        if failure.is_retryable:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        
        return {"ticker": ticker, "success": False, "failure": failure.to_dict()}


def _fetch_from_api(ticker: str) -> dict[str, Any]:
    """
    Fetch data from financial API using Yahoo Finance.
    
    Runs the async fetcher in a sync context for Celery.
    """
    import asyncio
    from .fetchers import YahooFinanceFetcher
    
    async def _async_fetch():
        fetcher = YahooFinanceFetcher()
        try:
            # Get financial data
            financials = await fetcher.get_financials(ticker)
            profile = await fetcher.get_profile(ticker)
            
            if not financials:
                # Return minimal data if fetch fails
                return {
                    "company_name": ticker,
                    "data_source": "yahoo_finance",
                    "error": "Failed to fetch financial data",
                }
            
            return {
                "company_name": profile.name if profile else ticker,
                "sector": profile.sector if profile else "",
                "industry": profile.industry if profile else "",
                "revenue": financials.revenue,
                "net_income": financials.net_income,
                "total_debt": financials.total_debt,
                "total_equity": financials.total_equity,
                "free_cash_flow": financials.free_cash_flow,
                "debt_to_equity": financials.debt_to_equity,
                "promoter_pledging_pct": Decimal("0"),  # Not available in Yahoo
                "free_cash_flow_year1": financials.free_cash_flow_year1,
                "free_cash_flow_year2": financials.free_cash_flow_year2,
                "free_cash_flow_year3": financials.free_cash_flow_year3,
                "pe_ratio": financials.pe_ratio,
                "data_source": "yahoo_finance",
            }
        finally:
            await fetcher.close()
    
    # Run async function in sync context
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(_async_fetch())


def _classify_error(error: Exception) -> FailureType:
    """Classify an exception into a FailureType."""
    error_str = str(error).lower()
    
    if "rate limit" in error_str or "429" in error_str:
        return FailureType.RATE_LIMIT
    elif "timeout" in error_str or "timed out" in error_str:
        return FailureType.TIMEOUT
    elif "not found" in error_str or "404" in error_str:
        return FailureType.NOT_FOUND
    elif "unauthorized" in error_str or "401" in error_str or "403" in error_str:
        return FailureType.AUTH_ERROR
    elif "connection" in error_str or "network" in error_str:
        return FailureType.NETWORK_ERROR
    elif "parse" in error_str or "json" in error_str or "xml" in error_str:
        return FailureType.PARSE_ERROR
    else:
        return FailureType.UNKNOWN


# =============================================================================
# SECTOR ANALYSIS CHORD
# =============================================================================

@shared_task(
    bind=True,
    soft_time_limit=300,
    time_limit=360,
    queue="analysis",
)
def aggregate_sector_data(self, results: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Aggregate data from multiple company fetches.
    
    This is the callback for the sector analysis Chord.
    It processes successful results and logs failures.
    
    Args:
        results: List of results from fetch_company_metrics tasks
        
    Returns:
        Aggregated sector metrics
    """
    logger.info(f"Aggregating data from {len(results)} companies")
    
    # Separate successes and failures
    successful = []
    failures = []
    
    for result in results:
        if result.get("success"):
            successful.append(result)
        else:
            failures.append(result)
    
    # Check data integrity
    total = len(results)
    success_rate = len(successful) / total if total > 0 else 0
    
    is_impaired = success_rate < 0.9  # Less than 90% success = impaired
    
    # Calculate aggregated metrics
    if successful:
        avg_de = sum(
            Decimal(str(r["data"].get("debt_to_equity", 0))) 
            for r in successful
        ) / len(successful)
        
        avg_fcf = sum(
            Decimal(str(r["data"].get("free_cash_flow", 0)))
            for r in successful
        ) / len(successful)
    else:
        avg_de = Decimal("0")
        avg_fcf = Decimal("0")
    
    return {
        "total_companies": total,
        "successful": len(successful),
        "failed": len(failures),
        "success_rate": float(success_rate),
        "is_impaired": is_impaired,
        "metrics": {
            "avg_debt_to_equity": float(avg_de),
            "avg_free_cash_flow": float(avg_fcf),
        },
        "failures": [f.get("failure", {}) for f in failures],
    }


@shared_task(bind=True, queue="ingestion")
def analyze_sector(self, sector_name: str, tickers: list[str]) -> dict[str, Any]:
    """
    Analyze an entire sector using Celery Chord.
    
    Creates a parallel group of fetch tasks and aggregates results.
    
    Args:
        sector_name: Name of the sector
        tickers: List of ticker symbols in the sector
        
    Returns:
        Task ID for the chord workflow
    """
    logger.info(f"Starting sector analysis for {sector_name} ({len(tickers)} stocks)")
    
    # Create the Chord workflow
    workflow = chord(
        # Header: Group of parallel fetch tasks
        group(fetch_company_metrics.s(ticker) for ticker in tickers),
        # Body: Aggregation callback
        aggregate_sector_data.s()
    )
    
    # Execute the workflow
    result = workflow.apply_async()
    
    return {
        "sector": sector_name,
        "task_id": result.id,
        "status": "started",
        "companies": len(tickers),
    }


# =============================================================================
# UTILITY TASKS
# =============================================================================

@shared_task(queue="ingestion")
def health_check() -> dict[str, str]:
    """Simple health check task."""
    return {"status": "healthy", "queue": "ingestion"}


@shared_task(queue="analysis")
def get_failure_statistics() -> dict[str, Any]:
    """Get failure statistics from the handler."""
    handler = get_failure_handler()
    return {
        "stats": handler.get_failure_stats(),
        "recent": handler.get_recent_failures(limit=10),
    }
