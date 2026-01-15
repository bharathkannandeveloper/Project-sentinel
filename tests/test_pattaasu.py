"""
Tests for Pattaasu Investment Models and Analyzer

Tests the Pydantic validation models and analysis engine.
"""
import pytest
from decimal import Decimal

from src.analysis.models import (
    PattaasuMetrics,
    FinancialMetrics,
    RiskAssessment,
    InvestmentRating,
    MoatRating,
    RiskLevel,
)
from src.analysis.pattaasu import PattaasuAnalyzer


class TestPattaasuMetrics:
    """Tests for PattaasuMetrics validation."""
    
    def test_valid_pattaasu_stock(self):
        """Test a stock that meets all Pattaasu criteria."""
        metrics = PattaasuMetrics(
            ticker="PERFECT",
            debt_to_equity=Decimal("0.1"),
            promoter_pledging_pct=Decimal("0"),
            free_cash_flow_year1=Decimal("100000000"),
            free_cash_flow_year2=Decimal("90000000"),
            free_cash_flow_year3=Decimal("80000000"),
        )
        
        assert metrics.is_pattaasu_compliant
        assert metrics.pattaasu_score >= Decimal("60")
    
    def test_high_debt_fails(self):
        """Test that high D/E ratio fails validation."""
        with pytest.raises(ValueError, match="exceeds Pattaasu limit"):
            PattaasuMetrics(
                ticker="DEBT",
                debt_to_equity=Decimal("1.5"),  # Over 1.0
                promoter_pledging_pct=Decimal("0"),
                free_cash_flow_year1=Decimal("100"),
                free_cash_flow_year2=Decimal("100"),
                free_cash_flow_year3=Decimal("100"),
            )
    
    def test_pledging_fails(self):
        """Test that any promoter pledging fails validation."""
        with pytest.raises(ValueError, match="Promoter pledging detected"):
            PattaasuMetrics(
                ticker="PLEDGE",
                debt_to_equity=Decimal("0.2"),
                promoter_pledging_pct=Decimal("5"),  # Must be 0
                free_cash_flow_year1=Decimal("100"),
                free_cash_flow_year2=Decimal("100"),
                free_cash_flow_year3=Decimal("100"),
            )
    
    def test_negative_fcf_fails(self):
        """Test that negative FCF in any year fails."""
        with pytest.raises(ValueError, match="Negative FCF"):
            PattaasuMetrics(
                ticker="BURN",
                debt_to_equity=Decimal("0.2"),
                promoter_pledging_pct=Decimal("0"),
                free_cash_flow_year1=Decimal("-100"),  # Negative
                free_cash_flow_year2=Decimal("100"),
                free_cash_flow_year3=Decimal("100"),
            )
    
    def test_score_calculation(self):
        """Test Pattaasu score calculation."""
        # Zero debt should get max debt points
        metrics = PattaasuMetrics(
            ticker="NODBT",
            debt_to_equity=Decimal("0"),
            promoter_pledging_pct=Decimal("0"),
            free_cash_flow_year1=Decimal("100"),
            free_cash_flow_year2=Decimal("100"),
            free_cash_flow_year3=Decimal("100"),
            moat_rating=MoatRating.WIDE,
        )
        
        # Should get: 30 (zero debt) + 25 (no pledge) + 25 (FCF) + 20 (wide moat) = 100
        assert metrics.pattaasu_score == Decimal("100")


class TestPattaasuAnalyzer:
    """Tests for PattaasuAnalyzer."""
    
    @pytest.fixture
    def analyzer(self):
        return PattaasuAnalyzer()
    
    def test_quick_validate_pass(self, analyzer):
        """Test quick validation for compliant stock."""
        is_valid, errors = analyzer.quick_validate({
            "debt_to_equity": 0.3,
            "promoter_pledging_pct": 0,
            "free_cash_flow_year1": 100,
            "free_cash_flow_year2": 100,
            "free_cash_flow_year3": 100,
        })
        
        assert is_valid
        assert len(errors) == 0
    
    def test_quick_validate_fail(self, analyzer):
        """Test quick validation for non-compliant stock."""
        is_valid, errors = analyzer.quick_validate({
            "debt_to_equity": 1.5,  # Too high
            "promoter_pledging_pct": 10,  # Must be zero
            "free_cash_flow_year1": -100,  # Negative
            "free_cash_flow_year2": 100,
            "free_cash_flow_year3": 100,
        })
        
        assert not is_valid
        assert len(errors) == 3  # Three violations
    
    def test_risk_assessment(self, analyzer):
        """Test risk assessment calculation."""
        metrics = FinancialMetrics(
            ticker="TEST",
            total_debt=Decimal("100"),
            total_equity=Decimal("500"),
            cash_and_equivalents=Decimal("50"),
            total_liabilities=Decimal("200"),
        )
        
        risk = analyzer.calculate_risk_assessment(metrics)
        
        assert risk.ticker == "TEST"
        assert risk.leverage_risk == RiskLevel.LOW  # D/E = 0.2
        assert "Low leverage" in "\n".join(risk.mitigants)


class TestFinancialMetrics:
    """Tests for FinancialMetrics model."""
    
    def test_debt_to_equity_property(self):
        """Test D/E ratio calculation."""
        metrics = FinancialMetrics(
            ticker="TEST",
            total_debt=Decimal("200"),
            total_equity=Decimal("400"),
        )
        
        assert metrics.debt_to_equity == Decimal("0.5")
    
    def test_zero_equity_handling(self):
        """Test D/E when equity is zero."""
        metrics = FinancialMetrics(
            ticker="TEST",
            total_debt=Decimal("100"),
            total_equity=Decimal("0"),
        )
        
        assert metrics.debt_to_equity == Decimal("999.99")
