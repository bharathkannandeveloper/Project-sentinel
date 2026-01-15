"""
Deep Analysis Engine

Comprehensive stock analysis combining:
- Fundamental Analysis (Balance Sheet, Cash Flow, Ratios)
- Technical Analysis (RSI, MACD, Moving Averages)
- Sentiment Analysis (News, Social)
- Rating Generation (Strong Buy → Strong Sell)
"""
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

logger = logging.getLogger("sentinel.analysis.deep")


class Rating(Enum):
    """Investment rating scale."""
    STRONG_BUY = "STRONG BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG SELL"


class Trend(Enum):
    """Price/metric trend."""
    STRONG_UP = "Strong Uptrend"
    UP = "Uptrend"
    SIDEWAYS = "Sideways"
    DOWN = "Downtrend"
    STRONG_DOWN = "Strong Downtrend"


# =============================================================================
# FUNDAMENTAL ANALYSIS
# =============================================================================

@dataclass
class FundamentalScore:
    """Fundamental analysis results."""
    # Profitability (0-25 points)
    roe: Decimal | None = None
    roce: Decimal | None = None
    profit_margin: Decimal | None = None
    profitability_score: int = 0
    
    # Solvency (0-25 points) 
    debt_to_equity: Decimal | None = None
    current_ratio: Decimal | None = None
    interest_coverage: Decimal | None = None
    solvency_score: int = 0
    
    # Efficiency (0-25 points)
    asset_turnover: Decimal | None = None
    inventory_turnover: Decimal | None = None
    receivables_turnover: Decimal | None = None
    efficiency_score: int = 0
    
    # Growth (0-25 points)
    revenue_growth: Decimal | None = None
    eps_growth: Decimal | None = None
    fcf_growth: Decimal | None = None
    growth_score: int = 0
    
    # Pattaasu Criteria
    pattaasu_debt_ok: bool = False
    pattaasu_pledging_ok: bool = True
    pattaasu_fcf_ok: bool = False
    
    # Total
    total_score: int = 0
    
    def calculate_total(self) -> int:
        """Calculate total fundamental score (0-100)."""
        self.total_score = (
            self.profitability_score +
            self.solvency_score +
            self.efficiency_score +
            self.growth_score
        )
        return self.total_score


# =============================================================================
# TECHNICAL ANALYSIS
# =============================================================================

@dataclass
class TechnicalIndicators:
    """Technical analysis indicators."""
    # Momentum
    rsi: Decimal | None = None
    rsi_signal: str = ""  # Oversold, Overbought, Neutral
    
    macd: Decimal | None = None
    macd_signal: Decimal | None = None
    macd_histogram: Decimal | None = None
    macd_trend: str = ""  # Bullish, Bearish, Neutral
    
    # Moving Averages
    sma_20: Decimal | None = None
    sma_50: Decimal | None = None
    sma_200: Decimal | None = None
    price_vs_sma: str = ""  # Above All, Below All, Mixed
    
    # Volatility
    bollinger_upper: Decimal | None = None
    bollinger_lower: Decimal | None = None
    atr: Decimal | None = None
    
    # Trend
    trend: Trend = Trend.SIDEWAYS
    support_level: Decimal | None = None
    resistance_level: Decimal | None = None
    
    # Score (0-100)
    technical_score: int = 50


@dataclass
class TechnicalScore:
    """Technical analysis summary."""
    indicators: TechnicalIndicators | None = None
    trend: Trend = Trend.SIDEWAYS
    signal: str = "NEUTRAL"  # BUY, SELL, NEUTRAL
    strength: int = 50  # 0-100
    
    key_levels: dict[str, Decimal] = field(default_factory=dict)
    patterns_detected: list[str] = field(default_factory=list)


# =============================================================================
# SENTIMENT ANALYSIS
# =============================================================================

@dataclass
class SentimentScore:
    """Sentiment analysis results."""
    # News Sentiment (-100 to +100)
    news_score: int = 0
    news_count: int = 0
    news_summary: str = ""
    
    # Social Sentiment
    social_score: int = 0
    social_volume: int = 0
    
    # Analyst Ratings
    analyst_buy: int = 0
    analyst_hold: int = 0
    analyst_sell: int = 0
    analyst_consensus: str = ""
    
    # Insider Activity
    insider_buying: Decimal = Decimal("0")
    insider_selling: Decimal = Decimal("0")
    insider_signal: str = ""
    
    # Overall (-100 to +100)
    overall_sentiment: int = 0


