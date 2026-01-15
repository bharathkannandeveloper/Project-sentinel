"""
Sentinel Chatbot with Dynamic Prompts

Features:
- Auto-detects prompt type (Simple vs Deep vs Comparison)
- Improved formatting (no heavy headers for simple chats)
- Tanglish support
"""
import asyncio
import os
import re
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from src.llm.manager import LLMManager
from src.llm.prompt_builder import (
    PromptContext, 
    PromptType, 
    build_prompt, 
    build_butterfly_prompt, 
    extract_rating
)
from src.ingestion.multi_source import (
    fetch_stock, 
    fetch_stock_history, 
    fetch_news, 
    calculate_technicals, 
    NSE_STOCKS, 
    get_market_status
)

logger = logging.getLogger("sentinel.chatbot")


# =============================================================================
# MEMORY
# =============================================================================

@dataclass
class Message:
    role: str
    content: str
    stock: str | None = None


class ConversationMemory:
    def __init__(self, max_messages: int = 30):
        self.messages: list[Message] = []
        self.max_messages = max_messages
        self.stocks_discussed: list[str] = []
    
    def add(self, role: str, content: str, stock: str | None = None):
        if not content: return
        self.messages.append(Message(role=role, content=content, stock=stock))
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
        if stock and stock not in self.stocks_discussed:
            self.stocks_discussed.append(stock)
    
    def get_context_list(self, limit: int = 10) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in self.messages[-limit:]]
    
    def clear(self):
        self.messages = []
        self.stocks_discussed = []


# =============================================================================
# BUTTERFLY EFFECT LOGIC (Simplified)
# =============================================================================

BUTTERFLY_CHAINS = {
    "war_iran": ["ONGC", "RELIANCE", "INDIGO", "SPICEJET"],
    "oil_surge": ["ONGC", "OIL", "BPCL", "ASIANPAINT"],
    "rbi_rate": ["HDFCBANK", "SBIN", "BAJFINANCE", "DLF"],
    "rupee_fall": ["TCS", "INFY", "TITAN", "MARUTI"],
}


def analyze_butterfly_impacts(event: str) -> list[dict]:
    """Simple impact logic for now."""
    event = event.lower()
    impacts = []
    
    if "iran" in event or "war" in event:
        impacts = [
            {"stock": "ONGC", "direction": "UP", "reason": "Oil price surge benefits producer"},
            {"stock": "RELIANCE", "direction": "UP", "reason": "Inventory gain & GRM boost"},
            {"stock": "INDIGO", "direction": "DOWN", "reason": "Fuel cost spike hurts margins"},
        ]
    elif "oil" in event:
        impacts = [
            {"stock": "ONGC", "direction": "UP", "reason": "Direct beneficiary of crude rise"},
            {"stock": "ASIANPAINT", "direction": "DOWN", "reason": "Input costs increase"},
        ]
    elif "rate" in event or "rbi" in event:
        impacts = [
            {"stock": "HDFCBANK", "direction": "UP", "reason": "NIM expansion possible"},
            {"stock": "BAJFINANCE", "direction": "DOWN", "reason": "Cost of funds rises"},
        ]
    
    return impacts


# =============================================================================
# CHATBOT CLASS
# =============================================================================

