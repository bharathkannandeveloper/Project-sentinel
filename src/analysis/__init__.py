"""
Investment Analysis Module

This module implements the Pattaasu investment methodology for identifying
high-quality stocks with zero-debt balance sheets, high promoter integrity,
and consistent free cash flow.
"""

from .models import (
    PattaasuMetrics,
    StockAnalysis,
    RiskAssessment,
    InvestmentRecommendation,
)
from .pattaasu import PattaasuAnalyzer

__all__ = [
    "PattaasuMetrics",
    "StockAnalysis",
    "RiskAssessment",
    "InvestmentRecommendation",
    "PattaasuAnalyzer",
]
