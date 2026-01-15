"""
Smart Prompt Builder - Dynamic & Data-Focused (Tanglish Edition)

Types:
- SIMPLE: Price checks, basic status
- DEEP: Full analysis with tables
- COMPARISON: Compare multiple stocks
- GENERAL: Market questions, small talk
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any


class PromptType(Enum):
    SIMPLE = "simple"
    DEEP = "deep"
    COMPARISON = "comparison"
    GENERAL = "general"


@dataclass
class PromptContext:
    """Context for building prompts."""
    stock_symbol: str = ""
    stock_name: str = ""
    sector: str = ""
    price: float = 0
    change_percent: float = 0
    prev_close: float = 0
    open: float = 0
    day_high: float = 0
    day_low: float = 0
    volume: int = 0
    week_52_high: float = 0
    week_52_low: float = 0
    market_cap: str = ""
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    eps: float | None = None
    dividend_yield: float | None = None
    debt_to_equity: float | None = None
    roe: float | None = None
    roce: float | None = None
    promoter_holding: float | None = None
    pledged_percent: float | None = None
    description: str = ""
    news: list[str] | None = None
    technicals: dict | None = None
    butterfly_context: str = ""
    user_question: str = ""
    prompt_type: PromptType = PromptType.DEEP


# =============================================================================
# SYSTEM PROMPTS
# =============================================================================

# Common Guidelines
BASE_INSTRUCTIONS = """You are Sentinel, a smart Indian stock analyst.
- Use **Tanglish** naturally (romanized Tamil + English) like "Paaru da", "Semma stock", "Waste pannatha".
- **DATA IS LIVE**: The data provided is REAL-TIME. Trust it 100%.
- **NO HALLUCINATIONS**: Do not make up numbers. Use only what is provided.
- **FORMATTING**: Use clean Markdown. No extra blank lines. Use tables where helpful.
"""

# 1. SIMPLE (Price check, simple status)
SIMPLE_SYSTEM = BASE_INSTRUCTIONS + """
## MODE: QUICK CHECK
- specific answer only.
- Just tell the price, status, and a quick one-line verdict.

### FORMAT
**[SYMBOL]**
₹[Price] ([Change]%) [Emoji]
*[One sentence Tanglish comment]*
"""

# 2. DEEP (Full analysis)
DEEP_SYSTEM = BASE_INSTRUCTIONS + """
## MODE: DEEP ANALYSIS
- Give comprehensive analysis covering Fundamentals, Technicals, News, and Geopolitics.
- Use the exact format below.

### RESPONSE FORMAT
### 🎯 VERDICT: [BUY / HOLD / SELL / AVOID]
*[One powerful conviction sentence based on combined data]*

### 📊 Key Fundamentals
| Metric | Value | Status |
|---|---|---|
| Price | ₹XXX | 🟢/🔴 |
| P/E | XX.X | High/Low |
| D/E | X.X | ✅/⚠️ |

### 📈 Technicals & Momentum
- **RSI (14)**: [Value from Context] ([Neutral/Overbought/Oversold])
- **Trend**: [Trend from Context] (vs SMA50)
- **Moving Avg (50)**: [Value from Context]

### 📰 Recent News & Sentiment
*[Summarize the news provided in context. If none, mention general market mood]*
- [News Item 1] -> [Impact]
- [News Item 2]

### 🦋 Geopolitical/Butterfly Effect
*[Analyze macro factors provided in context]*
- **Macro Factors**: [From Context]
- **Chain Reaction**: [How it affects this stock]

### 💡 Sentinel's Take
*[Commanding advice in Tanglish. Synthesize all above factors.]*
"""

# 3. COMPARISON
COMPARISON_SYSTEM = BASE_INSTRUCTIONS + """
## MODE: COMPARISON
- Compare the stocks provided.
- Use a table for comparison.
- Pick a WINNER at the end.

### FORMAT
**Comparison**

| Feature | Stock A | Stock B |
|---|---|---|
| Price | ... | ... |
| P/E | ... | ... |
| Verdict| ... | ... |

