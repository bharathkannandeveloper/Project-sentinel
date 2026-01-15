"""
Indian Stock Data via Yahoo Finance

Uses Yahoo Finance with .NS (NSE) and .BO (BSE) suffixes for Indian stocks.
More reliable than direct NSE API access.
"""
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx

logger = logging.getLogger("sentinel.ingestion.indian")


# Comprehensive Indian stock database with names and sectors
INDIAN_STOCKS = {
    # NIFTY 50 Stocks
    "RELIANCE": {"name": "Reliance Industries", "sector": "Oil & Gas", "market_cap": "Large"},
    "TCS": {"name": "Tata Consultancy Services", "sector": "IT", "market_cap": "Large"},
    "HDFCBANK": {"name": "HDFC Bank", "sector": "Banking", "market_cap": "Large"},
    "INFY": {"name": "Infosys", "sector": "IT", "market_cap": "Large"},
    "ICICIBANK": {"name": "ICICI Bank", "sector": "Banking", "market_cap": "Large"},
    "HINDUNILVR": {"name": "Hindustan Unilever", "sector": "FMCG", "market_cap": "Large"},
    "SBIN": {"name": "State Bank of India", "sector": "Banking", "market_cap": "Large"},
    "BHARTIARTL": {"name": "Bharti Airtel", "sector": "Telecom", "market_cap": "Large"},
    "KOTAKBANK": {"name": "Kotak Mahindra Bank", "sector": "Banking", "market_cap": "Large"},
    "ITC": {"name": "ITC Limited", "sector": "FMCG", "market_cap": "Large"},
    "LT": {"name": "Larsen & Toubro", "sector": "Infrastructure", "market_cap": "Large"},
    "AXISBANK": {"name": "Axis Bank", "sector": "Banking", "market_cap": "Large"},
    "ASIANPAINT": {"name": "Asian Paints", "sector": "Paints", "market_cap": "Large"},
    "MARUTI": {"name": "Maruti Suzuki", "sector": "Automobiles", "market_cap": "Large"},
    "BAJFINANCE": {"name": "Bajaj Finance", "sector": "NBFC", "market_cap": "Large"},
    "TITAN": {"name": "Titan Company", "sector": "Consumer Goods", "market_cap": "Large"},
    "SUNPHARMA": {"name": "Sun Pharma", "sector": "Pharma", "market_cap": "Large"},
    "ULTRACEMCO": {"name": "UltraTech Cement", "sector": "Cement", "market_cap": "Large"},
    "NESTLEIND": {"name": "Nestle India", "sector": "FMCG", "market_cap": "Large"},
    "WIPRO": {"name": "Wipro", "sector": "IT", "market_cap": "Large"},
    "HCLTECH": {"name": "HCL Technologies", "sector": "IT", "market_cap": "Large"},
    "POWERGRID": {"name": "Power Grid Corporation", "sector": "Power", "market_cap": "Large"},
    "NTPC": {"name": "NTPC Limited", "sector": "Power", "market_cap": "Large"},
    "ONGC": {"name": "Oil & Natural Gas Corp", "sector": "Oil & Gas", "market_cap": "Large"},
    "JSWSTEEL": {"name": "JSW Steel", "sector": "Metals", "market_cap": "Large"},
    "TATASTEEL": {"name": "Tata Steel", "sector": "Metals", "market_cap": "Large"},
    "M&M": {"name": "Mahindra & Mahindra", "sector": "Automobiles", "market_cap": "Large"},
    "ADANIPORTS": {"name": "Adani Ports", "sector": "Infrastructure", "market_cap": "Large"},
    "COALINDIA": {"name": "Coal India", "sector": "Mining", "market_cap": "Large"},
    "GRASIM": {"name": "Grasim Industries", "sector": "Diversified", "market_cap": "Large"},
    "BAJAJFINSV": {"name": "Bajaj Finserv", "sector": "Financial Services", "market_cap": "Large"},
    "TECHM": {"name": "Tech Mahindra", "sector": "IT", "market_cap": "Large"},
    "DRREDDY": {"name": "Dr. Reddy's Labs", "sector": "Pharma", "market_cap": "Large"},
    "CIPLA": {"name": "Cipla", "sector": "Pharma", "market_cap": "Large"},
    "APOLLOHOSP": {"name": "Apollo Hospitals", "sector": "Healthcare", "market_cap": "Large"},
    "TATAMOTORS": {"name": "Tata Motors", "sector": "Automobiles", "market_cap": "Large"},
    "HEROMOTOCO": {"name": "Hero MotoCorp", "sector": "Automobiles", "market_cap": "Large"},
    "EICHERMOT": {"name": "Eicher Motors", "sector": "Automobiles", "market_cap": "Large"},
    "DIVISLAB": {"name": "Divi's Laboratories", "sector": "Pharma", "market_cap": "Large"},
    "BPCL": {"name": "Bharat Petroleum", "sector": "Oil & Gas", "market_cap": "Large"},
    "TATACONSUM": {"name": "Tata Consumer Products", "sector": "FMCG", "market_cap": "Large"},
    "ADANIENT": {"name": "Adani Enterprises", "sector": "Diversified", "market_cap": "Large"},
    "HINDALCO": {"name": "Hindalco Industries", "sector": "Metals", "market_cap": "Large"},
    "INDUSINDBK": {"name": "IndusInd Bank", "sector": "Banking", "market_cap": "Large"},
    "BRITANNIA": {"name": "Britannia Industries", "sector": "FMCG", "market_cap": "Large"},
    "SBILIFE": {"name": "SBI Life Insurance", "sector": "Insurance", "market_cap": "Large"},
    "HDFCLIFE": {"name": "HDFC Life Insurance", "sector": "Insurance", "market_cap": "Large"},
    "BAJAJ-AUTO": {"name": "Bajaj Auto", "sector": "Automobiles", "market_cap": "Large"},
    "SHREECEM": {"name": "Shree Cement", "sector": "Cement", "market_cap": "Large"},
    
    # Popular Mid-caps
    "TATAPOWER": {"name": "Tata Power", "sector": "Power", "market_cap": "Mid"},
    "IRCTC": {"name": "IRCTC", "sector": "Travel", "market_cap": "Mid"},
    "ZOMATO": {"name": "Zomato", "sector": "Food Tech", "market_cap": "Mid"},
    "PAYTM": {"name": "One97 Communications (Paytm)", "sector": "Fintech", "market_cap": "Mid"},
    "NYKAA": {"name": "FSN E-Commerce (Nykaa)", "sector": "E-commerce", "market_cap": "Mid"},
    "DMART": {"name": "Avenue Supermarts (DMart)", "sector": "Retail", "market_cap": "Large"},
    "PIDILITIND": {"name": "Pidilite Industries", "sector": "Chemicals", "market_cap": "Large"},
    "HAVELLS": {"name": "Havells India", "sector": "Electricals", "market_cap": "Mid"},
    "GODREJCP": {"name": "Godrej Consumer Products", "sector": "FMCG", "market_cap": "Mid"},
    "DABUR": {"name": "Dabur India", "sector": "FMCG", "market_cap": "Mid"},
    "MARICO": {"name": "Marico", "sector": "FMCG", "market_cap": "Mid"},
    "COLPAL": {"name": "Colgate-Palmolive India", "sector": "FMCG", "market_cap": "Mid"},
    "BERGEPAINT": {"name": "Berger Paints", "sector": "Paints", "market_cap": "Mid"},
    "PAGEIND": {"name": "Page Industries", "sector": "Textiles", "market_cap": "Mid"},
    "VOLTAS": {"name": "Voltas", "sector": "Consumer Durables", "market_cap": "Mid"},
    "TRENT": {"name": "Trent (Westside)", "sector": "Retail", "market_cap": "Mid"},
    "POLYCAB": {"name": "Polycab India", "sector": "Electricals", "market_cap": "Mid"},
    "ABCAPITAL": {"name": "Aditya Birla Capital", "sector": "Financial Services", "market_cap": "Mid"},
    "MUTHOOTFIN": {"name": "Muthoot Finance", "sector": "NBFC", "market_cap": "Mid"},
    "CHOLAFIN": {"name": "Cholamandalam Finance", "sector": "NBFC", "market_cap": "Mid"},
    "BANDHANBNK": {"name": "Bandhan Bank", "sector": "Banking", "market_cap": "Mid"},
    "IDFCFIRSTB": {"name": "IDFC First Bank", "sector": "Banking", "market_cap": "Mid"},
    "FEDERALBNK": {"name": "Federal Bank", "sector": "Banking", "market_cap": "Mid"},
    "RBLBANK": {"name": "RBL Bank", "sector": "Banking", "market_cap": "Mid"},
    "PNB": {"name": "Punjab National Bank", "sector": "Banking", "market_cap": "Mid"},
    "BANKBARODA": {"name": "Bank of Baroda", "sector": "Banking", "market_cap": "Mid"},
    "CANBK": {"name": "Canara Bank", "sector": "Banking", "market_cap": "Mid"},
    "UNIONBANK": {"name": "Union Bank of India", "sector": "Banking", "market_cap": "Mid"},
    "IOC": {"name": "Indian Oil Corporation", "sector": "Oil & Gas", "market_cap": "Large"},
    "GAIL": {"name": "GAIL India", "sector": "Oil & Gas", "market_cap": "Mid"},
    "HINDPETRO": {"name": "Hindustan Petroleum", "sector": "Oil & Gas", "market_cap": "Mid"},
    "VEDL": {"name": "Vedanta", "sector": "Metals", "market_cap": "Mid"},
    "NMDC": {"name": "NMDC", "sector": "Mining", "market_cap": "Mid"},
    "SAIL": {"name": "Steel Authority of India", "sector": "Metals", "market_cap": "Mid"},
    "TATAELXSI": {"name": "Tata Elxsi", "sector": "IT", "market_cap": "Mid"},
    "LTIM": {"name": "LTIMindtree", "sector": "IT", "market_cap": "Large"},
    "MPHASIS": {"name": "Mphasis", "sector": "IT", "market_cap": "Mid"},
    "PERSISTENT": {"name": "Persistent Systems", "sector": "IT", "market_cap": "Mid"},
    "COFORGE": {"name": "Coforge", "sector": "IT", "market_cap": "Mid"},
    "HAPPSTMNDS": {"name": "Happiest Minds", "sector": "IT", "market_cap": "Small"},
}


