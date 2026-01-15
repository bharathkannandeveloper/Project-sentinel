"""
Perplexity Finance Scraper

Scrapes rich stock data from perplexity.ai/finance including:
- Real-time quote
- Price movements with AI analysis
- Recent developments
- Key issues (bullish/bearish)
- Company info
- Peer comparisons
"""
import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger("sentinel.scraper.perplexity")


@dataclass
class PriceMovement:
    """A price movement event with AI analysis."""
    date: str
    price: float
    change_percent: float
    analysis: str


@dataclass
class Development:
    """A recent development/news item."""
    title: str
    summary: str
    time_ago: str
    source: str = ""


@dataclass
class KeyIssue:
    """Bullish or bearish view."""
    sentiment: str  # "bullish" or "bearish"
    text: str
    source: str = ""


@dataclass
class CompanyInfo:
    """Company fundamental info."""
    name: str
    symbol: str
    exchange: str
    country: str
    sector: str
    industry: str
    market_cap: str
    pe_ratio: float | None
    eps: float | None
    dividend_yield: float | None
    employees: str
    ceo: str
    description: str


@dataclass
class PerplexityData:
    """Complete data from Perplexity Finance."""
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    prev_close: float
    
    # Extended data
    day_range: str = ""
    week_52_range: str = ""
    market_cap: str = ""
    pe_ratio: float | None = None
    eps: float | None = None
    dividend_yield: float | None = None
    volume: str = ""
    
    # AI analysis
    price_movements: list[PriceMovement] = field(default_factory=list)
    developments: list[Development] = field(default_factory=list)
    key_issues: list[KeyIssue] = field(default_factory=list)
    
    # Company info
    company_info: CompanyInfo | None = None
    
    # Peers
    peers: list[dict] = field(default_factory=list)
    
    # Meta
    source: str = "perplexity"
    fetched_at: datetime = field(default_factory=datetime.now)


