"""
Indian Stock Data Only - Multi-Source

NSE/BSE stocks only. No US markets.
Fallback: Yahoo Finance → Google Finance → NSE Direct
"""
import asyncio
import logging
import re
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import xml.etree.ElementTree as ET

# ... existing imports ...

# Helper Functions
def _calculate_rsi(prices: list[float], period: int = 14) -> float:
    if len(prices) < period + 1: return 50.0
    deltas = [prices[i]-prices[i-1] for i in range(1, len(prices))]
    gains = [d for d in deltas if d > 0]
    losses = [abs(d) for d in deltas if d < 0]
    
    # Simple avg for speed (Exponential is better but this is sufficient for MVP)
    avg_gain = sum(gains[-period:]) / period if gains else 0
    avg_loss = sum(losses[-period:]) / period if losses else 0.001
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

async def fetch_stock_history(symbol: str) -> list[float]:
    """Fetch 3mo daily closing prices for technicals."""
    y_sym = f"{symbol}.NS"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{y_sym}?interval=1d&range=3mo"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                data = r.json()
                result = data.get('chart', {}).get('result', [])
                if result:
                    closes = result[0].get('indicators', {}).get('quote', [])[0].get('close', [])
                    return [c for c in closes if c is not None]
    except Exception:
        pass
    return []

async def fetch_news(symbol: str) -> list[str]:
    """Fetch top 3 news headlines from Google News RSS."""
    url = f"https://news.google.com/rss/search?q={symbol}+stock+India&hl=en-IN&gl=IN&ceid=IN:en"
    headlines = []
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(url)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                for item in root.findall('.//item')[:3]:
                    title = item.find('title')
                    if title is not None:
                        headlines.append(title.text)
    except Exception:
        pass
    return headlines

def calculate_technicals(prices: list[float]) -> dict:
    """Calculate basic technicals from history."""
    if not prices or len(prices) < 20:
        return {"rsi": 50.0, "trend": "Neutral", "sma50": 0.0}
    
    rsi = _calculate_rsi(prices)
    sma50 = sum(prices[-50:]) / 50 if len(prices) >= 50 else prices[-1]

    current = prices[-1]
    trend = "Bullish" if current > sma50 else "Bearish"
    
    return {
        "rsi": round(rsi, 2),
        "trend": trend,
        "sma50": round(sma50, 2),
        "history_len": len(prices)
    }



# =============================================================================
# MARKET STATUS
# =============================================================================

IST = ZoneInfo("Asia/Kolkata")

def get_market_status() -> dict:
    """
    Get NSE market status.
    
    Market hours: 9:15 AM - 3:30 PM IST, Mon-Fri
    Pre-open: 9:00 AM - 9:15 AM
    """
    now = datetime.now(IST)
    current_time = now.time()
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    
    # Weekend
    if weekday >= 5:
        return {
            "is_open": False,
            "status": "CLOSED",
            "reason": "Weekend",
            "next_open": "Monday 9:15 AM",
            "current_time": now.strftime("%I:%M %p IST"),
            "date": now.strftime("%d %b %Y"),
        }
    
    # Pre-open (9:00 - 9:15)
    pre_open_start = time(9, 0)
    market_open = time(9, 15)
    market_close = time(15, 30)
    
    if current_time < pre_open_start:
        return {
            "is_open": False,
            "status": "PRE-MARKET",
            "reason": "Market opens at 9:15 AM",
            "current_time": now.strftime("%I:%M %p IST"),
            "date": now.strftime("%d %b %Y"),
        }
    elif current_time < market_open:
        return {
            "is_open": False,
            "status": "PRE-OPEN",
            "reason": "Pre-open session",
            "current_time": now.strftime("%I:%M %p IST"),
            "date": now.strftime("%d %b %Y"),
        }
    elif current_time <= market_close:
        return {
            "is_open": True,
            "status": "OPEN",
            "reason": "Live trading",
            "closes_at": "3:30 PM",
            "current_time": now.strftime("%I:%M %p IST"),
            "date": now.strftime("%d %b %Y"),
        }
    else:
        return {
            "is_open": False,
            "status": "CLOSED",
            "reason": "After hours",
            "next_open": "Tomorrow 9:15 AM",
            "current_time": now.strftime("%I:%M %p IST"),
            "date": now.strftime("%d %b %Y"),
        }


