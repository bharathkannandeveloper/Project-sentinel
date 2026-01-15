"""
NSE India Data Fetcher

Fetches stock data from NSE India (National Stock Exchange).
Supports quotes, company info, and historical data.
"""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx

logger = logging.getLogger("sentinel.ingestion.nse")


# NSE India endpoints
NSE_BASE_URL = "https://www.nseindia.com"
NSE_API_URL = "https://www.nseindia.com/api"


@dataclass
class NSEQuote:
    """NSE stock quote data."""
    symbol: str
    name: str
    last_price: Decimal
    change: Decimal
    change_percent: Decimal
    open_price: Decimal
    high: Decimal
    low: Decimal
    prev_close: Decimal
    volume: int
    timestamp: datetime


@dataclass
class NSEFundamentals:
    """NSE fundamental data."""
    symbol: str
    pe_ratio: Decimal | None
    pb_ratio: Decimal | None
    eps: Decimal | None
    book_value: Decimal | None
    dividend_yield: Decimal | None
    face_value: Decimal | None
    market_cap: Decimal | None
    industry: str
    sector: str


@dataclass
class NSEFinancials:
    """Full financials from annual reports."""
    symbol: str
    revenue: Decimal | None
    net_income: Decimal | None
    total_debt: Decimal | None
    total_equity: Decimal | None
    cash_and_equivalents: Decimal | None
    free_cash_flow: Decimal | None
    debt_to_equity: Decimal | None
    roe: Decimal | None
    roce: Decimal | None