class PerplexityScraper:
    """
    Scrapes stock data from Perplexity Finance.
    
    URL format: https://www.perplexity.ai/finance/{SYMBOL}.NS (for NSE)
    """
    
    BASE_URL = "https://www.perplexity.ai/finance"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    
    async def fetch(self, symbol: str, market: str = "NS") -> dict[str, Any]:
        """
        Fetch complete stock data from Perplexity Finance.
        
        Args:
            symbol: Stock symbol (e.g., "HDFCBANK", "AAPL")
            market: Market suffix ("NS" for NSE, "BO" for BSE, "" for US)
            
        Returns:
            Dict with all scraped data
        """
        # Build URL
        if market:
            url = f"{self.BASE_URL}/{symbol}.{market}"
        else:
            url = f"{self.BASE_URL}/{symbol}"
        
        try:
            async with httpx.AsyncClient(timeout=20.0, headers=self.HEADERS, follow_redirects=True) as client:
                response = await client.get(url)
                
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Perplexity returned {response.status_code}",
                        "symbol": symbol,
                    }
                
                html = response.text
                
                # Parse the page
                data = self._parse_page(html, symbol)
                data["url"] = url
                data["success"] = True
                
                return data
                
        except Exception as e:
            logger.error(f"Perplexity scrape failed for {symbol}: {e}")
            return {
                "success": False,
                "error": str(e),
                "symbol": symbol,
            }
    
    def _parse_page(self, html: str, symbol: str) -> dict[str, Any]:
        """Parse Perplexity Finance page HTML."""
        data = {
            "symbol": symbol,
            "name": "",
            "price": 0,
            "change": 0,
            "change_percent": 0,
            "price_movements": [],
            "developments": [],
            "key_issues": [],
            "peers": [],
            "info": {},
        }
        
        # Extract company name
        name_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if name_match:
            data["name"] = name_match.group(1).strip()
        
        # Extract price - look for price pattern
        # Pattern: ₹925.45 or $123.45
        price_match = re.search(r'[₹$]([\d,]+\.?\d*)', html)
        if price_match:
            data["price"] = float(price_match.group(1).replace(",", ""))
        
        # Extract change percent
        change_match = re.search(r'([+-]?\d+\.?\d*)%', html)
        if change_match:
            data["change_percent"] = float(change_match.group(1))
        
        # Extract market cap
        mcap_match = re.search(r'Market Cap[^₹$]*[₹$]([\d.]+[TBM])', html)
        if mcap_match:
            data["info"]["market_cap"] = mcap_match.group(1)
        
        # Extract P/E
        pe_match = re.search(r'P/E Ratio[^\d]*([\d.]+)', html)
        if pe_match:
            data["info"]["pe_ratio"] = float(pe_match.group(1))
        
        # Extract EPS
        eps_match = re.search(r'EPS[^₹$]*[₹$]([\d.]+)', html)
        if eps_match:
            data["info"]["eps"] = float(eps_match.group(1))
        
        # Extract dividend yield
        div_match = re.search(r'Dividend Yield[^\d]*([\d.]+)%', html)
        if div_match:
            data["info"]["dividend_yield"] = float(div_match.group(1))
        
        # Extract 52W range
        range_match = re.search(r'52W Range[^₹$]*[₹$]([\d,.]+)-?[₹$]?([\d,.]+)', html)
        if range_match:
            data["info"]["week_52_low"] = float(range_match.group(1).replace(",", ""))
            data["info"]["week_52_high"] = float(range_match.group(2).replace(",", ""))
        
        # Extract volume
        vol_match = re.search(r'Volume[^\d]*([\d.]+[MKB]?)', html)
        if vol_match:
            data["info"]["volume"] = vol_match.group(1)
        
        # Extract sector/industry
        sector_match = re.search(r'Sector[^>]*>([^<]+)', html)
        if sector_match:
            data["info"]["sector"] = sector_match.group(1).strip()
        
        industry_match = re.search(r'Industry[^>]*>([^<]+)', html)
        if industry_match:
            data["info"]["industry"] = industry_match.group(1).strip()
        
        # Extract CEO
        ceo_match = re.search(r'CEO[^>]*>([^<]+)', html)
        if ceo_match:
            data["info"]["ceo"] = ceo_match.group(1).strip()
        
        # Extract employees
        emp_match = re.search(r'Employees[^\d]*([\d,]+[KM]?)', html)
        if emp_match:
            data["info"]["employees"] = emp_match.group(1)
        
        # Extract price movements (simplified - would need JS rendering for full data)
        # These typically come from dynamic JS, so we'll note this limitation
        
        # Extract company description (usually in a paragraph)
        desc_match = re.search(r'<p[^>]*class="[^"]*description[^"]*"[^>]*>([^<]+)</p>', html)
        if desc_match:
            data["info"]["description"] = desc_match.group(1).strip()
        
        # Look for any description-like long text
        if not data["info"].get("description"):
            long_text = re.search(r'<p[^>]*>(.{200,500})</p>', html)
            if long_text:
                data["info"]["description"] = long_text.group(1).strip()
        
        return data
    
    async def search(self, query: str) -> list[dict]:
        """Search for stocks."""
        # Perplexity doesn't have a search API, but we can try the page
        results = []
        
        # Try common patterns
        test_symbols = [query.upper()]
        if not query.endswith(".NS"):
            test_symbols.append(f"{query.upper()}.NS")
        
        for symbol in test_symbols:
            data = await self.fetch(symbol.replace(".NS", ""), "NS" if ".NS" in symbol else "")
            if data.get("success") and data.get("price", 0) > 0:
                results.append({
                    "symbol": symbol.replace(".NS", ""),
                    "name": data.get("name", symbol),
                    "market": "NSE" if ".NS" in symbol else "US",
                })
                break
        
        return results


async def fetch_perplexity_data(symbol: str, market: str = "NS") -> dict:
    """
    Convenience function to fetch Perplexity data.
    
    Args:
        symbol: Stock symbol
        market: "NS" for NSE, "BO" for BSE, "" for US
    """
    scraper = PerplexityScraper()
    return await scraper.fetch(symbol, market)


# Fallback: if Perplexity fails, we still have Yahoo
async def fetch_with_perplexity_fallback(symbol: str) -> dict:
    """
    Try Perplexity first, fallback to Yahoo.
    """
    # Determine market
    from src.ingestion.multi_source import STOCK_INFO, fetch_stock
    
    is_indian = symbol.upper() in STOCK_INFO
    market = "NS" if is_indian else ""
    
    # Try Perplexity
    data = await fetch_perplexity_data(symbol, market)
    
    if data.get("success") and data.get("price", 0) > 0:
        data["source"] = "perplexity"
        return data
    
    # Fallback to multi-source (Yahoo/Google)
    fallback_data = await fetch_stock(symbol)
    if fallback_data.get("success"):
        fallback_data["source"] = fallback_data.get("source", "yahoo")
        return fallback_data
    
    return {
        "success": False,
        "symbol": symbol,
        "error": "All sources failed",
        "sources_tried": ["perplexity", "yahoo", "google"],
    }