# =============================================================================
# INDIAN STOCK DATABASE (All major stocks)
# =============================================================================

# Full list of NSE stocks with sector info
NSE_STOCKS = {
    # NIFTY 50
    "RELIANCE": {"name": "Reliance Industries", "sector": "Oil & Gas"},
    "TCS": {"name": "Tata Consultancy Services", "sector": "IT"},
    "HDFCBANK": {"name": "HDFC Bank", "sector": "Banking"},
    "INFY": {"name": "Infosys", "sector": "IT"},
    "ICICIBANK": {"name": "ICICI Bank", "sector": "Banking"},
    "HINDUNILVR": {"name": "Hindustan Unilever", "sector": "FMCG"},
    "SBIN": {"name": "State Bank of India", "sector": "Banking"},
    "BHARTIARTL": {"name": "Bharti Airtel", "sector": "Telecom"},
    "KOTAKBANK": {"name": "Kotak Mahindra Bank", "sector": "Banking"},
    "ITC": {"name": "ITC Limited", "sector": "FMCG"},
    "LT": {"name": "Larsen & Toubro", "sector": "Infrastructure"},
    "AXISBANK": {"name": "Axis Bank", "sector": "Banking"},
    "ASIANPAINT": {"name": "Asian Paints", "sector": "Paints"},
    "MARUTI": {"name": "Maruti Suzuki", "sector": "Auto"},
    "BAJFINANCE": {"name": "Bajaj Finance", "sector": "NBFC"},
    "TITAN": {"name": "Titan Company", "sector": "Consumer"},
    "SUNPHARMA": {"name": "Sun Pharma", "sector": "Pharma"},
    "ULTRACEMCO": {"name": "UltraTech Cement", "sector": "Cement"},
    "NESTLEIND": {"name": "Nestle India", "sector": "FMCG"},
    "WIPRO": {"name": "Wipro", "sector": "IT"},
    "HCLTECH": {"name": "HCL Technologies", "sector": "IT"},
    "POWERGRID": {"name": "Power Grid Corp", "sector": "Power"},
    "NTPC": {"name": "NTPC", "sector": "Power"},
    "ONGC": {"name": "ONGC", "sector": "Oil & Gas"},
    "JSWSTEEL": {"name": "JSW Steel", "sector": "Metals"},
    "TATASTEEL": {"name": "Tata Steel", "sector": "Metals"},
    "M&M": {"name": "Mahindra & Mahindra", "sector": "Auto"},
    "ADANIPORTS": {"name": "Adani Ports", "sector": "Infra"},
    "COALINDIA": {"name": "Coal India", "sector": "Mining"},
    "GRASIM": {"name": "Grasim Industries", "sector": "Diversified"},
    "BAJAJFINSV": {"name": "Bajaj Finserv", "sector": "Financial"},
    "TECHM": {"name": "Tech Mahindra", "sector": "IT"},
    "DRREDDY": {"name": "Dr. Reddy's Labs", "sector": "Pharma"},
    "CIPLA": {"name": "Cipla", "sector": "Pharma"},
    "APOLLOHOSP": {"name": "Apollo Hospitals", "sector": "Healthcare"},
    "TATAMOTORS": {"name": "Tata Motors", "sector": "Auto"},
    "HEROMOTOCO": {"name": "Hero MotoCorp", "sector": "Auto"},
    "EICHERMOT": {"name": "Eicher Motors", "sector": "Auto"},
    "DIVISLAB": {"name": "Divi's Labs", "sector": "Pharma"},
    "BPCL": {"name": "Bharat Petroleum", "sector": "Oil & Gas"},
    "TATACONSUM": {"name": "Tata Consumer", "sector": "FMCG"},
    "ADANIENT": {"name": "Adani Enterprises", "sector": "Diversified"},
    "HINDALCO": {"name": "Hindalco", "sector": "Metals"},
    "INDUSINDBK": {"name": "IndusInd Bank", "sector": "Banking"},
    "BRITANNIA": {"name": "Britannia", "sector": "FMCG"},
    "SBILIFE": {"name": "SBI Life", "sector": "Insurance"},
    "HDFCLIFE": {"name": "HDFC Life", "sector": "Insurance"},
    "BAJAJ-AUTO": {"name": "Bajaj Auto", "sector": "Auto"},
    "SHREECEM": {"name": "Shree Cement", "sector": "Cement"},
    
    # NIFTY NEXT 50 & Popular
    "TATAPOWER": {"name": "Tata Power", "sector": "Power"},
    "IRCTC": {"name": "IRCTC", "sector": "Travel"},
    "ZOMATO": {"name": "Zomato", "sector": "Food Tech"},
    "PAYTM": {"name": "Paytm", "sector": "Fintech"},
    "NYKAA": {"name": "Nykaa", "sector": "E-commerce"},
    "DMART": {"name": "Avenue Supermarts", "sector": "Retail"},
    "PIDILITIND": {"name": "Pidilite", "sector": "Chemicals"},
    "HAVELLS": {"name": "Havells", "sector": "Electricals"},
    "GODREJCP": {"name": "Godrej Consumer", "sector": "FMCG"},
    "DABUR": {"name": "Dabur", "sector": "FMCG"},
    "MARICO": {"name": "Marico", "sector": "FMCG"},
    "COLPAL": {"name": "Colgate-Palmolive", "sector": "FMCG"},
    "BERGEPAINT": {"name": "Berger Paints", "sector": "Paints"},
    "PAGEIND": {"name": "Page Industries", "sector": "Textiles"},
    "VOLTAS": {"name": "Voltas", "sector": "Consumer"},
    "TRENT": {"name": "Trent (Westside)", "sector": "Retail"},
    "POLYCAB": {"name": "Polycab", "sector": "Electricals"},
    "MUTHOOTFIN": {"name": "Muthoot Finance", "sector": "NBFC"},
    "CHOLAFIN": {"name": "Cholamandalam", "sector": "NBFC"},
    "BANDHANBNK": {"name": "Bandhan Bank", "sector": "Banking"},
    "IDFCFIRSTB": {"name": "IDFC First Bank", "sector": "Banking"},
    "FEDERALBNK": {"name": "Federal Bank", "sector": "Banking"},
    "PNB": {"name": "Punjab National Bank", "sector": "Banking"},
    "BANKBARODA": {"name": "Bank of Baroda", "sector": "Banking"},
    "CANBK": {"name": "Canara Bank", "sector": "Banking"},
    "IOC": {"name": "Indian Oil", "sector": "Oil & Gas"},
    "GAIL": {"name": "GAIL India", "sector": "Oil & Gas"},
    "HINDPETRO": {"name": "HPCL", "sector": "Oil & Gas"},
    "VEDL": {"name": "Vedanta", "sector": "Metals"},
    "NMDC": {"name": "NMDC", "sector": "Mining"},
    "SAIL": {"name": "SAIL", "sector": "Metals"},
    "TATAELXSI": {"name": "Tata Elxsi", "sector": "IT"},
    "LTIM": {"name": "LTIMindtree", "sector": "IT"},
    "MPHASIS": {"name": "Mphasis", "sector": "IT"},
    "PERSISTENT": {"name": "Persistent Systems", "sector": "IT"},
    "COFORGE": {"name": "Coforge", "sector": "IT"},
    "HAPPSTMNDS": {"name": "Happiest Minds", "sector": "IT"},
    "DIXON": {"name": "Dixon Technologies", "sector": "Electronics"},
    "CDSL": {"name": "CDSL", "sector": "Financial"},
    "NAUKRI": {"name": "Info Edge (Naukri)", "sector": "Internet"},
    "INDIAMART": {"name": "IndiaMART", "sector": "Internet"},
    "POLICYBZR": {"name": "PB Fintech", "sector": "Fintech"},
    "LICI": {"name": "LIC India", "sector": "Insurance"},
    "ADANIGREEN": {"name": "Adani Green", "sector": "Renewables"},
    "ADANIPOWER": {"name": "Adani Power", "sector": "Power"},
    "VEDL": {"name": "Vedanta", "sector": "Metals"},
    "JIOFIN": {"name": "Jio Financial", "sector": "Financial"},
    "YESBANK": {"name": "Yes Bank", "sector": "Banking"},
    "IDEA": {"name": "Vodafone Idea", "sector": "Telecom"},
    "SUZLON": {"name": "Suzlon Energy", "sector": "Renewables"},
    "IRFC": {"name": "IRFC", "sector": "Financial"},
    "HAL": {"name": "Hindustan Aeronautics", "sector": "Defence"},
    "BEL": {"name": "Bharat Electronics", "sector": "Defence"},
    "BHEL": {"name": "BHEL", "sector": "Capital Goods"},
}