class NSEFetcher:
    """
    Fetches data from NSE India.
    
    NSE requires specific headers and cookies to access the API.
    We need to first visit the main page to get cookies.
    """
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.nseindia.com/",
    }
    
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._cookies_initialized = False
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with cookies."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=self.HEADERS,
                timeout=httpx.Timeout(30.0),
                follow_redirects=True,
            )
        
        # Initialize cookies by visiting main page
        if not self._cookies_initialized:
            try:
                await self._client.get(NSE_BASE_URL)
                self._cookies_initialized = True
            except Exception as e:
                logger.warning(f"Failed to initialize NSE cookies: {e}")
        
        return self._client
    
    async def get_quote(self, symbol: str) -> NSEQuote | None:
        """
        Get real-time quote for an NSE symbol.
        
        Args:
            symbol: NSE stock symbol (e.g., "INFY", "TCS", "RELIANCE")
            
        Returns:
            NSEQuote with current price and stats
        """
        symbol = symbol.upper()
        client = await self._get_client()
        
        try:
            url = f"{NSE_API_URL}/quote-equity?symbol={symbol}"
            response = await client.get(url)
            
            if response.status_code != 200:
                logger.warning(f"NSE quote failed for {symbol}: {response.status_code}")
                return None
            
            data = response.json()
            price_info = data.get("priceInfo", {})
            
            return NSEQuote(
                symbol=symbol,
                name=data.get("info", {}).get("companyName", symbol),
                last_price=Decimal(str(price_info.get("lastPrice", 0))),
                change=Decimal(str(price_info.get("change", 0))),
                change_percent=Decimal(str(price_info.get("pChange", 0))),
                open_price=Decimal(str(price_info.get("open", 0))),
                high=Decimal(str(price_info.get("intraDayHighLow", {}).get("max", 0))),
                low=Decimal(str(price_info.get("intraDayHighLow", {}).get("min", 0))),
                prev_close=Decimal(str(price_info.get("previousClose", 0))),
                volume=int(data.get("securityWiseDP", {}).get("quantityTraded", 0) or 0),
                timestamp=datetime.now(),
            )
            
        except Exception as e:
            logger.error(f"Error fetching NSE quote for {symbol}: {e}")
            return None
    
    async def get_fundamentals(self, symbol: str) -> NSEFundamentals | None:
        """
        Get fundamental data for an NSE stock.
        
        Args:
            symbol: NSE stock symbol
            
        Returns:
            NSEFundamentals with ratios and metrics
        """
        symbol = symbol.upper()
        client = await self._get_client()
        
        try:
            url = f"{NSE_API_URL}/quote-equity?symbol={symbol}"
            response = await client.get(url)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            info = data.get("info", {})
            metadata = data.get("metadata", {})
            
            # Get PE from trade info
            pe = None
            if "priceInfo" in data:
                pe_str = data.get("priceInfo", {}).get("perChange365d")
            
            return NSEFundamentals(
                symbol=symbol,
                pe_ratio=self._safe_decimal(metadata.get("pdSymbolPe")),
                pb_ratio=self._safe_decimal(metadata.get("pdSectorPe")),  # Sector PE as proxy
                eps=None,  # Need to calculate from financials
                book_value=None,
                dividend_yield=None,
                face_value=self._safe_decimal(info.get("faceValue")),
                market_cap=None,
                industry=info.get("industry", ""),
                sector=info.get("sector", ""),
            )
            
        except Exception as e:
            logger.error(f"Error fetching NSE fundamentals for {symbol}: {e}")
            return None
    
    async def get_stock_info(self, symbol: str) -> dict[str, Any] | None:
        """
        Get detailed stock information.
        
        Returns all available data from NSE for analysis.
        """
        symbol = symbol.upper()
        client = await self._get_client()
        
        try:
            url = f"{NSE_API_URL}/quote-equity?symbol={symbol}"
            response = await client.get(url)
            
            if response.status_code != 200:
                return None
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error fetching NSE info for {symbol}: {e}")
            return None
    
    async def search_stocks(self, query: str) -> list[dict[str, str]]:
        """
        Search for stocks by name or symbol.
        
        Args:
            query: Search term
            
        Returns:
            List of matching stocks with symbol and name
        """
        client = await self._get_client()
        
        try:
            url = f"{NSE_API_URL}/search/autocomplete?q={query}"
            response = await client.get(url)
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            results = []
            
            for item in data.get("symbols", []):
                results.append({
                    "symbol": item.get("symbol", ""),
                    "name": item.get("symbol_info", ""),
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching NSE: {e}")
            return []
    
    async def get_all_indices(self) -> list[dict[str, Any]]:
        """Get all NSE indices."""
        client = await self._get_client()
        
        try:
            url = f"{NSE_API_URL}/allIndices"
            response = await client.get(url)
            
            if response.status_code != 200:
                return []
            
            return response.json().get("data", [])
            
        except Exception as e:
            logger.error(f"Error fetching indices: {e}")
            return []
    
    def _safe_decimal(self, value: Any) -> Decimal | None:
        """Safely convert to Decimal."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return None
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Top NSE stocks for quick reference
NIFTY_50_STOCKS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "SBIN", "BHARTIARTL", "KOTAKBANK", "ITC",
    "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "BAJFINANCE",
    "TITAN", "SUNPHARMA", "ULTRACEMCO", "NESTLEIND", "WIPRO",
    "HCLTECH", "POWERGRID", "NTPC", "ONGC", "JSWSTEEL",
    "TATASTEEL", "M&M", "ADANIPORTS", "COALINDIA", "GRASIM",
]


# Convenience function
async def fetch_nse_stock(symbol: str) -> dict[str, Any]:
    """
    Fetch comprehensive data for an NSE stock.
    
    Returns quote, fundamentals, and raw data combined.
    """
    fetcher = NSEFetcher()
    
    try:
        quote = await fetcher.get_quote(symbol)
        fundamentals = await fetcher.get_fundamentals(symbol)
        raw_data = await fetcher.get_stock_info(symbol)
        
        return {
            "symbol": symbol,
            "success": quote is not None,
            "quote": {
                "price": float(quote.last_price) if quote else None,
                "change": float(quote.change) if quote else None,
                "change_percent": float(quote.change_percent) if quote else None,
                "volume": quote.volume if quote else None,
                "name": quote.name if quote else symbol,
            } if quote else None,
            "fundamentals": {
                "pe_ratio": float(fundamentals.pe_ratio) if fundamentals and fundamentals.pe_ratio else None,
                "sector": fundamentals.sector if fundamentals else "",
                "industry": fundamentals.industry if fundamentals else "",
            } if fundamentals else None,
            "raw_data": raw_data,
        }
        
    finally:
        await fetcher.close()