# =============================================================================
# GEOPOLITICAL / BUTTERFLY EFFECT
# =============================================================================

@dataclass
class ButterflyEffect:
    """Geopolitical impact analysis."""
    # Active Events
    active_events: list[str] = field(default_factory=list)
    
    # Impact Chains
    positive_factors: list[str] = field(default_factory=list)
    negative_factors: list[str] = field(default_factory=list)
    
    # Sector Exposure
    sector_risk: str = ""  # Low, Medium, High
    sector_opportunity: str = ""
    
    # Score (-50 to +50)
    geo_score: int = 0


# =============================================================================
# COMBINED ANALYSIS
# =============================================================================

@dataclass
class DeepAnalysis:
    """Complete stock analysis."""
    symbol: str
    company_name: str
    sector: str = ""
    industry: str = ""
    
    # Current Price
    current_price: Decimal = Decimal("0")
    change_percent: Decimal = Decimal("0")
    
    # Analysis Components
    fundamental: FundamentalScore | None = None
    technical: TechnicalScore | None = None
    sentiment: SentimentScore | None = None
    butterfly: ButterflyEffect | None = None
    
    # Final Rating
    rating: Rating = Rating.HOLD
    confidence: int = 50  # 0-100
    target_price: Decimal | None = None
    
    # Summary
    bull_case: list[str] = field(default_factory=list)
    bear_case: list[str] = field(default_factory=list)
    key_risks: list[str] = field(default_factory=list)
    recommendation: str = ""


# =============================================================================
# ANALYSIS ENGINE
# =============================================================================

