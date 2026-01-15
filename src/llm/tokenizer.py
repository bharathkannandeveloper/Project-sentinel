"""
Token Management and Prompt Engineering

Handles tokenization, context window management, and prompt construction
for different LLM providers.
"""
import logging
from functools import lru_cache
from typing import Any

import tiktoken

from .base import Message, ProviderType

logger = logging.getLogger("sentinel.llm")


# Model to tokenizer mapping
MODEL_TOKENIZERS = {
    # OpenAI models
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "gpt-4-turbo": "cl100k_base",
    "gpt-4": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
    
    # Claude models (approximation using cl100k)
    "claude-opus-4-5": "cl100k_base",
    "claude-sonnet-4": "cl100k_base",
    "claude-3-opus": "cl100k_base",
    "claude-3-sonnet": "cl100k_base",
    "claude-3-haiku": "cl100k_base",
    
    # Gemini models
    "gemini-2.0-flash": "cl100k_base",
    "gemini-1.5-pro": "cl100k_base",
    
    # Groq/Llama models
    "llama-3.3-70b-versatile": "cl100k_base",
    "llama-3.1-70b-versatile": "cl100k_base",
    "llama-3.1-8b-instant": "cl100k_base",
    "mixtral-8x7b-32768": "cl100k_base",
}

# Provider context windows
PROVIDER_CONTEXT_WINDOWS = {
    ProviderType.GROQ: 131072,  # 128K for Llama 3.3
    ProviderType.OLLAMA: 128000,  # Depends on model
    ProviderType.OPENAI: 128000,  # GPT-4o
    ProviderType.ANTHROPIC: 200000,  # Claude 3
    ProviderType.GEMINI: 1000000,  # Gemini 1.5
    ProviderType.GROK: 128000,
    ProviderType.TOGETHER: 128000,
    ProviderType.OPENROUTER: 128000,
}


@lru_cache(maxsize=16)
def get_tokenizer(encoding_name: str = "cl100k_base") -> tiktoken.Encoding:
    """Get a cached tokenizer instance."""
    return tiktoken.get_encoding(encoding_name)


class TokenManager:
    """
    Manages tokenization and context window for LLM prompts.
    
    Provides utilities for:
    - Counting tokens in messages
    - Truncating prompts to fit context windows
    - Managing system prompts
    - Optimizing prompt construction
    """
    
    def __init__(
        self,
        model: str = "gpt-4o",
        max_context_tokens: int | None = None,
        reserve_output_tokens: int = 4096,
    ):
        """
        Initialize the token manager.
        
        Args:
            model: Model name for tokenizer selection
            max_context_tokens: Maximum context window size
            reserve_output_tokens: Tokens to reserve for output
        """
        self.model = model
        self.encoding_name = MODEL_TOKENIZERS.get(model, "cl100k_base")
        self.tokenizer = get_tokenizer(self.encoding_name)
        self.max_context_tokens = max_context_tokens or 128000
        self.reserve_output_tokens = reserve_output_tokens
    
    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text string."""
        return len(self.tokenizer.encode(text))
    
    def count_message_tokens(self, message: Message) -> int:
        """
        Count tokens in a message including role overhead.
        
        Most chat models add ~4 tokens per message for formatting.
        """
        tokens = self.count_tokens(message.content)
        tokens += self.count_tokens(message.role)
        tokens += 4  # Formatting overhead
        if message.name:
            tokens += self.count_tokens(message.name) + 1
        return tokens
    
    def count_messages_tokens(self, messages: list[Message]) -> int:
        """Count total tokens across all messages."""
        total = 3  # Base overhead for message format
        for msg in messages:
            total += self.count_message_tokens(msg)
        return total
    
    def truncate_to_fit(
        self,
        messages: list[Message],
        max_tokens: int | None = None,
    ) -> list[Message]:
        """
        Truncate messages to fit within the context window.
        
        Strategy:
        1. Always keep the system message (first message)
        2. Always keep the latest user message
        3. Trim older messages from the middle
        
        Args:
            messages: List of messages to potentially truncate
            max_tokens: Maximum tokens allowed (defaults to context - output reserve)
            
        Returns:
            Truncated list of messages that fits the context window
        """
        if not messages:
            return []
        
        max_tokens = max_tokens or (self.max_context_tokens - self.reserve_output_tokens)
        
        # Check if already fits
        if self.count_messages_tokens(messages) <= max_tokens:
            return messages
        
        # Separate system message and conversation
        system_msg = None
        conversation = []
        
        for msg in messages:
            if msg.role == "system" and system_msg is None:
                system_msg = msg
            else:
                conversation.append(msg)
        
        # Calculate token budget
        system_tokens = self.count_message_tokens(system_msg) if system_msg else 0
        available_tokens = max_tokens - system_tokens
        
        # Keep messages from the end (most recent)
        kept_messages: list[Message] = []
        current_tokens = 0
        
        for msg in reversed(conversation):
            msg_tokens = self.count_message_tokens(msg)
            if current_tokens + msg_tokens <= available_tokens:
                kept_messages.insert(0, msg)
                current_tokens += msg_tokens
            else:
                break
        
        # Reconstruct message list
        result = []
        if system_msg:
            result.append(system_msg)
        result.extend(kept_messages)
        
        logger.debug(
            f"Truncated messages from {len(messages)} to {len(result)} "
            f"({self.count_messages_tokens(result)} tokens)"
        )
        
        return result
    
    def truncate_text(self, text: str, max_tokens: int) -> str:
        """Truncate text to a maximum number of tokens."""
        tokens = self.tokenizer.encode(text)
        if len(tokens) <= max_tokens:
            return text
        
        truncated_tokens = tokens[:max_tokens]
        return self.tokenizer.decode(truncated_tokens)


# =============================================================================
# SYSTEM PROMPTS
# =============================================================================

SENTINEL_SYSTEM_PROMPT = """You are The Sentinel, an autonomous quantitative financial analyst.