def search_indian_stocks(query: str, limit: int = 10) -> list[dict[str, str]]:
    """
    Search Indian stocks by ticker or company name.
    
    Args:
        query: Search term (ticker or company name)
        limit: Max results to return
        
    Returns:
        List of matching stocks with symbol, name, sector
    """
    query = query.upper().strip()
    results = []
    
    for symbol, info in INDIAN_STOCKS.items():
        # Match by symbol
        if query in symbol:
            results.append({
                "symbol": symbol,
                "name": info["name"],
                "sector": info["sector"],
                "market": "NSE",
            })
        # Match by company name
        elif query.lower() in info["name"].lower():
            results.append({
                "symbol": symbol,
                "name": info["name"],
                "sector": info["sector"],
                "market": "NSE",
            })
        
        if len(results) >= limit:
            break
    
    return results


def get_yahoo_symbol(ticker: str) -> str:
    """
    Convert ticker to Yahoo Finance format.
    
    For Indian stocks, adds .NS suffix.
    """
    ticker = ticker.upper().strip()
    
    # Remove existing suffix
    ticker = ticker.replace(".NS", "").replace(".BO", "")
    
    # Check if it's an Indian stock
    if ticker in INDIAN_STOCKS:
        return f"{ticker}.NS"
    
    # Return as-is for US stocks
    return ticker


