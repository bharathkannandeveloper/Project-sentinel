"""
SEC EDGAR Scraper

Fetches company filings (10-K, 10-Q, 8-K) from SEC EDGAR.
Extracts MD&A, Risk Factors, and Financial Statements.
"""
import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from xml.etree import ElementTree

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger("sentinel.ingestion.edgar")


# SEC EDGAR API endpoints
EDGAR_BASE = "https://data.sec.gov"
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"


@dataclass
class SECFiling:
    """Represents a SEC filing."""
    ticker: str
    cik: str
    form_type: str  # 10-K, 10-Q, 8-K
    filed_date: datetime
    period_of_report: datetime | None
    accession_number: str
    filing_url: str
    
    # Extracted content
    risk_factors: str = ""
    mda_text: str = ""  # Management Discussion & Analysis
    
    # Parsed data
    extracted_entities: list[str] = field(default_factory=list)


@dataclass
class CompanyFilings:
    """Collection of filings for a company."""
    ticker: str
    cik: str
    company_name: str
    filings: list[SECFiling] = field(default_factory=list)


class EDGARScraper:
    """
    SEC EDGAR filing scraper.
    
    Fetches 10-K, 10-Q, 8-K filings and extracts key sections
    for LLM analysis and knowledge graph population.
    """
    
    # SEC requires User-Agent for API access
    HEADERS = {
        "User-Agent": "ProjectSentinel/1.0 (contact@example.com)",
        "Accept": "application/json",
    }
    
    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        self._session = session
        self._owns_session = False
        self._cik_cache: dict[str, str] = {}
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self.HEADERS)
            self._owns_session = True
        return self._session
    
    async def get_cik(self, ticker: str) -> str | None:
        """
        Get CIK number for a ticker.
        
        SEC uses CIK (Central Index Key) to identify companies.
        """
        if ticker in self._cik_cache:
            return self._cik_cache[ticker]
        
        session = await self._get_session()
        url = f"{EDGAR_BASE}/submissions/CIK{ticker}.json"
        
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    cik = data.get("cik", "")
                    if cik:
                        # Pad to 10 digits
                        cik_padded = str(cik).zfill(10)
                        self._cik_cache[ticker] = cik_padded
                        return cik_padded
        except Exception as e:
            logger.debug(f"CIK lookup failed for {ticker}: {e}")
        
        # Try company tickers API
        try:
            tickers_url = f"{EDGAR_BASE}/files/company_tickers.json"
            async with session.get(tickers_url) as response:
                if response.status == 200:
                    data = await response.json()
                    for entry in data.values():
                        if entry.get("ticker", "").upper() == ticker.upper():
                            cik = str(entry.get("cik_str", "")).zfill(10)
                            self._cik_cache[ticker] = cik
                            return cik
        except Exception as e:
            logger.error(f"Failed to lookup CIK: {e}")
        
        return None
    
    async def get_filings(
        self,
        ticker: str,
        form_types: list[str] = ["10-K", "10-Q"],
        limit: int = 10,
    ) -> CompanyFilings | None:
        """
        Get recent filings for a company.
        
        Args:
            ticker: Stock ticker symbol
            form_types: Types of forms to fetch
            limit: Maximum number of filings
            
        Returns:
            CompanyFilings with list of SEC filings
        """
        cik = await self.get_cik(ticker)
        if not cik:
            logger.warning(f"Could not find CIK for {ticker}")
            return None
        
        session = await self._get_session()
        url = f"{EDGAR_BASE}/submissions/CIK{cik}.json"
        
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                company_name = data.get("name", "")
                
                filings_data = data.get("filings", {}).get("recent", {})
                
                filings = []
                form_list = filings_data.get("form", [])
                dates = filings_data.get("filingDate", [])
                accessions = filings_data.get("accessionNumber", [])
                periods = filings_data.get("reportDate", [])
                primary_docs = filings_data.get("primaryDocument", [])
                
                for i, form in enumerate(form_list):
                    if len(filings) >= limit:
                        break
                    
                    if form not in form_types:
                        continue
                    
                    accession = accessions[i].replace("-", "")
                    filing_url = f"{EDGAR_BASE}/Archives/edgar/data/{cik}/{accession}/{primary_docs[i]}"
                    
                    filed_date = datetime.strptime(dates[i], "%Y-%m-%d")
                    period_date = datetime.strptime(periods[i], "%Y-%m-%d") if periods[i] else None
                    
                    filings.append(SECFiling(
                        ticker=ticker,
                        cik=cik,
                        form_type=form,
                        filed_date=filed_date,
                        period_of_report=period_date,
                        accession_number=accessions[i],
                        filing_url=filing_url,
                    ))
                
                return CompanyFilings(
                    ticker=ticker,
                    cik=cik,
                    company_name=company_name,
                    filings=filings,
                )
                
        except Exception as e:
            logger.error(f"Failed to fetch filings for {ticker}: {e}")
            return None
    
    async def extract_filing_content(
        self,
        filing: SECFiling,
    ) -> SECFiling:
        """
        Extract key sections from a filing.
        
        Extracts:
        - Risk Factors (Item 1A)
        - Management Discussion & Analysis (Item 7)
        
        Args:
            filing: The SEC filing to extract content from
            
        Returns:
            Updated filing with extracted content
        """
        session = await self._get_session()
        
        try:
            async with session.get(filing.filing_url) as response:
                if response.status != 200:
                    return filing
                
                html = await response.text()
                soup = BeautifulSoup(html, "lxml")
                
                # Remove scripts and styles
                for script in soup(["script", "style"]):
                    script.decompose()
                
                text = soup.get_text(separator="\n")
                
                # Extract Risk Factors section
                filing.risk_factors = self._extract_section(
                    text,
                    start_pattern=r"Item\s*1A\.?\s*Risk\s*Factors",
                    end_pattern=r"Item\s*1B\.?\s*|Item\s*2\.?\s*",
                )
                
                # Extract MD&A section
                filing.mda_text = self._extract_section(
                    text,
                    start_pattern=r"Item\s*7\.?\s*Management['']s\s*Discussion",
                    end_pattern=r"Item\s*7A\.?\s*|Item\s*8\.?\s*",
                )
                
        except Exception as e:
            logger.error(f"Failed to extract content: {e}")
        
        return filing
    
    def _extract_section(
        self,
        text: str,
        start_pattern: str,
        end_pattern: str,
        max_length: int = 50000,
    ) -> str:
        """Extract a section between two patterns."""
        try:
            start_match = re.search(start_pattern, text, re.IGNORECASE)
            if not start_match:
                return ""
            
            start_pos = start_match.start()
            remaining = text[start_pos:start_pos + max_length]
            
            end_match = re.search(end_pattern, remaining, re.IGNORECASE)
            if end_match:
                return remaining[:end_match.start()].strip()
            
            return remaining[:max_length].strip()
            
        except Exception:
            return ""
    
    async def get_latest_10k(self, ticker: str) -> SECFiling | None:
        """
        Get the latest 10-K filing with extracted content.
        
        Convenience method for Pattaasu analysis.
        """
        filings = await self.get_filings(ticker, form_types=["10-K"], limit=1)
        
        if not filings or not filings.filings:
            return None
        
        return await self.extract_filing_content(filings.filings[0])
    
    async def close(self) -> None:
        """Close the session."""
        if self._owns_session and self._session:
            await self._session.close()


# Example usage
async def fetch_company_sec_data(ticker: str) -> dict[str, Any]:
    """Fetch SEC data for a company."""
    scraper = EDGARScraper()
    
    try:
        filings = await scraper.get_filings(ticker, limit=5)
        
        if not filings:
            return {"error": f"No filings found for {ticker}"}
        
        # Get latest 10-K with content
        latest_10k = None
        for f in filings.filings:
            if f.form_type == "10-K":
                latest_10k = await scraper.extract_filing_content(f)
                break
        
        return {
            "ticker": ticker,
            "cik": filings.cik,
            "company_name": filings.company_name,
            "filings_count": len(filings.filings),
            "latest_10k": {
                "filed_date": latest_10k.filed_date.isoformat() if latest_10k else None,
                "risk_factors_length": len(latest_10k.risk_factors) if latest_10k else 0,
                "mda_length": len(latest_10k.mda_text) if latest_10k else 0,
            } if latest_10k else None,
        }
        
    finally:
        await scraper.close()