## Core Identity
You operate at the intersection of rigorous software engineering and quantitative finance. 
You are tasked with analyzing financial data, SEC filings, and market conditions to identify 
investment opportunities aligned with the "Pattaasu" methodology.

## Pattaasu Investment Criteria
1. **Zero Debt**: Debt-to-Equity ratio must be < 1.0, preferably near zero
2. **No Promoter Pledging**: Promoter pledging percentage must be 0%
3. **Positive Cash Flow**: Free Cash Flow must be positive for trailing 3 years
4. **Branding Power**: Company must demonstrate pricing power and competitive moat

## Analytical Framework
- Treat all input data as potentially noisy until verified
- Use precise decimal calculations for financial metrics
- Always cite sources when extracting data from documents
- Flag uncertainties with confidence levels

## Response Format
For financial analysis, structure responses as:
1. Executive Summary
2. Key Metrics (with citations)
3. Risk Assessment
4. Investment Thesis (Buy/Hold/Sell)
5. Confidence Level (High/Medium/Low)

When extracting data, use JSON format:
```json
{
  "metric_name": "value",
  "source": "document section",
  "confidence": "high|medium|low"
}
```
"""

FINANCIAL_EXTRACTION_PROMPT = """Extract the following financial metrics from the provided document.
Output in strict JSON format with source citations.

Required fields:
- revenue: Annual revenue (most recent fiscal year)
- net_income: Net income
- total_debt: Total debt (short-term + long-term)
- total_equity: Total shareholders' equity
- free_cash_flow: Free cash flow
- debt_to_equity: Calculated D/E ratio
- promoter_pledging_pct: Percentage of promoter shares pledged (if available)

For each field, include:
- value: The numeric value
- unit: Currency or percentage
- source: Document section where found
- confidence: high/medium/low

If a field cannot be found, set value to null and explain in a "note" field.
"""


def get_system_prompt(task_type: str = "general") -> str:
    """Get the appropriate system prompt for a task type."""
    prompts: dict[str, str] = {
        "general": SENTINEL_SYSTEM_PROMPT,
        "extraction": FINANCIAL_EXTRACTION_PROMPT,
    }
    return prompts.get(task_type, SENTINEL_SYSTEM_PROMPT)
