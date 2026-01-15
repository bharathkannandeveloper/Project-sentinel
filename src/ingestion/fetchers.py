"""
Market Data Fetchers

Implements data fetching from various financial APIs:
- Yahoo Finance (free)
- Alpha Vantage (API key required)
- NSE India (for Indian markets)
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

import aiohttp

logger = logging.getLogger("sentinel.ingestion.fetchers")


@dataclass
class StockQuote:
    """Real-time stock quote data."""
    ticker: str
    price: Decimal
    change: Decimal
    change_percent: Decimal
    volume: int
    open_price: Decimal
    high: Decimal
    low: Decimal
    prev_close: Decimal
    market_cap: Decimal | None = None
    pe_ratio: Decimal | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CompanyProfile:
    """Company profile and basic info."""
    ticker: str
    name: str
    sector: str = ""
    industry: str = ""
    description: str = ""
    exchange: str = ""
    country: str = ""
    website: str = ""
    employees: int | None = None
    fiscal_year_end: str = ""


@dataclass
class FinancialData:
    """Complete financial data for Pattaasu analysis."""
    ticker: str
    company_name: str = ""
    
    # Balance Sheet
    total_assets: Decimal | None = None
    total_liabilities: Decimal | None = None
    total_equity: Decimal | None = None
    total_debt: Decimal | None = None
    cash_and_equivalents: Decimal | None = None
    
    # Income Statement
    revenue: Decimal | None = None
    net_income: Decimal | None = None
    gross_profit: Decimal | None = None
    operating_income: Decimal | None = None
    
    # Cash Flow
    operating_cash_flow: Decimal | None = None
    free_cash_flow: Decimal | None = None
    capital_expenditures: Decimal | None = None
    
    # FCF for Pattaasu (3 years)
    free_cash_flow_year1: Decimal | None = None
    free_cash_flow_year2: Decimal | None = None
    free_cash_flow_year3: Decimal | None = None
    
    # Ratios
    debt_to_equity: Decimal | None = None
    pe_ratio: Decimal | None = None
    pb_ratio: Decimal | None = None
    
    # For Indian markets
    promoter_holding_pct: Decimal | None = None
    promoter_pledging_pct: Decimal | None = None
    
    # Metadata
    fiscal_year: int | None = None
    data_source: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


class DataFetcher(ABC):
    """Abstract base class for data fetchers."""
    
    @abstractmethod
    async def get_quote(self, ticker: str) -> StockQuote | None:
        """Fetch real-time quote."""
        pass
    
    @abstractmethod
    async def get_profile(self, ticker: str) -> CompanyProfile | None:
        """Fetch company profile."""
        pass
    
    @abstractmethod
    async def get_financials(self, ticker: str) -> FinancialData | None:
        """Fetch financial data."""
        pass


class YahooFinanceFetcher(DataFetcher):
    """
    Yahoo Finance data fetcher.
    
    Uses the free Yahoo Finance API (no key required).
    Note: For production, consider using yfinance library.
    """
    
    BASE_URL = "https://query1.finance.yahoo.com/v8/finance"
    
    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        self._session = session
        self._owns_session = False
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            self._owns_session = True
        return self._session
    
    async def get_quote(self, ticker: str) -> StockQuote | None:
        """Fetch real-time quote from Yahoo Finance."""
        session = await self._get_session()
        url = f"{self.BASE_URL}/chart/{ticker}"
        
        params = {
            "interval": "1d",
            "range": "1d",
        }
        
        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(f"Yahoo Finance returned {response.status} for {ticker}")
                    return None
                
                data = await response.json()
                
                result = data.get("chart", {}).get("result", [])
                if not result:
                    return None
                
                meta = result[0].get("meta", {})
                
                return StockQuote(
                    ticker=ticker,
                    price=Decimal(str(meta.get("regularMarketPrice", 0))),
                    change=Decimal(str(meta.get("regularMarketPrice", 0) - meta.get("chartPreviousClose", 0))),
                    change_percent=Decimal(str(
                        ((meta.get("regularMarketPrice", 0) / meta.get("chartPreviousClose", 1)) - 1) * 100
                    )),
                    volume=meta.get("regularMarketVolume", 0),
                    open_price=Decimal(str(meta.get("regularMarketOpen", 0))),
                    high=Decimal(str(meta.get("regularMarketDayHigh", 0))),
                    low=Decimal(str(meta.get("regularMarketDayLow", 0))),
                    prev_close=Decimal(str(meta.get("chartPreviousClose", 0))),
                )
                
        except Exception as e:
            logger.error(f"Failed to fetch quote for {ticker}: {e}")
            return None
    
    async def get_profile(self, ticker: str) -> CompanyProfile | None:
        """Fetch company profile from Yahoo Finance."""
        session = await self._get_session()
        
        # Use quoteSummary endpoint
        url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
        params = {"modules": "assetProfile,summaryProfile"}
        
        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                result = data.get("quoteSummary", {}).get("result", [])
                
                if not result:
                    return None
                
                profile = result[0].get("assetProfile", {})
                summary = result[0].get("summaryProfile", {})
                
                return CompanyProfile(
                    ticker=ticker,
                    name=summary.get("shortName", ticker),
                    sector=profile.get("sector", ""),
                    industry=profile.get("industry", ""),
                    description=profile.get("longBusinessSummary", ""),
                    exchange="",
                    country=profile.get("country", ""),
                    website=profile.get("website", ""),
                    employees=profile.get("fullTimeEmployees"),
                )
                
        except Exception as e:
            logger.error(f"Failed to fetch profile for {ticker}: {e}")
            return None
    
    async def get_financials(self, ticker: str) -> FinancialData | None:
        """Fetch financial data from Yahoo Finance."""
        session = await self._get_session()
        
        url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
        params = {
            "modules": "balanceSheetHistory,incomeStatementHistory,cashflowStatementHistory,defaultKeyStatistics,financialData"
        }
        
        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                result = data.get("quoteSummary", {}).get("result", [])
                
                if not result:
                    return None
                
                r = result[0]
                
                # Extract balance sheet
                bs_history = r.get("balanceSheetHistory", {}).get("balanceSheetStatements", [])
                latest_bs = bs_history[0] if bs_history else {}
                
                # Extract income statement
                is_history = r.get("incomeStatementHistory", {}).get("incomeStatementHistory", [])
                latest_is = is_history[0] if is_history else {}
                
                # Extract cash flow
                cf_history = r.get("cashflowStatementHistory", {}).get("cashflowStatements", [])
                
                # Get FCF for last 3 years
                fcf_years = []
                for cf in cf_history[:3]:
                    ocf = cf.get("operatingCashflow", {}).get("raw", 0)
                    capex = cf.get("capitalExpenditures", {}).get("raw", 0)
                    fcf_years.append(Decimal(str(ocf - abs(capex))))
                
                while len(fcf_years) < 3:
                    fcf_years.append(None)
                
                # Key statistics
                key_stats = r.get("defaultKeyStatistics", {})
                fin_data = r.get("financialData", {})
                
                # Calculate D/E
                total_debt = Decimal(str(fin_data.get("totalDebt", {}).get("raw", 0)))
                total_equity = Decimal(str(latest_bs.get("totalStockholderEquity", {}).get("raw", 1)))
                d_e = total_debt / total_equity if total_equity > 0 else Decimal("999")
                
                return FinancialData(
                    ticker=ticker,
                    total_assets=Decimal(str(latest_bs.get("totalAssets", {}).get("raw", 0))),
                    total_liabilities=Decimal(str(latest_bs.get("totalLiab", {}).get("raw", 0))),
                    total_equity=total_equity,
                    total_debt=total_debt,
                    cash_and_equivalents=Decimal(str(latest_bs.get("cash", {}).get("raw", 0))),
                    revenue=Decimal(str(latest_is.get("totalRevenue", {}).get("raw", 0))),
                    net_income=Decimal(str(latest_is.get("netIncome", {}).get("raw", 0))),
                    operating_cash_flow=Decimal(str(cf_history[0].get("operatingCashflow", {}).get("raw", 0))) if cf_history else None,
                    free_cash_flow=fcf_years[0],
                    free_cash_flow_year1=fcf_years[0],
                    free_cash_flow_year2=fcf_years[1],
                    free_cash_flow_year3=fcf_years[2],
                    debt_to_equity=d_e,
                    pe_ratio=Decimal(str(key_stats.get("trailingPE", {}).get("raw", 0))) if key_stats.get("trailingPE") else None,
                    data_source="yahoo_finance",
                )
                
        except Exception as e:
            logger.error(f"Failed to fetch financials for {ticker}: {e}")
            return None
    
    async def close(self) -> None:
        """Close the session if we own it."""
        if self._owns_session and self._session:
            await self._session.close()


class AlphaVantageFetcher(DataFetcher):
    """
    Alpha Vantage data fetcher.
    
    Requires API key from https://www.alphavantage.co/
    Free tier: 5 API calls per minute
    """
    
    BASE_URL = "https://www.alphavantage.co/query"
    
    def __init__(self, api_key: str, session: aiohttp.ClientSession | None = None) -> None:
        self.api_key = api_key
        self._session = session
        self._owns_session = False
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session
    
    async def _request(self, function: str, symbol: str, **params) -> dict[str, Any] | None:
        """Make API request."""
        session = await self._get_session()
        
        request_params = {
            "function": function,
            "symbol": symbol,
            "apikey": self.api_key,
            **params,
        }
        
        try:
            async with session.get(self.BASE_URL, params=request_params) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                
                # Check for rate limit
                if "Note" in data or "Information" in data:
                    logger.warning(f"Alpha Vantage rate limited: {data}")
                    return None
                
                return data
                
        except Exception as e:
            logger.error(f"Alpha Vantage request failed: {e}")
            return None
    
    async def get_quote(self, ticker: str) -> StockQuote | None:
        """Get global quote from Alpha Vantage."""
        data = await self._request("GLOBAL_QUOTE", ticker)
        
        if not data or "Global Quote" not in data:
            return None
        
        quote = data["Global Quote"]
        
        return StockQuote(
            ticker=ticker,
            price=Decimal(quote.get("05. price", "0")),
            change=Decimal(quote.get("09. change", "0")),
            change_percent=Decimal(quote.get("10. change percent", "0%").rstrip("%")),
            volume=int(quote.get("06. volume", 0)),
            open_price=Decimal(quote.get("02. open", "0")),
            high=Decimal(quote.get("03. high", "0")),
            low=Decimal(quote.get("04. low", "0")),
            prev_close=Decimal(quote.get("08. previous close", "0")),
        )
    
    async def get_profile(self, ticker: str) -> CompanyProfile | None:
        """Get company overview from Alpha Vantage."""
        data = await self._request("OVERVIEW", ticker)
        
        if not data or "Symbol" not in data:
            return None
        
        return CompanyProfile(
            ticker=ticker,
            name=data.get("Name", ticker),
            sector=data.get("Sector", ""),
            industry=data.get("Industry", ""),
            description=data.get("Description", ""),
            exchange=data.get("Exchange", ""),
            country=data.get("Country", ""),
            employees=int(data.get("FullTimeEmployees", 0)) if data.get("FullTimeEmployees") else None,
            fiscal_year_end=data.get("FiscalYearEnd", ""),
        )
    
    async def get_financials(self, ticker: str) -> FinancialData | None:
        """Get financial data from Alpha Vantage."""
        # Fetch multiple data points
        overview = await self._request("OVERVIEW", ticker)
        balance_sheet = await self._request("BALANCE_SHEET", ticker)
        cash_flow = await self._request("CASH_FLOW", ticker)
        
        if not overview:
            return None
        
        # Parse balance sheet
        bs_annual = (balance_sheet or {}).get("annualReports", [])
        latest_bs = bs_annual[0] if bs_annual else {}
        
        # Parse cash flow for 3 years
        cf_annual = (cash_flow or {}).get("annualReports", [])
        fcf_years = []
        for cf in cf_annual[:3]:
            ocf = Decimal(cf.get("operatingCashflow", 0) or 0)
            capex = Decimal(cf.get("capitalExpenditures", 0) or 0)
            fcf_years.append(ocf - abs(capex))
        
        while len(fcf_years) < 3:
            fcf_years.append(None)
        
        return FinancialData(
            ticker=ticker,
            company_name=overview.get("Name", ""),
            total_assets=Decimal(latest_bs.get("totalAssets", 0) or 0),
            total_equity=Decimal(latest_bs.get("totalShareholderEquity", 0) or 0),
            total_debt=Decimal(latest_bs.get("shortLongTermDebt", 0) or 0) + Decimal(latest_bs.get("longTermDebt", 0) or 0),
            revenue=Decimal(overview.get("RevenueTTM", 0) or 0),
            net_income=Decimal(overview.get("GrossProfitTTM", 0) or 0),
            free_cash_flow_year1=fcf_years[0],
            free_cash_flow_year2=fcf_years[1],
            free_cash_flow_year3=fcf_years[2],
            pe_ratio=Decimal(overview.get("PERatio", 0) or 0) if overview.get("PERatio") else None,
            data_source="alpha_vantage",
        )
    
    async def close(self) -> None:
        if self._owns_session and self._session:
            await self._session.close()


# Factory function
async def create_fetcher(source: str = "yahoo", api_key: str | None = None) -> DataFetcher:
    """Create a data fetcher instance."""
    if source == "yahoo":
        return YahooFinanceFetcher()
    elif source == "alphavantage" and api_key:
        return AlphaVantageFetcher(api_key)
    else:
        return YahooFinanceFetcher()