class SentinelBot:
    """Intelligent stock analyst bot."""
    
    def __init__(self):
        self.memory = ConversationMemory()
        self.llm_manager = LLMManager()
    
    def _determine_prompt_type(self, message: str, is_analyze_api: bool = False) -> PromptType:
        """Decide what kind of response the user wants."""
        if is_analyze_api:
            return PromptType.DEEP
            
        msg = message.lower()
        
        if "compare" in msg or "vs" in msg or "better" in msg:
            return PromptType.COMPARISON
        
        if any(x in msg for x in ["price", "value", "rate", "what is"]):
            return PromptType.SIMPLE
            
        if any(x in msg for x in ["analyze", "fundamental", "technical", "report"]):
            return PromptType.DEEP
            
        return PromptType.GENERAL

    async def analyze(self, symbol: str) -> dict:
        """Full Deep Analysis (via Analyze Button)."""
        symbol = symbol.upper().strip()
        
        # Parallel Fetch for Speed
        data_task = fetch_stock(symbol)
        hist_task = fetch_stock_history(symbol)
        news_task = fetch_news(symbol)
        
        # Use return_exceptions=True to prevent one failure from crashing all
        results = await asyncio.gather(data_task, hist_task, news_task, return_exceptions=True)
        
        data = results[0] if isinstance(results[0], dict) else {"success": False, "error": "Fetch failed"}
        history = results[1] if isinstance(results[1], list) else []
        news = results[2] if isinstance(results[2], list) else []
        
        if not data.get("success"):
            return {
                "success": False, 
                "error": data.get("error", "Stock not available"),
                "symbol": symbol
            }
            
        # Calculate Technicals
        technicals = calculate_technicals(history)
        
        # Check Butterfly Effect
        butterfly_ctx = ""
        for chain, related in BUTTERFLY_CHAINS.items():
            if symbol in related:
                butterfly_ctx += f"Stock is part of the **{chain.upper()}** event chain (Watch closely).\n"
        
        # Build Context
        ctx = self._create_context(symbol, data, PromptType.DEEP)
        ctx.technicals = technicals
        ctx.news = news
        ctx.butterfly_context = butterfly_ctx
        
        # Get AI Response
        analysis = await self._generate_response(ctx)
        
        self.memory.add("user", f"Analyze {symbol}", stock=symbol)
        self.memory.add("assistant", analysis, stock=symbol)
        
        return {
            "success": True,
            "symbol": symbol,
            "name": data.get("name"),
            "price": data.get("price"),
            "change_percent": data.get("change_percent"),
            "rating": extract_rating(analysis),
            "analysis": analysis,
            "data": data,
            "source": data.get("source"),
            "technicals": technicals 
        }

    def _extract_ticker(self, text: str) -> list[str]:
        """Find all tickers in text."""
        text_upper = text.upper()
        found = []
        for symbol in NSE_STOCKS:
            # Simple boundary check to avoid substring matches like 'IT' in 'WITH'
            # (Checking if symbol is present is rough, but works for limited set)
            if symbol in text_upper:
                # Basic check to avoid false positives (e.g. "ON" in "ONGC")
                # Ideally regex, but simple substring for now
                found.append(symbol)
        
        # Filter: if shorter match is inside longer match (e.g. "IT" in "ITC"), keep longer?
        # Actually NSE symbols are fairly unique.
        # But optimize: "ITC" contains "IT".
        # Let's just return unique found.
        return list(set(found))

    async def chat(self, message: str) -> dict:
        """Dynamic Chat Handler."""
        print(f"Chat Request: {message}")
        self.memory.add("user", message)
        
        try:
            # 1. Check for Butterfly/Event
            impacts = analyze_butterfly_impacts(message)
            if impacts:
                print("Butterfly logic triggered")
                system_prompt, user_prompt = build_butterfly_prompt(message, impacts)
                response = await self._call_llm(system_prompt, user_prompt)
                self.memory.add("assistant", response)
                return {"success": True, "response": response}

            # 2. Extract Stock Tickers
            tickers = self._extract_ticker(message)
            print(f"Found tickers: {tickers}")
            
            # 3. Determine Mode
            p_type = self._determine_prompt_type(message)
            
            if tickers:
                # Fetch data for all found tickers
                # If comparison, we want up to 3-4
                # Parse top 3 if too many
                targets = tickers[:4]
                multi_data = []
                primary_data = None
                
                for t in targets:
                    d = await fetch_stock(t)
                    if d.get("success"):
                        # Format compact info for prompt
                        change_icon = "🟢" if d['change'] >= 0 else "🔴"
                        info = f"Stock: {d['symbol']}\nPrice: ₹{d['price']}\nChange: {d['change_percent']}% {change_icon}\nPE: {d.get('pe', 'N/A')}\nSector: {d.get('sector', 'N/A')}\n"
                        multi_data.append(info)
                        if not primary_data: primary_data = d # Keep first as primary context
                
                combined_data_str = "\n---\n".join(multi_data)
                
                if primary_data:
                    # Create context using primary stock but inject combined string
                    ctx = self._create_context(primary_data['symbol'], primary_data, p_type, message)
                    # We need to hack the prompt builder or append to user question to include other stocks
                    # Let's append to user_question context for simplicity
                    ctx.user_question = f"{message}\n\nRELEVANT LIVE DATA:\n{combined_data_str}"
                    
                    response = await self._generate_response(ctx)
                else:
                    response = "Data fetch failed for specified stocks."
            else:
                # General chat
                ctx = PromptContext(user_question=message, prompt_type=PromptType.GENERAL)
                context_messages = self.memory.get_context_list(5)
                system_prompt, user_prompt = build_prompt(ctx) 
                history_text = "\n".join([f"{m['role']}: {m['content']}" for m in context_messages[:-1]])
                user_prompt = f"Chat History:\n{history_text}\n\nUser Question: {message}"
                response = await self._call_llm(system_prompt, user_prompt)

            print(f"Response len: {len(response)}")
            self.memory.add("assistant", response)
            
            return {
                "success": True, 
                "response": response, 
                "stocks": self.memory.stocks_discussed
            }
        except Exception as e:
            print(f"Chat Error: {e}")
            return {"success": False, "response": f"Error da: {str(e)}"}


    def _create_context(self, symbol: str, data: dict, p_type: PromptType, user_msg: str = "") -> PromptContext:
        """Map data dict to PromptContext object."""
        return PromptContext(
            stock_symbol=symbol,
            stock_name=data.get("name", ""),
            sector=data.get("sector", ""),
            price=data.get("price", 0),
            change_percent=data.get("change_percent", 0),
            prev_close=data.get("prev_close", 0),
            open=data.get("open", 0),
            day_high=data.get("high", 0),
            day_low=data.get("low", 0),
            volume=data.get("volume", 0),
            market_cap=data.get("market_cap", ""),
            pe_ratio=data.get("pe", 0),
            prompt_type=p_type,
            user_question=user_msg
        )

    # Legacy method removed


    async def _generate_response(self, context: PromptContext) -> str:
        """Generate response using prompt builder."""
        system, user = build_prompt(context)
        return await self._call_llm(system, user)

    async def _call_llm(self, system: str, user: str) -> str:
        """Execute LLM call via LLMManager."""
        try:
            response = await self.llm_manager.complete(
                prompt=user,
                system_prompt=system,
                temperature=0.7,
                max_tokens=2048
            )
            return response.content
        except Exception as e:
            return f"Error: {str(e)}"

    def clear_memory(self):
        self.memory.clear()
        
    def reload_config(self):
        """Reload LLM configuration."""
        # LLMManager uses cached config, which we might have updated in memory.
        # Re-init manager to pick up changes or check if it picks up automatically.
        # Since config object is singleton, it should see changes if instance shares same config object.
        # But safeguards:
        from src.llm.config import get_llm_config
        self.llm_manager = LLMManager(config=get_llm_config())

# Singleton
_bot = None
def get_chatbot():
    global _bot
    if _bot is None:
        _bot = SentinelBot()
    return _bot

def analyze_butterfly(event):
    """Bridge for old import."""
    return analyze_butterfly_impacts(event)
