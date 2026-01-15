"""
Pydantic Models for Financial Analysis

Defines strict data validation models implementing the Pattaasu investment
criteria. Uses Pydantic v2 for runtime validation and type safety.
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    ConfigDict,
)


class InvestmentRating(str, Enum):
    """Investment recommendation rating."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class ConfidenceLevel(str, Enum):
    """Confidence level for analysis."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MoatRating(str, Enum):
    """Competitive moat strength rating."""
    WIDE = "wide"         # Strong pricing power, high barriers
    NARROW = "narrow"     # Some competitive advantage
    NONE = "none"         # No sustainable advantage


class RiskLevel(str, Enum):
    """Risk assessment level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Custom types with validation
PositiveDecimal = Annotated[Decimal, Field(ge=0)]
Percentage = Annotated[Decimal, Field(ge=0, le=100)]
Ratio = Annotated[Decimal, Field(ge=0)]


class FinancialMetrics(BaseModel):
    """Base financial metrics for a company."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    # Identification
    ticker: str = Field(..., min_length=1, max_length=10)
    company_name: str = Field(default="")
    cik: str | None = Field(default=None, description="SEC CIK number")
    
    # Revenue metrics
    revenue: PositiveDecimal | None = Field(default=None, description="Annual revenue in base currency")
    revenue_growth_yoy: Decimal | None = Field(default=None, description="Year-over-year revenue growth %")
    
    # Profitability
    net_income: Decimal | None = Field(default=None)
    gross_margin: Percentage | None = Field(default=None)
    operating_margin: Percentage | None = Field(default=None)
    net_margin: Percentage | None = Field(default=None)
    
    # Balance sheet
    total_assets: PositiveDecimal | None = Field(default=None)
    total_liabilities: PositiveDecimal | None = Field(default=None)
    total_equity: Decimal | None = Field(default=None)
    total_debt: PositiveDecimal | None = Field(default=None, description="Short-term + long-term debt")
    cash_and_equivalents: PositiveDecimal | None = Field(default=None)
    
    # Cash flow
    operating_cash_flow: Decimal | None = Field(default=None)
    free_cash_flow: Decimal | None = Field(default=None)
    capital_expenditures: Decimal | None = Field(default=None)
    
    # Valuation
    market_cap: PositiveDecimal | None = Field(default=None)
    enterprise_value: PositiveDecimal | None = Field(default=None)
    pe_ratio: Decimal | None = Field(default=None)
    pb_ratio: Decimal | None = Field(default=None)
    ev_ebitda: Decimal | None = Field(default=None)
    
    # Per share
    eps: Decimal | None = Field(default=None)
    book_value_per_share: Decimal | None = Field(default=None)
    
    # Dividends
    dividend_yield: Percentage | None = Field(default=None)
    payout_ratio: Percentage | None = Field(default=None)
    
    # Metadata
    fiscal_year_end: datetime | None = Field(default=None)
    data_source: str = Field(default="unknown")
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def debt_to_equity(self) -> Decimal | None:
        """Calculate debt-to-equity ratio."""
        if self.total_debt is None or self.total_equity is None:
            return None
        if self.total_equity <= 0:
            return Decimal("999.99")  # Infinite/undefined
        return self.total_debt / self.total_equity


class PattaasuMetrics(BaseModel):
    """
    Pattaasu Investment Criteria Validation Model.
    
    Implements strict validation for the Pattaasu methodology:
    1. Debt-to-Equity < 1.0 (preferably near zero)
    2. Promoter Pledging = 0%
    3. Free Cash Flow > 0 for trailing 3 years
    4. Strong branding/moat power
    
    Validation errors indicate non-compliance with criteria.
    """
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_default=True,
        extra="forbid",
    )
    
    # Core identification
    ticker: str = Field(..., min_length=1, max_length=10)
    company_name: str = Field(default="")
    
    # Pattaasu Criterion 1: Debt levels
    debt_to_equity: Decimal = Field(
        ...,
        description="Total Debt / Total Shareholder Equity. Must be < 1.0"
    )
    total_debt: PositiveDecimal = Field(
        default=Decimal("0"),
        description="Total debt (short-term + long-term)"
    )
    total_equity: Decimal = Field(
        default=Decimal("1"),
        description="Total shareholders' equity"
    )
    
    # Pattaasu Criterion 2: Promoter integrity
    promoter_pledging_pct: Percentage = Field(
        ...,
        description="Percentage of promoter shares pledged. Must be 0%"
    )
    promoter_holding_pct: Percentage | None = Field(
        default=None,
        description="Total promoter holding percentage"
    )
    
    # Pattaasu Criterion 3: Cash flow consistency
    free_cash_flow_year1: Decimal = Field(
        ...,
        description="FCF in most recent fiscal year"
    )
    free_cash_flow_year2: Decimal = Field(
        ...,
        description="FCF in previous fiscal year"
    )
    free_cash_flow_year3: Decimal = Field(
        ...,
        description="FCF in fiscal year before previous"
    )
    
    # Pattaasu Criterion 4: Moat strength (qualitative)
    moat_rating: MoatRating = Field(
        default=MoatRating.NONE,
        description="Competitive moat strength"
    )
    moat_reasoning: str = Field(
        default="",
        description="Explanation of moat assessment"
    )
    
    # Calculated scores
    pattaasu_score: Decimal = Field(
        default=Decimal("0"),
        description="Overall Pattaasu compliance score (0-100)"
    )
    
    @field_validator("debt_to_equity")
    @classmethod
    def validate_debt_to_equity(cls, v: Decimal) -> Decimal:
        """
        Validate debt-to-equity ratio.
        
        Pattaasu criteria: D/E must be less than 1.0
        Ideal: Near zero (debt-free)
        """
        if v >= Decimal("1.0"):
            raise ValueError(
                f"Debt-to-Equity ratio {v} exceeds Pattaasu limit of 1.0. "
                f"Company has excessive leverage."
            )
        if v < Decimal("0"):
            raise ValueError(f"Invalid negative D/E ratio: {v}")
        return v
    
    @field_validator("promoter_pledging_pct")
    @classmethod
    def validate_promoter_pledging(cls, v: Decimal) -> Decimal:
        """
        Validate promoter pledging percentage.
        
        Pattaasu criteria: Pledging MUST be exactly 0%
        Any pledging indicates promoter financial stress.
        """
        if v > Decimal("0"):
            raise ValueError(
                f"Promoter pledging detected: {v}%. "
                f"Pattaasu criteria requires 0% pledging. "
                f"High pledging indicates promoter financial stress."
            )
        return v
    
    @model_validator(mode="after")
    def validate_cash_flow_consistency(self) -> "PattaasuMetrics":
        """
        Validate 3-year free cash flow positivity.
        
        All three years must have positive FCF.
        """
        fcf_values = [
            ("Year 1", self.free_cash_flow_year1),
            ("Year 2", self.free_cash_flow_year2),
            ("Year 3", self.free_cash_flow_year3),
        ]
        
        negative_years = [
            name for name, fcf in fcf_values if fcf <= Decimal("0")
        ]
        
        if negative_years:
            raise ValueError(
                f"Negative FCF in: {', '.join(negative_years)}. "
                f"Pattaasu criteria requires positive FCF for all 3 years."
            )
        
        return self
    
    @model_validator(mode="after")
    def calculate_pattaasu_score(self) -> "PattaasuMetrics":
        """Calculate overall Pattaasu compliance score."""
        score = Decimal("0")
        
        # Debt score (max 30 points)
        if self.debt_to_equity == Decimal("0"):
            score += Decimal("30")
        elif self.debt_to_equity < Decimal("0.1"):
            score += Decimal("25")
        elif self.debt_to_equity < Decimal("0.3"):
            score += Decimal("20")
        elif self.debt_to_equity < Decimal("0.5"):
            score += Decimal("15")
        else:
            score += Decimal("10")
        
        # Pledging score (max 25 points - all or nothing)
        if self.promoter_pledging_pct == Decimal("0"):
            score += Decimal("25")
        
        # FCF score (max 25 points)
        avg_fcf = (
            self.free_cash_flow_year1 +
            self.free_cash_flow_year2 +
            self.free_cash_flow_year3
        ) / 3
        if avg_fcf > Decimal("0"):
            score += Decimal("25")
        
        # Moat score (max 20 points)
        moat_scores = {
            MoatRating.WIDE: Decimal("20"),
            MoatRating.NARROW: Decimal("10"),
            MoatRating.NONE: Decimal("0"),
        }
        score += moat_scores.get(self.moat_rating, Decimal("0"))
        
        self.pattaasu_score = score
        return self
    
    @property
    def fcf_3yr_average(self) -> Decimal:
        """Calculate 3-year average FCF."""
        return (
            self.free_cash_flow_year1 +
            self.free_cash_flow_year2 +
            self.free_cash_flow_year3
        ) / 3
    
    @property
    def is_pattaasu_compliant(self) -> bool:
        """Check if stock meets all Pattaasu criteria."""
        return (
            self.debt_to_equity < Decimal("1.0") and
            self.promoter_pledging_pct == Decimal("0") and
            self.free_cash_flow_year1 > Decimal("0") and
            self.free_cash_flow_year2 > Decimal("0") and
            self.free_cash_flow_year3 > Decimal("0")
        )


class RiskAssessment(BaseModel):
    """Risk assessment for a stock."""
    
    model_config = ConfigDict(extra="allow")
    
    ticker: str
    overall_risk: RiskLevel = Field(default=RiskLevel.MEDIUM)
    
    # Specific risk factors
    leverage_risk: RiskLevel = Field(default=RiskLevel.LOW)
    liquidity_risk: RiskLevel = Field(default=RiskLevel.LOW)
    governance_risk: RiskLevel = Field(default=RiskLevel.LOW)
    market_risk: RiskLevel = Field(default=RiskLevel.MEDIUM)
    sector_risk: RiskLevel = Field(default=RiskLevel.MEDIUM)
    
    # Risk explanations
    risk_factors: list[str] = Field(default_factory=list)
    mitigants: list[str] = Field(default_factory=list)
    
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.MEDIUM)
    analysis_date: datetime = Field(default_factory=datetime.utcnow)


class StockAnalysis(BaseModel):
    """Complete stock analysis combining all metrics."""
    
    model_config = ConfigDict(extra="allow")
    
    # Core data
    ticker: str
    company_name: str = Field(default="")
    sector: str = Field(default="")
    industry: str = Field(default="")
    
    # Financial metrics
    metrics: FinancialMetrics | None = Field(default=None)
    
    # Pattaasu validation (if compliant)
    pattaasu: PattaasuMetrics | None = Field(default=None)
    is_pattaasu_compliant: bool = Field(default=False)
    pattaasu_score: Decimal = Field(default=Decimal("0"))
    
    # Risk assessment
    risk: RiskAssessment | None = Field(default=None)
    
    # Qualitative analysis
    moat_analysis: str = Field(default="")
    management_quality: str = Field(default="")
    competitive_position: str = Field(default="")
    
    # Investment thesis
    bull_case: str = Field(default="")
    bear_case: str = Field(default="")
    catalyst: str = Field(default="")
    
    # Metadata
    analysis_date: datetime = Field(default_factory=datetime.utcnow)
    analyst: str = Field(default="Sentinel AI")
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.MEDIUM)
    data_sources: list[str] = Field(default_factory=list)


class InvestmentRecommendation(BaseModel):
    """Final investment recommendation."""
    
    model_config = ConfigDict(extra="allow")
    
    ticker: str
    company_name: str = Field(default="")
    
    # Recommendation
    rating: InvestmentRating
    target_price: Decimal | None = Field(default=None)
    current_price: Decimal | None = Field(default=None)
    upside_potential: Decimal | None = Field(default=None)
    
    # Reasoning
    summary: str = Field(..., min_length=10)
    key_points: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    
    # Pattaasu alignment
    pattaasu_score: Decimal = Field(default=Decimal("0"))
    is_pattaasu_compliant: bool = Field(default=False)
    
    # Confidence and metadata
    confidence: ConfidenceLevel
    time_horizon: str = Field(default="12-18 months")
    recommendation_date: datetime = Field(default_factory=datetime.utcnow)
    
    @field_validator("rating", mode="before")
    @classmethod
    def normalize_rating(cls, v: Any) -> InvestmentRating:
        """Normalize rating input."""
        if isinstance(v, str):
            return InvestmentRating(v.lower().replace(" ", "_"))
        return v