# =============================================================================
# YAHOO FINANCE FETCHER
# =============================================================================

async def fetch_yahoo(symbol: str) -> dict:
    """Fetch from Yahoo Finance with NSE suffix."""
    yahoo_symbol = f"{symbol}.NS"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://finance.yahoo.com",
        "Referer": "https://finance.yahoo.com/",
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
            response = await client.get(url, params={"interval": "1d", "range": "5d"})
            
            if response.status_code == 200:
                data = response.json()
                result = data.get("chart", {}).get("result", [])
                
                if result:
                    meta = result[0].get("meta", {})
                    price = meta.get("regularMarketPrice", 0)
                    # Try multiple keys for previous close to avoid 0% change bug
                    prev = meta.get("chartPreviousClose") or meta.get("previousClose") or meta.get("regularMarketPreviousClose") or price
                    
                    if price and price > 0:
                        stock_info = NSE_STOCKS.get(symbol, {})
                        return {
                            "success": True,
                            "symbol": symbol,
                            "name": stock_info.get("name", meta.get("shortName", symbol)),
                            "sector": stock_info.get("sector", ""),
                            "price": float(price),
                            "change": round(float(price - prev), 2),
                            "change_percent": round((price - prev) / prev * 100, 2) if prev else 0,
                            "prev_close": float(prev),
                            "open": float(meta.get("regularMarketOpen", 0)),
                            "high": float(meta.get("regularMarketDayHigh", 0)),
                            "low": float(meta.get("regularMarketDayLow", 0)),
                            "volume": int(meta.get("regularMarketVolume", 0)),
                            "source": "yahoo",
                        }
            
            return {"success": False, "error": "Yahoo returned no data"}
            
    except Exception as e:
        return {"success": False, "error": f"Yahoo: {str(e)}"}


