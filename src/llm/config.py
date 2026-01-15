"""
LLM Configuration Management

Handles loading API keys, setting defaults, and managing provider configuration.
"""
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv

from .base import ProviderType

# Load environment variables
load_dotenv()


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""
    enabled: bool = False
    api_key: str | None = None
    base_url: str | None = None
    default_model: str | None = None
    timeout: float = 60.0
    max_retries: int = 3
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMConfig:
    """
    Complete LLM configuration with all providers.
    
    Manages provider priority, fallback chains, and global settings.
    """
    default_provider: ProviderType = ProviderType.GROQ
    fallback_provider: ProviderType = ProviderType.OLLAMA
    
    # Global settings
    default_temperature: float = 0.7
    default_max_tokens: int = 4096
    request_timeout: float = 60.0
    
    # Provider-specific configurations
    providers: dict[ProviderType, ProviderConfig] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Initialize provider configurations from environment."""
        self._load_from_environment()
    
    def _load_from_environment(self) -> None:
        """Load provider configurations from environment variables."""
        
        # Groq Configuration
        groq_key = os.getenv("GROQ_API_KEY")
        self.providers[ProviderType.GROQ] = ProviderConfig(
            enabled=bool(groq_key),
            api_key=groq_key,
            base_url="https://api.groq.com/openai/v1",
            default_model="llama-3.3-70b-versatile",
        )
        
        # Ollama Configuration (no API key needed, but requires Ollama running)
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.providers[ProviderType.OLLAMA] = ProviderConfig(
            enabled=False,  # Disabled by default - will be enabled by health check
            base_url=ollama_url,
            default_model="llama3.1:8b",
        )
        
        # OpenAI Configuration
        openai_key = os.getenv("OPENAI_API_KEY")
        self.providers[ProviderType.OPENAI] = ProviderConfig(
            enabled=bool(openai_key),
            api_key=openai_key,
            default_model="gpt-4o",
        )
        
        # Anthropic Configuration
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.providers[ProviderType.ANTHROPIC] = ProviderConfig(
            enabled=bool(anthropic_key),
            api_key=anthropic_key,
            default_model="claude-opus-4-5-20250220",
            extra={"high_effort": True},  # Enable high-effort reasoning
        )
        
        # Google Gemini Configuration
        gemini_key = os.getenv("GOOGLE_API_KEY")
        self.providers[ProviderType.GEMINI] = ProviderConfig(
            enabled=bool(gemini_key),
            api_key=gemini_key,
            default_model="gemini-2.0-flash",
        )
        
        # xAI Grok Configuration
        grok_key = os.getenv("GROK_API_KEY")
        self.providers[ProviderType.GROK] = ProviderConfig(
            enabled=bool(grok_key),
            api_key=grok_key,
            base_url="https://api.x.ai/v1",
            default_model="grok-2",
        )
        
        # Together AI Configuration
        together_key = os.getenv("TOGETHER_API_KEY")
        self.providers[ProviderType.TOGETHER] = ProviderConfig(
            enabled=bool(together_key),
            api_key=together_key,
            base_url="https://api.together.xyz/v1",
            default_model="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        )
        
        # OpenRouter Configuration
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self.providers[ProviderType.OPENROUTER] = ProviderConfig(
            enabled=bool(openrouter_key),
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
            default_model="anthropic/claude-3.5-sonnet",
        )
    
    def get_provider_config(self, provider: ProviderType) -> ProviderConfig:
        """Get configuration for a specific provider."""
        return self.providers.get(provider, ProviderConfig())
    
    def get_enabled_providers(self) -> list[ProviderType]:
        """Get list of enabled providers."""
        return [
            provider
            for provider, config in self.providers.items()
            if config.enabled
        ]
    
    def get_fallback_chain(self) -> list[ProviderType]:
        """
        Get the provider fallback chain.
        
        Returns providers in priority order for automatic failover.
        """
        chain = []
        
        # Start with default provider
        if self.default_provider in self.providers:
            chain.append(self.default_provider)
        
        # Add fallback provider
        if self.fallback_provider != self.default_provider:
            chain.append(self.fallback_provider)
        
        # Add remaining enabled providers
        for provider in self.get_enabled_providers():
            if provider not in chain:
                chain.append(provider)
        
        return chain


@lru_cache(maxsize=1)
def get_llm_config() -> LLMConfig:
    """
    Get the global LLM configuration (cached singleton).
    
    Returns:
        LLMConfig instance with all provider configurations
    """
    # Override default provider if specified in environment
    default_provider_str = os.getenv("DEFAULT_LLM_PROVIDER", "groq")
    fallback_provider_str = os.getenv("FALLBACK_LLM_PROVIDER", "ollama")
    
    try:
        default_provider = ProviderType(default_provider_str.lower())
    except ValueError:
        default_provider = ProviderType.GROQ
    
    try:
        fallback_provider = ProviderType(fallback_provider_str.lower())
    except ValueError:
        fallback_provider = ProviderType.OLLAMA
    
    return LLMConfig(
        default_provider=default_provider,
        fallback_provider=fallback_provider,
    )


def clear_config_cache() -> None:
    """Clear the configuration cache (useful for testing)."""
    get_llm_config.cache_clear()
