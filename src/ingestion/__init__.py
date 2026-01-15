"""
Data Ingestion Module

Handles distributed data fetching from financial sources using Celery Canvas.
"""

from .handlers import FailureHandler, FailureObject
from .tasks import (
    fetch_company_metrics,
    analyze_sector,
    aggregate_sector_data,
)

__all__ = [
    "FailureHandler",
    "FailureObject",
    "fetch_company_metrics",
    "analyze_sector",
    "aggregate_sector_data",
]