# =============================================================================
# GOOGLE FINANCE SCRAPER
# =============================================================================

async def fetch_google(symbol: str) -> dict:
    """Fetch from Google Finance."""
    try:
        url = f"https://www.google.com/finance/quote/{symbol}:NSE"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
        
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            response = await client.get(url)
            
            if response.status_code == 200:
                text = response.text
                
                price_match = re.search(r'data-last-price="([\d.]+)"', text)
                change_match = re.search(r'data-last-price-change="(-?[\d.]+)"', text)
                pct_match = re.search(r'data-last-price-change-percentage="(-?[\d.]+)"', text)
                
                if price_match:
                    price = float(price_match.group(1))
                    change = float(change_match.group(1)) if change_match else 0
                    pct = float(pct_match.group(1)) if pct_match else 0
                    
                    stock_info = NSE_STOCKS.get(symbol, {})
                    return {
                        "success": True,
                        "symbol": symbol,
                        "name": stock_info.get("name", symbol),
                        "sector": stock_info.get("sector", ""),
                        "price": price,
                        "change": change,
                        "change_percent": pct,
                        "prev_close": price - change,
                        "source": "google",
                    }
        
        return {"success": False, "error": "Google parsing failed"}
        
    except Exception as e:
        return {"success": False, "error": f"Google: {str(e)}"}