async def fetch_indian_stock(ticker: str) -> dict[str, Any]:
    """
    Fetch Indian stock data via Yahoo Finance.
    
    Args:
        ticker: NSE stock symbol (e.g., "INFY", "TCS")
        
    Returns:
        Stock data dictionary
    """
    ticker = ticker.upper().strip().replace(".NS", "").replace(".BO", "")
    yahoo_symbol = f"{ticker}.NS"
    
    # Get stock info from database
    stock_info = INDIAN_STOCKS.get(ticker, {})
    
    try:
        # Fetch from Yahoo Finance
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Quote endpoint
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
            response = await client.get(url, params={
                "interval": "1d",
                "range": "5d",
            })
            
            if response.status_code != 200:
                logger.warning(f"Yahoo Finance error for {yahoo_symbol}: {response.status_code}")
                return {
                    "symbol": ticker,
                    "success": False,
                    "error": f"Could not fetch data for {ticker}. Yahoo returned {response.status_code}",
                }
            
            data = response.json()
            result = data.get("chart", {}).get("result", [])
            
            if not result:
                return {
                    "symbol": ticker,
                    "success": False,
                    "error": f"No data found for {ticker}",
                }
            
            meta = result[0].get("meta", {})
            quote = result[0].get("indicators", {}).get("quote", [{}])[0]
            
            # Get latest values
            current_price = meta.get("regularMarketPrice", 0)
            prev_close = meta.get("previousClose", current_price)
            change = current_price - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0
            
            return {
                "symbol": ticker,
                "success": True,
                "market": "NSE",
                "yahoo_symbol": yahoo_symbol,
                "quote": {
                    "price": current_price,
                    "change": round(change, 2),
                    "change_percent": round(change_pct, 2),
                    "prev_close": prev_close,
                    "day_high": meta.get("regularMarketDayHigh", 0),
                    "day_low": meta.get("regularMarketDayLow", 0),
                    "volume": meta.get("regularMarketVolume", 0),
                    "name": stock_info.get("name", meta.get("shortName", ticker)),
                },
                "info": {
                    "name": stock_info.get("name", meta.get("shortName", ticker)),
                    "sector": stock_info.get("sector", ""),
                    "market_cap": stock_info.get("market_cap", ""),
                    "exchange": "NSE",
                    "currency": "INR",
                }
            }
            
    except Exception as e:
        logger.error(f"Error fetching {ticker}: {e}")
        return {
            "symbol": ticker,
            "success": False,
            "error": str(e),
        }


