"""
LLM Provider Module

This module provides a unified interface for multiple LLM providers:
- Groq (default, high-speed inference)
- Ollama (local LLMs)
- OpenAI
- Anthropic (Claude)
- Google Gemini
- xAI Grok
- Together AI
- OpenRouter

Usage:
    from src.llm import LLMManager
    
    manager = LLMManager()
    response = await manager.complete("Analyze this financial data...")
    
    # Stream responses
    async for chunk in manager.stream("Generate analysis..."):
        print(chunk, end="")
"""

from .base import LLMProvider, LLMResponse, ModelInfo
from .config import LLMConfig, get_llm_config
from .manager import LLMManager
from .tokenizer import TokenManager

__all__ = [
    "LLMProvider",
    "LLMResponse",
    "ModelInfo",
    "LLMConfig",
    "get_llm_config",
    "LLMManager",
    "TokenManager",
]
