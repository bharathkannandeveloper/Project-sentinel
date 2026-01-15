"""
Pattaasu Investment Analyzer

Implements the Pattaasu investment methodology for screening stocks
based on financial health, promoter integrity, and consistent cash flow.
"""
import logging
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from .models import (
    ConfidenceLevel,
    FinancialMetrics,
    InvestmentRating,
    InvestmentRecommendation,
    MoatRating,
    PattaasuMetrics,
    RiskAssessment,
    RiskLevel,
    StockAnalysis,
)

logger = logging.getLogger("sentinel.analysis.pattaasu")


class PattaasuAnalyzer:
    """
    Pattaasu Investment Methodology Analyzer.
    
    Evaluates stocks against the Pattaasu criteria:
    1. Zero/Low Debt: D/E < 1.0
    2. No Promoter Pledging: 0% pledged shares
    3. Consistent FCF: Positive for 3 consecutive years
    4. Strong Moat: Pricing power and competitive advantage
    
    Usage:
        analyzer = PattaasuAnalyzer()
        
        # Quick validation
        is_valid, errors = analyzer.quick_validate(metrics_dict)
        
        # Full analysis
        analysis = await analyzer.analyze(ticker, financial_data)
    """
    
    def __init__(self, llm_manager=None) -> None:
        """
        Initialize the analyzer.
        
        Args:
            llm_manager: Optional LLMManager for qualitative analysis
        """
        self.llm_manager = llm_manager
    
    def quick_validate(
        self,
        metrics: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        """
        Quick validation of Pattaasu criteria.
        
        Args:
            metrics: Dictionary with financial metrics
            
        Returns:
            Tuple of (is_compliant, list_of_errors)
        """
        errors = []
        
        # Check debt-to-equity
        d_e = metrics.get("debt_to_equity")
        if d_e is not None and Decimal(str(d_e)) >= Decimal("1.0"):
            errors.append(f"Debt-to-Equity {d_e} exceeds limit of 1.0")
        
        # Check promoter pledging
        pledging = metrics.get("promoter_pledging_pct")
        if pledging is not None and Decimal(str(pledging)) > Decimal("0"):
            errors.append(f"Promoter pledging {pledging}% detected (must be 0%)")
        
        # Check FCF
        fcf_years = [
            metrics.get("free_cash_flow_year1"),
            metrics.get("free_cash_flow_year2"),
            metrics.get("free_cash_flow_year3"),
        ]
        
        for i, fcf in enumerate(fcf_years, 1):
            if fcf is not None and Decimal(str(fcf)) <= Decimal("0"):
                errors.append(f"Negative FCF in Year {i}: {fcf}")
        
        return (len(errors) == 0, errors)
    
    def validate_pattaasu(
        self,
        metrics: dict[str, Any],
    ) -> PattaasuMetrics | None:
        """
        Validate metrics against Pattaasu criteria.
        
        Args:
            metrics: Dictionary with all required Pattaasu fields
            
        Returns:
            PattaasuMetrics if valid, None if validation fails
        """
        try:
            return PattaasuMetrics(**metrics)
        except ValidationError as e:
            logger.debug(f"Pattaasu validation failed: {e}")
            return None
    
    def calculate_risk_assessment(
        self,
        metrics: FinancialMetrics,
        pattaasu: PattaasuMetrics | None = None,
    ) -> RiskAssessment:
        """
        Calculate comprehensive risk assessment.
        
        Args:
            metrics: Financial metrics
            pattaasu: Optional Pattaasu metrics
            
        Returns:
            RiskAssessment with detailed risk analysis
        """
        risk_factors = []
        mitigants = []
        
        # Leverage risk
        d_e = metrics.debt_to_equity
        if d_e is None:
            leverage_risk = RiskLevel.MEDIUM
        elif d_e < Decimal("0.3"):
            leverage_risk = RiskLevel.LOW
            mitigants.append("Low leverage provides financial flexibility")
        elif d_e < Decimal("0.7"):
            leverage_risk = RiskLevel.MEDIUM
        elif d_e < Decimal("1.0"):
            leverage_risk = RiskLevel.HIGH
            risk_factors.append(f"Elevated leverage (D/E: {d_e})")
        else:
            leverage_risk = RiskLevel.CRITICAL
            risk_factors.append(f"Excessive leverage (D/E: {d_e})")
        
        # Liquidity risk (based on current ratio/cash)
        if metrics.cash_and_equivalents and metrics.total_liabilities:
            cash_ratio = metrics.cash_and_equivalents / metrics.total_liabilities
            if cash_ratio > Decimal("0.2"):
                liquidity_risk = RiskLevel.LOW
                mitigants.append("Strong cash position")
            elif cash_ratio > Decimal("0.1"):
                liquidity_risk = RiskLevel.MEDIUM
            else:
                liquidity_risk = RiskLevel.HIGH
                risk_factors.append("Limited liquidity buffer")
        else:
            liquidity_risk = RiskLevel.MEDIUM
        
        # Governance risk (from Pattaasu metrics)
        if pattaasu:
            if pattaasu.promoter_pledging_pct > Decimal("0"):
                governance_risk = RiskLevel.HIGH
                risk_factors.append(f"Promoter pledging: {pattaasu.promoter_pledging_pct}%")
            else:
                governance_risk = RiskLevel.LOW
                mitigants.append("Zero promoter pledging")
        else:
            governance_risk = RiskLevel.MEDIUM
        
        # Determine overall risk
        risk_levels = [leverage_risk, liquidity_risk, governance_risk]
        
        if RiskLevel.CRITICAL in risk_levels:
            overall_risk = RiskLevel.CRITICAL
        elif risk_levels.count(RiskLevel.HIGH) >= 2:
            overall_risk = RiskLevel.HIGH
        elif RiskLevel.HIGH in risk_levels:
            overall_risk = RiskLevel.MEDIUM
        elif risk_levels.count(RiskLevel.LOW) >= 2:
            overall_risk = RiskLevel.LOW
        else:
            overall_risk = RiskLevel.MEDIUM
        
        return RiskAssessment(
            ticker=metrics.ticker,
            overall_risk=overall_risk,
            leverage_risk=leverage_risk,
            liquidity_risk=liquidity_risk,
            governance_risk=governance_risk,
            risk_factors=risk_factors,
            mitigants=mitigants,
            confidence=ConfidenceLevel.MEDIUM,
        )
    
    async def analyze_moat_with_llm(
        self,
        ticker: str,
        company_description: str,
        md_and_a_text: str | None = None,
    ) -> tuple[MoatRating, str]:
        """
        Analyze competitive moat using LLM.
        
        Args:
            ticker: Stock ticker
            company_description: Company description
            md_and_a_text: Optional MD&A section from 10-K
            
        Returns:
            Tuple of (MoatRating, reasoning)
        """
        if not self.llm_manager:
            return MoatRating.NONE, "LLM not available for moat analysis"
        
        prompt = f"""Analyze the competitive moat for {ticker}.

Company Description:
{company_description}

{f"Management Discussion & Analysis:{chr(10)}{md_and_a_text}" if md_and_a_text else ""}

Evaluate the following moat factors:
1. Brand Power: Does the company have pricing power?
2. Switching Costs: How difficult is it for customers to switch?
3. Network Effects: Does value increase with more users?
4. Cost Advantages: Does the company have structural cost advantages?
5. Intangible Assets: Patents, licenses, regulatory approvals?

Output your analysis in this exact JSON format:
{{
    "moat_rating": "wide" | "narrow" | "none",
    "reasoning": "2-3 sentence explanation",
    "key_factors": ["factor1", "factor2"]
}}
"""
        
        try:
            response = await self.llm_manager.complete(
                prompt=prompt,
                temperature=0.3,
                max_tokens=500,
            )
            
            # Parse response
            import json
            import re
            
            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', response.content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                rating = MoatRating(data.get("moat_rating", "none").lower())
                reasoning = data.get("reasoning", "")
                return rating, reasoning
            
            return MoatRating.NONE, "Could not parse moat analysis"
            
        except Exception as e:
            logger.error(f"Moat analysis failed: {e}")
            return MoatRating.NONE, f"Analysis error: {e}"
    
    async def generate_recommendation(
        self,
        analysis: StockAnalysis,
    ) -> InvestmentRecommendation:
        """
        Generate investment recommendation based on analysis.
        
        Args:
            analysis: Complete stock analysis
            
        Returns:
            InvestmentRecommendation with rating and reasoning
        """
        # Determine rating based on Pattaasu score and risk
        pattaasu_score = analysis.pattaasu_score
        
        if analysis.is_pattaasu_compliant and pattaasu_score >= Decimal("80"):
            if analysis.risk and analysis.risk.overall_risk == RiskLevel.LOW:
                rating = InvestmentRating.STRONG_BUY
            else:
                rating = InvestmentRating.BUY
        elif analysis.is_pattaasu_compliant and pattaasu_score >= Decimal("60"):
            rating = InvestmentRating.BUY
        elif pattaasu_score >= Decimal("50"):
            rating = InvestmentRating.HOLD
        elif pattaasu_score >= Decimal("30"):
            rating = InvestmentRating.SELL
        else:
            rating = InvestmentRating.STRONG_SELL
        
        # Generate summary
        if analysis.is_pattaasu_compliant:
            summary = (
                f"{analysis.ticker} meets Pattaasu criteria with a score of {pattaasu_score}. "
                f"The company demonstrates financial discipline with low debt, "
                f"strong cash generation, and aligned promoter interests."
            )
        else:
            summary = (
                f"{analysis.ticker} does not meet full Pattaasu criteria (score: {pattaasu_score}). "
                f"Consider the risk factors before investing."
            )
        
        # Key points
        key_points = []
        if analysis.pattaasu:
            if analysis.pattaasu.debt_to_equity < Decimal("0.3"):
                key_points.append("Very low leverage - financial flexibility")
            if analysis.pattaasu.moat_rating == MoatRating.WIDE:
                key_points.append("Wide competitive moat - pricing power")
            if analysis.pattaasu.fcf_3yr_average > Decimal("0"):
                key_points.append("Consistent positive free cash flow")
        
        # Risks
        risks = []
        if analysis.risk:
            risks = analysis.risk.risk_factors[:3]  # Top 3 risks
        
        return InvestmentRecommendation(
            ticker=analysis.ticker,
            company_name=analysis.company_name,
            rating=rating,
            summary=summary,
            key_points=key_points,
            risks=risks,
            pattaasu_score=pattaasu_score,
            is_pattaasu_compliant=analysis.is_pattaasu_compliant,
            confidence=analysis.confidence,
        )
    
    async def full_analysis(
        self,
        ticker: str,
        financial_data: dict[str, Any],
        company_description: str = "",
        md_and_a_text: str | None = None,
    ) -> StockAnalysis:
        """
        Perform complete Pattaasu analysis on a stock.
        
        Args:
            ticker: Stock ticker symbol
            financial_data: Dictionary with financial metrics
            company_description: Company description for moat analysis
            md_and_a_text: Optional MD&A text for qualitative analysis
            
        Returns:
            Complete StockAnalysis
        """
        # Create financial metrics
        metrics = FinancialMetrics(
            ticker=ticker,
            **{k: v for k, v in financial_data.items() if v is not None}
        )
        
        # Attempt Pattaasu validation
        pattaasu_data = {
            "ticker": ticker,
            "debt_to_equity": financial_data.get("debt_to_equity", Decimal("0")),
            "total_debt": financial_data.get("total_debt", Decimal("0")),
            "total_equity": financial_data.get("total_equity", Decimal("1")),
            "promoter_pledging_pct": financial_data.get("promoter_pledging_pct", Decimal("0")),
            "free_cash_flow_year1": financial_data.get("free_cash_flow_year1", Decimal("0")),
            "free_cash_flow_year2": financial_data.get("free_cash_flow_year2", Decimal("0")),
            "free_cash_flow_year3": financial_data.get("free_cash_flow_year3", Decimal("0")),
        }
        
        pattaasu = self.validate_pattaasu(pattaasu_data)
        is_compliant = pattaasu is not None
        pattaasu_score = pattaasu.pattaasu_score if pattaasu else Decimal("0")
        
        # Calculate risk
        risk = self.calculate_risk_assessment(metrics, pattaasu)
        
        # Analyze moat if LLM available
        moat_analysis = ""
        if self.llm_manager and company_description:
            moat_rating, moat_reasoning = await self.analyze_moat_with_llm(
                ticker, company_description, md_and_a_text
            )
            moat_analysis = moat_reasoning
            
            # Update Pattaasu with moat if valid
            if pattaasu:
                pattaasu.moat_rating = moat_rating
                pattaasu.moat_reasoning = moat_reasoning
        
        return StockAnalysis(
            ticker=ticker,
            company_name=financial_data.get("company_name", ""),
            sector=financial_data.get("sector", ""),
            industry=financial_data.get("industry", ""),
            metrics=metrics,
            pattaasu=pattaasu,
            is_pattaasu_compliant=is_compliant,
            pattaasu_score=pattaasu_score,
            risk=risk,
            moat_analysis=moat_analysis,
            confidence=ConfidenceLevel.MEDIUM,
        )