# US Stock database for search
US_STOCKS = {
    "AAPL": {"name": "Apple Inc.", "sector": "Technology"},
    "MSFT": {"name": "Microsoft Corporation", "sector": "Technology"},
    "GOOGL": {"name": "Alphabet Inc. (Google)", "sector": "Technology"},
    "AMZN": {"name": "Amazon.com Inc.", "sector": "Consumer Discretionary"},
    "NVDA": {"name": "NVIDIA Corporation", "sector": "Technology"},
    "META": {"name": "Meta Platforms (Facebook)", "sector": "Technology"},
    "TSLA": {"name": "Tesla Inc.", "sector": "Automobiles"},
    "BRK-B": {"name": "Berkshire Hathaway", "sector": "Financial Services"},
    "JPM": {"name": "JPMorgan Chase", "sector": "Banking"},
    "V": {"name": "Visa Inc.", "sector": "Financial Services"},
    "JNJ": {"name": "Johnson & Johnson", "sector": "Healthcare"},
    "WMT": {"name": "Walmart Inc.", "sector": "Retail"},
    "MA": {"name": "Mastercard", "sector": "Financial Services"},
    "PG": {"name": "Procter & Gamble", "sector": "Consumer Staples"},
    "HD": {"name": "Home Depot", "sector": "Retail"},
    "DIS": {"name": "Walt Disney Company", "sector": "Entertainment"},
    "NFLX": {"name": "Netflix Inc.", "sector": "Entertainment"},
    "PYPL": {"name": "PayPal Holdings", "sector": "Fintech"},
    "INTC": {"name": "Intel Corporation", "sector": "Technology"},
    "AMD": {"name": "Advanced Micro Devices", "sector": "Technology"},
    "CRM": {"name": "Salesforce", "sector": "Technology"},
    "ADBE": {"name": "Adobe Inc.", "sector": "Technology"},
    "CSCO": {"name": "Cisco Systems", "sector": "Technology"},
    "ORCL": {"name": "Oracle Corporation", "sector": "Technology"},
    "IBM": {"name": "IBM", "sector": "Technology"},
}


def search_all_stocks(query: str, limit: int = 15) -> list[dict[str, str]]:
    """
    Search all stocks (Indian + US) by ticker or company name.
    """
    query = query.strip()
    results = []
    
    # Search Indian stocks first
    indian_results = search_indian_stocks(query, limit=10)
    results.extend(indian_results)
    
    # Search US stocks
    query_upper = query.upper()
    for symbol, info in US_STOCKS.items():
        if len(results) >= limit:
            break
        if query_upper in symbol or query.lower() in info["name"].lower():
            results.append({
                "symbol": symbol,
                "name": info["name"],
                "sector": info["sector"],
                "market": "US",
            })
    
    return results[:limit]