# =============================================================================
# MULTI-SOURCE FETCH
# =============================================================================

async def fetch_stock(symbol: str) -> dict:
    """
    Fetch Indian stock with fallback.
    
    Order: Yahoo → Google
    """
    symbol = symbol.upper().strip().replace(".NS", "").replace(".BO", "")
    sources_tried = []
    
    # Try Yahoo
    sources_tried.append("yahoo")
    result = await fetch_yahoo(symbol)
    if result.get("success"):
        result["sources_tried"] = sources_tried
        result["market"] = "NSE"
        return result
    
    # Try Google
    sources_tried.append("google")
    result = await fetch_google(symbol)
    if result.get("success"):
        result["sources_tried"] = sources_tried
        result["market"] = "NSE"
        return result
    
    return {
        "success": False,
        "symbol": symbol,
        "error": f"Stock data not available. Try another ticker.",
        "sources_tried": sources_tried,
    }


# =============================================================================
# MARKET STATS (Indices & Gainers)
# =============================================================================

NSE_INDICES = {
    "^NSEI": "NIFTY 50",
    "^NSEBANK": "BANK NIFTY",
    "^BSESN": "SENSEX",
    "^CNXIT": "NIFTY IT",
    "^CNXAUTO": "NIFTY AUTO",
    "^CNXPHARMA": "NIFTY PHARMA",
    "^CNXFMCG": "NIFTY FMCG",
    "^CNXMETAL": "NIFTY METAL",
    "^CNXENERGY": "NIFTY ENERGY",
}

async def get_market_indices() -> list[dict]:
    """Fetch major indices."""
    tasks = []
    for symbol in NSE_INDICES:
        tasks.append(fetch_yahoo(symbol))
    
    results = await asyncio.gather(*tasks)
    indices = []
    
    for res in results:
        if res.get("success"):
            name = NSE_INDICES.get(res["symbol"], res["symbol"])
            indices.append({
                "symbol": name,
                "price": res["price"],
                "change": res["change"],
                "change_percent": res["change_percent"],
                "direction": "UP" if res["change"] >= 0 else "DOWN"
            })
    return indices


async def get_top_gainers(limit: int = 5) -> list[dict]:
    """
    Get top gainers from our tracked NIFTY 50 list.
    Real market screening is expensive; this scans our watched list.
    """
    # Pick a random sample or important subset to scan to save time/bandwidth
    # For now, let's scan a fixed set of popular volatile stocks
    subset = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ZOMATO", "TATAMOTORS", 
              "ADANIENT", "SBIN", "BAJFINANCE", "ITC"]
    
    tasks = [fetch_stock(sym) for sym in subset]
    results = await asyncio.gather(*tasks)
    
    valid = [r for r in results if r.get("success")]
    sorted_stocks = sorted(valid, key=lambda x: x.get("change_percent", 0), reverse=True)
    
    return sorted_stocks[:limit]

# =============================================================================
# SEARCH
# =============================================================================

def search_stocks(query: str, limit: int = 15) -> list[dict]:
    """Search NSE stocks only."""
    query = query.upper().strip()
    results = []
    
    for symbol, info in NSE_STOCKS.items():
        if query in symbol or query.lower() in info["name"].lower():
            results.append({
                "symbol": symbol,
                "name": info["name"],
                "sector": info["sector"],
                "market": "NSE",
            })
            if len(results) >= limit:
                break
    
    return results