### 🏆 Winner: [Stock Name]
*[Reason in Tanglish]*
"""

# 4. GENERAL (Chat, Geopolitics)
GENERAL_SYSTEM = BASE_INSTRUCTIONS + """
## MODE: GENERAL / CHAT
- Answer general market questions or geopolitics.
- Use bullet points for clarity.
- Keep it conversational but authoritative.
"""

def build_prompt(context: PromptContext) -> tuple[str, str]:
    """Build prompt based on context type."""
    
    # 1. Build Data Section
    data_parts = [f"**LIVE MARKET DATA for {context.stock_symbol} ({context.stock_name})**"]
    
    if context.price:
        direction = "UP 🟢" if context.change_percent >= 0 else "DOWN 🔴"
        data_parts.append(f"- **Current Price**: ₹{context.price:,.2f}")
        data_parts.append(f"- **Change**: {context.change_percent:+.2f}% ({direction})")
        data_parts.append(f"- **Prev Close**: ₹{context.prev_close:,.2f}")
    
    if context.day_high:
        data_parts.append(f"- **Day Range**: ₹{context.day_low:,.2f} - ₹{context.day_high:,.2f}")
    
    if context.pe_ratio:
        data_parts.append(f"- **P/E**: {context.pe_ratio:.2f}")
        data_parts.append(f"- **Market Cap**: {context.market_cap}")
    
    if context.debt_to_equity is not None:
        data_parts.append(f"- **D/E Ratio**: {context.debt_to_equity:.2f}")
        
    if context.technicals:
        data_parts.append("\n**Technicals (Calculated):**")
        t = context.technicals
        data_parts.append(f"- RSI (14): {t.get('rsi')}")
        data_parts.append(f"- Trend (vs SMA50): {t.get('trend')}")
        data_parts.append(f"- SMA(50): {t.get('sma50')}")

    if context.news:
        data_parts.append("\n**Recent News Headlines:**")
        for n in context.news[:5]:
            data_parts.append(f"- {n}")
            
    if context.butterfly_context:
        data_parts.append("\n**Active Geopolitical Context:**")
        data_parts.append(context.butterfly_context)

    data_text = "\n".join(data_parts)
    
    # 2. Select System Prompt
    user_content = f"""
{data_text}

**User Question**: {context.user_question}

Provide your response based on the LIVE DATA above.
"""

    if context.prompt_type == PromptType.SIMPLE:
        return SIMPLE_SYSTEM, user_content
    elif context.prompt_type == PromptType.DEEP:
        return DEEP_SYSTEM, user_content
    elif context.prompt_type == PromptType.COMPARISON:
        return COMPARISON_SYSTEM, user_content
    else:
        return GENERAL_SYSTEM, user_content

BUTTERFLY_SYSTEM = BASE_INSTRUCTIONS + """
## MODE: BUTTERFLY EFFECT
- Analyze chain reactions.
- Be specific about Indian stocks.

### FORMAT
**Event**: [Event Name]

**Impact Chain**:
[Event] → [Global Effect] → [India Impact]

**Stocks to Watch**:
- **[Stock]**: [Reason] (Benefit/Risk)

*[Actionable advice in Tanglish]*
"""


# =============================================================================
# PROMPT CONSTRUCTION
# =============================================================================

def build_prompt(context: PromptContext) -> tuple[str, str]:
    """Build prompt based on context type."""
    
    # 1. Build Data Section
    data_parts = [f"**LIVE MARKET DATA for {context.stock_symbol} ({context.stock_name})**"]
    
    if context.price:
        direction = "UP 🟢" if context.change_percent >= 0 else "DOWN 🔴"
        data_parts.append(f"- **Current Price**: ₹{context.price:,.2f}")
        data_parts.append(f"- **Change**: {context.change_percent:+.2f}% ({direction})")
        data_parts.append(f"- **Prev Close**: ₹{context.prev_close:,.2f}")
    
    if context.day_high:
        data_parts.append(f"- **Day Range**: ₹{context.day_low:,.2f} - ₹{context.day_high:,.2f}")
    
    if context.pe_ratio:
        data_parts.append(f"- **P/E**: {context.pe_ratio:.2f}")
        data_parts.append(f"- **Market Cap**: {context.market_cap}")
    
    if context.debt_to_equity is not None:
        data_parts.append(f"- **D/E Ratio**: {context.debt_to_equity:.2f}")
        
    if context.news:
        data_parts.append("\n**Recent News**:")
        for n in context.news[:3]:
            data_parts.append(f"- {n}")

    data_text = "\n".join(data_parts)
    
    # 2. Select System Prompt
    user_content = f"""
{data_text}

**User Question**: {context.user_question}

Provide your response based on the LIVE DATA above.
"""

    if context.prompt_type == PromptType.SIMPLE:
        return SIMPLE_SYSTEM, user_content
    elif context.prompt_type == PromptType.DEEP:
        return DEEP_SYSTEM, user_content
    elif context.prompt_type == PromptType.COMPARISON:
        return COMPARISON_SYSTEM, user_content
    else:
        return GENERAL_SYSTEM, user_content


def build_butterfly_prompt(event: str, impacts: list[dict]) -> tuple[str, str]:
    """Build geopolitical prompt."""
    
    impact_lines = []
    for i in impacts[:10]:
        impact_lines.append(f"- **{i['stock']}**: {i['direction']} ({i['reason']})")
    
    impact_text = "\n".join(impact_lines)
    
    user_prompt = f"""
**Global Event**: {event}

**Identified Impacts**:
{impact_text}

Analyze this for the Indian investor. Who wins? Who loses? Use Tanglish.
"""
    return BUTTERFLY_SYSTEM, user_prompt


def extract_rating(response: str) -> str:
    """Extract rating from AI response."""
    upper = response.upper()
    if "STRONG BUY" in upper: return "STRONG BUY"
    if "STRONG SELL" in upper: return "STRONG SELL"
    if "AVOID" in upper: return "AVOID"
    if "BUY" in upper and "SELL" not in upper: return "BUY"
    if "SELL" in upper: return "SELL"
    return "HOLD"