class DeepAnalyzer:
    """
    Comprehensive stock analysis engine.
    
    Combines fundamental, technical, sentiment, and geopolitical
    analysis to generate a final rating with confidence score.
    """
    
    def __init__(self, llm_manager: Any = None) -> None:
        """
        Initialize analyzer.
        
        Args:
            llm_manager: Optional LLM manager for AI analysis
        """
        self.llm = llm_manager
    
    def analyze_fundamentals(
        self,
        financials: dict[str, Any],
    ) -> FundamentalScore:
        """
        Analyze fundamental metrics.
        
        Args:
            financials: Financial data dictionary
            
        Returns:
            FundamentalScore with ratings
        """
        score = FundamentalScore()
        
        # Extract values
        de = self._to_decimal(financials.get("debt_to_equity", 99))
        roe = self._to_decimal(financials.get("roe"))
        roce = self._to_decimal(financials.get("roce"))
        current_ratio = self._to_decimal(financials.get("current_ratio"))
        margin = self._to_decimal(financials.get("profit_margin"))
        revenue_growth = self._to_decimal(financials.get("revenue_growth"))
        fcf = self._to_decimal(financials.get("free_cash_flow", 0))
        fcf_y1 = self._to_decimal(financials.get("free_cash_flow_year1", 0))
        fcf_y2 = self._to_decimal(financials.get("free_cash_flow_year2", 0))
        fcf_y3 = self._to_decimal(financials.get("free_cash_flow_year3", 0))
        
        score.debt_to_equity = de
        score.roe = roe
        score.roce = roce
        score.profit_margin = margin
        score.revenue_growth = revenue_growth
        
        # Profitability Score (0-25)
        prof_score = 0
        if roe and roe > Decimal("15"):
            prof_score += 10
        elif roe and roe > Decimal("10"):
            prof_score += 5
        
        if roce and roce > Decimal("15"):
            prof_score += 10
        elif roce and roce > Decimal("10"):
            prof_score += 5
        
        if margin and margin > Decimal("15"):
            prof_score += 5
        elif margin and margin > Decimal("10"):
            prof_score += 3
        
        score.profitability_score = min(prof_score, 25)
        
        # Solvency Score (0-25) - Pattaasu aligned
        solv_score = 0
        if de is not None:
            if de < Decimal("0.1"):
                solv_score += 15
                score.pattaasu_debt_ok = True
            elif de < Decimal("0.5"):
                solv_score += 10
                score.pattaasu_debt_ok = True
            elif de < Decimal("1.0"):
                solv_score += 5
                score.pattaasu_debt_ok = True
            else:
                score.pattaasu_debt_ok = False
        
        if current_ratio and current_ratio > Decimal("1.5"):
            solv_score += 10
        elif current_ratio and current_ratio > Decimal("1.0"):
            solv_score += 5
        
        score.solvency_score = min(solv_score, 25)
        
        # Growth Score (0-25)
        growth_score = 0
        if revenue_growth and revenue_growth > Decimal("15"):
            growth_score += 15
        elif revenue_growth and revenue_growth > Decimal("10"):
            growth_score += 10
        elif revenue_growth and revenue_growth > Decimal("5"):
            growth_score += 5
        
        # FCF check for Pattaasu
        if fcf_y1 and fcf_y1 > 0 and fcf_y2 and fcf_y2 > 0 and fcf_y3 and fcf_y3 > 0:
            score.pattaasu_fcf_ok = True
            growth_score += 10
        elif fcf and fcf > 0:
            growth_score += 5
        
        score.growth_score = min(growth_score, 25)
        
        # Efficiency (placeholder)
        score.efficiency_score = 12  # Default middle score
        
        score.calculate_total()
        return score
    
    def analyze_technicals(
        self,
        price_data: dict[str, Any],
    ) -> TechnicalScore:
        """
        Analyze technical indicators.
        
        For now returns a simplified score.
        Full implementation would use actual price history.
        """
        score = TechnicalScore()
        indicators = TechnicalIndicators()
        
        current = self._to_decimal(price_data.get("current_price", 0))
        change = self._to_decimal(price_data.get("change_percent", 0))
        
        # Simple trend detection from change
        if change and change > Decimal("2"):
            score.trend = Trend.STRONG_UP
            score.signal = "BUY"
            score.strength = 70
        elif change and change > Decimal("0.5"):
            score.trend = Trend.UP
            score.signal = "BUY"
            score.strength = 60
        elif change and change < Decimal("-2"):
            score.trend = Trend.STRONG_DOWN
            score.signal = "SELL"
            score.strength = 30
        elif change and change < Decimal("-0.5"):
            score.trend = Trend.DOWN
            score.signal = "SELL"
            score.strength = 40
        else:
            score.trend = Trend.SIDEWAYS
            score.signal = "NEUTRAL"
            score.strength = 50
        
        # Placeholder RSI (would calculate from price history)
        indicators.rsi = Decimal("50")
        indicators.rsi_signal = "Neutral"
        
        score.indicators = indicators
        return score
    
    def generate_rating(
        self,
        fundamental: FundamentalScore,
        technical: TechnicalScore,
        sentiment: SentimentScore | None = None,
        butterfly: ButterflyEffect | None = None,
    ) -> tuple[Rating, int]:
        """
        Generate final rating from all analysis.
        
        Returns:
            Tuple of (Rating, confidence %)
        """
        # Weighted score calculation
        fund_weight = 0.50  # 50% fundamental
        tech_weight = 0.25  # 25% technical
        sent_weight = 0.15  # 15% sentiment
        geo_weight = 0.10   # 10% geopolitical
        
        # Normalize scores to 0-100
        fund_score = fundamental.total_score if fundamental else 50
        tech_score = technical.strength if technical else 50
        sent_score = ((sentiment.overall_sentiment + 100) / 2) if sentiment else 50
        geo_score = ((butterfly.geo_score + 50)) if butterfly else 50
        
        # Calculate weighted average
        total = (
            fund_score * fund_weight +
            tech_score * tech_weight +
            sent_score * sent_weight +
            geo_score * geo_weight
        )
        
        # Pattaasu bonus/penalty
        if fundamental:
            if fundamental.pattaasu_debt_ok and fundamental.pattaasu_fcf_ok:
                total += 10  # Bonus for Pattaasu compliance
            elif not fundamental.pattaasu_debt_ok:
                total -= 15  # Penalty for high debt
        
        total = max(0, min(100, total))
        
        # Convert to rating
        if total >= 80:
            rating = Rating.STRONG_BUY
            confidence = min(95, int(total))
        elif total >= 65:
            rating = Rating.BUY
            confidence = min(85, int(total))
        elif total >= 45:
            rating = Rating.HOLD
            confidence = 60
        elif total >= 30:
            rating = Rating.SELL
            confidence = min(75, 100 - int(total))
        else:
            rating = Rating.STRONG_SELL
            confidence = min(90, 100 - int(total))
        
        return rating, confidence
    
    def generate_bull_bear_cases(
        self,
        fundamental: FundamentalScore,
        technical: TechnicalScore,
    ) -> tuple[list[str], list[str], list[str]]:
        """Generate bull case, bear case, and key risks."""
        bull_case = []
        bear_case = []
        risks = []
        
        # Fundamental factors
        if fundamental:
            if fundamental.pattaasu_debt_ok:
                bull_case.append("Low debt levels (Pattaasu compliant)")
            else:
                bear_case.append("High debt-to-equity ratio")
                risks.append("Leverage risk in downturn")
            
            if fundamental.pattaasu_fcf_ok:
                bull_case.append("Consistent positive free cash flow")
            else:
                bear_case.append("Inconsistent cash generation")
            
            if fundamental.roe and fundamental.roe > Decimal("15"):
                bull_case.append(f"Strong ROE of {fundamental.roe}%")
            
            if fundamental.profitability_score >= 20:
                bull_case.append("High profitability metrics")
            elif fundamental.profitability_score <= 10:
                bear_case.append("Weak profitability")
        
        # Technical factors
        if technical:
            if technical.trend in [Trend.STRONG_UP, Trend.UP]:
                bull_case.append(f"Price in {technical.trend.value}")
            elif technical.trend in [Trend.STRONG_DOWN, Trend.DOWN]:
                bear_case.append(f"Price in {technical.trend.value}")
        
        return bull_case, bear_case, risks
    
    def create_analysis(
        self,
        symbol: str,
        company_name: str,
        financials: dict[str, Any],
        price_data: dict[str, Any],
        sector: str = "",
        industry: str = "",
    ) -> DeepAnalysis:
        """
        Create complete analysis for a stock.
        
        Args:
            symbol: Stock symbol
            company_name: Company name
            financials: Financial data
            price_data: Price and quote data
            sector: Sector name
            industry: Industry name
            
        Returns:
            DeepAnalysis with all components
        """
        # Run analyses
        fundamental = self.analyze_fundamentals(financials)
        technical = self.analyze_technicals(price_data)
        
        # Generate rating
        rating, confidence = self.generate_rating(fundamental, technical)
        
        # Generate cases
        bull, bear, risks = self.generate_bull_bear_cases(fundamental, technical)
        
        # Build recommendation text
        if rating == Rating.STRONG_BUY:
            rec = f"{symbol} looks excellent! Pattaasu aligned with strong fundamentals."
        elif rating == Rating.BUY:
            rec = f"{symbol} shows good potential. Consider accumulating on dips."
        elif rating == Rating.HOLD:
            rec = f"{symbol} is neutral. Wait for clearer signals before acting."
        elif rating == Rating.SELL:
            rec = f"{symbol} has concerning metrics. Consider reducing exposure."
        else:
            rec = f"{symbol} shows major red flags. Exit recommended."
        
        return DeepAnalysis(
            symbol=symbol,
            company_name=company_name,
            sector=sector,
            industry=industry,
            current_price=self._to_decimal(price_data.get("price", 0)) or Decimal("0"),
            change_percent=self._to_decimal(price_data.get("change_percent", 0)) or Decimal("0"),
            fundamental=fundamental,
            technical=technical,
            rating=rating,
            confidence=confidence,
            bull_case=bull,
            bear_case=bear,
            key_risks=risks,
            recommendation=rec,
        )
    
    def _to_decimal(self, value: Any) -> Decimal | None:
        """Safely convert to Decimal."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return None


# Convenience function
def quick_analyze(
    symbol: str,
    financials: dict[str, Any],
    price: float,
    change_percent: float = 0,
) -> dict[str, Any]:
    """
    Quick analysis for a stock.
    
    Returns simplified analysis dict.
    """
    analyzer = DeepAnalyzer()
    
    result = analyzer.create_analysis(
        symbol=symbol,
        company_name=financials.get("company_name", symbol),
        financials=financials,
        price_data={"price": price, "change_percent": change_percent},
        sector=financials.get("sector", ""),
        industry=financials.get("industry", ""),
    )
    
    return {
        "symbol": result.symbol,
        "rating": result.rating.value,
        "confidence": result.confidence,
        "fundamental_score": result.fundamental.total_score if result.fundamental else 0,
        "pattaasu_compliant": (
            result.fundamental.pattaasu_debt_ok and 
            result.fundamental.pattaasu_fcf_ok
        ) if result.fundamental else False,
        "bull_case": result.bull_case,
        "bear_case": result.bear_case,
        "recommendation": result.recommendation,
    }
