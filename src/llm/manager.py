"""
LLM Provider Manager

Orchestrates multiple LLM providers with automatic fallback,
load balancing, and health monitoring.
"""
import asyncio
import logging
from typing import Any, AsyncIterator

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .base import LLMProvider, LLMResponse, Message, ModelInfo, ProviderType
from .config import get_llm_config, LLMConfig
from .providers import (
    GroqProvider,
    OllamaProvider,
    OpenAIProvider,
    AnthropicProvider,
    GeminiProvider,
    GrokProvider,
    TogetherProvider,
    OpenRouterProvider,
)

logger = logging.getLogger("sentinel.llm.manager")


# Provider class mapping
PROVIDER_CLASSES: dict[ProviderType, type[LLMProvider]] = {
    ProviderType.GROQ: GroqProvider,
    ProviderType.OLLAMA: OllamaProvider,
    ProviderType.OPENAI: OpenAIProvider,
    ProviderType.ANTHROPIC: AnthropicProvider,
    ProviderType.GEMINI: GeminiProvider,
    ProviderType.GROK: GrokProvider,
    ProviderType.TOGETHER: TogetherProvider,
    ProviderType.OPENROUTER: OpenRouterProvider,
}


class LLMManager:
    """
    Unified LLM provider manager.
    
    Handles:
    - Provider initialization and caching
    - Automatic fallback on failures
    - Health monitoring
    - Dynamic model discovery
    
    Usage:
        manager = LLMManager()
        
        # Simple completion
        response = await manager.complete("Analyze this stock...")
        
        # Streaming
        async for chunk in manager.stream("Generate analysis..."):
            print(chunk, end="")
        
        # Specific provider
        response = await manager.complete("...", provider=ProviderType.ANTHROPIC)
    """
    
    def __init__(self, config: LLMConfig | None = None) -> None:
        """
        Initialize the LLM manager.
        
        Args:
            config: Optional configuration override
        """
        self.config = config or get_llm_config()
        self._providers: dict[ProviderType, LLMProvider] = {}
        self._health_status: dict[ProviderType, bool] = {}
    
    def _get_provider(self, provider_type: ProviderType) -> LLMProvider:
        """Get or create a provider instance."""
        if provider_type not in self._providers:
            if provider_type not in PROVIDER_CLASSES:
                raise ValueError(f"Unknown provider: {provider_type}")
            
            self._providers[provider_type] = PROVIDER_CLASSES[provider_type]()
        
        return self._providers[provider_type]
    
    async def health_check(self, provider_type: ProviderType) -> bool:
        """Check health of a specific provider."""
        try:
            provider = self._get_provider(provider_type)
            is_healthy = await provider.health_check()
            self._health_status[provider_type] = is_healthy
            return is_healthy
        except Exception as e:
            logger.warning(f"Health check failed for {provider_type}: {e}")
            self._health_status[provider_type] = False
            return False
    
    async def check_all_providers(self) -> dict[ProviderType, bool]:
        """Check health of all configured providers."""
        tasks = []
        providers = []
        
        for provider_type in self.config.get_fallback_chain():
            provider_config = self.config.get_provider_config(provider_type)
            if provider_config.enabled:
                providers.append(provider_type)
                tasks.append(self.health_check(provider_type))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            provider: result if isinstance(result, bool) else False
            for provider, result in zip(providers, results)
        }
    
    async def list_all_models(self) -> dict[ProviderType, list[ModelInfo]]:
        """List models from all available providers."""
        all_models: dict[ProviderType, list[ModelInfo]] = {}
        
        for provider_type in self.config.get_enabled_providers():
            try:
                provider = self._get_provider(provider_type)
                if provider.is_available:
                    models = await provider.list_models()
                    all_models[provider_type] = models
            except Exception as e:
                logger.warning(f"Failed to list models from {provider_type}: {e}")
        
        return all_models

    async def get_models_for_provider(self, provider_type: ProviderType) -> list[ModelInfo]:
        """List models for a specific provider."""
        try:
            # Check availability directly first
            provider = self._get_provider(provider_type)
            # Even if not 'enabled' in config, if configured, try to list.
            if provider.is_available:
                return await provider.list_models()
            else:
                logger.warning(f"Provider {provider_type} is not available")
                return []
        except Exception as e:
            logger.error(f"Failed to list models for {provider_type}: {e}")
            return []
    
    def _select_provider(
        self,
        preferred: ProviderType | None = None,
    ) -> ProviderType:
        """Select the best available provider."""
        if preferred:
            provider_config = self.config.get_provider_config(preferred)
            if provider_config.enabled:
                return preferred
        
        # Use fallback chain
        for provider_type in self.config.get_fallback_chain():
            provider_config = self.config.get_provider_config(provider_type)
            if provider_config.enabled:
                # Check cached health status
                if self._health_status.get(provider_type, True):
                    return provider_type
        
        # Default to primary provider
        return self.config.default_provider
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True,
    )
    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        provider: ProviderType | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        messages: list[Message] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate a completion with automatic fallback.
        
        Args:
            prompt: User prompt (ignored if messages provided)
            system_prompt: Optional system prompt
            provider: Preferred provider (uses default if not specified)
            model: Model to use (uses provider default if not specified)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            messages: Optional pre-built message list
            **kwargs: Provider-specific parameters
            
        Returns:
            LLMResponse with the completion
        """
        # Build message list if not provided
        if messages is None:
            messages = []
            if system_prompt:
                messages.append(Message(role="system", content=system_prompt))
            messages.append(Message(role="user", content=prompt))
        
        # Try providers in order
        fallback_chain = self.config.get_fallback_chain()
        
        if provider:
            # Move preferred provider to front
            if provider in fallback_chain:
                fallback_chain.remove(provider)
            fallback_chain = [provider] + fallback_chain
        
        last_error: Exception | None = None
        
        for provider_type in fallback_chain:
            try:
                provider_instance = self._get_provider(provider_type)
                
                if not provider_instance.is_available:
                    continue
                
                logger.debug(f"Trying provider: {provider_type}")
                
                response = await provider_instance.complete(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                
                self._health_status[provider_type] = True
                return response
                
            except Exception as e:
                logger.warning(f"Provider {provider_type} failed: {e}")
                self._health_status[provider_type] = False
                last_error = e
                continue
        
        raise last_error or RuntimeError("No providers available")
    
    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        provider: ProviderType | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        messages: list[Message] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        Stream a completion with automatic fallback.
        
        Note: Fallback only occurs before streaming starts.
        If streaming fails mid-response, the error is raised.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            provider: Preferred provider
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            messages: Optional pre-built message list
            **kwargs: Provider-specific parameters
            
        Yields:
            String chunks as they are generated
        """
        if messages is None:
            messages = []
            if system_prompt:
                messages.append(Message(role="system", content=system_prompt))
            messages.append(Message(role="user", content=prompt))
        
        fallback_chain = self.config.get_fallback_chain()
        
        if provider:
            if provider in fallback_chain:
                fallback_chain.remove(provider)
            fallback_chain = [provider] + fallback_chain
        
        last_error: Exception | None = None
        
        for provider_type in fallback_chain:
            try:
                provider_instance = self._get_provider(provider_type)
                
                if not provider_instance.is_available:
                    continue
                
                logger.debug(f"Streaming from: {provider_type}")
                
                async for chunk in provider_instance.stream(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                ):
                    yield chunk
                
                self._health_status[provider_type] = True
                return
                
            except Exception as e:
                logger.warning(f"Stream provider {provider_type} failed: {e}")
                self._health_status[provider_type] = False
                last_error = e
                continue
        
        raise last_error or RuntimeError("No providers available for streaming")
    
    async def analyze_financial_data(
        self,
        data: str,
        analysis_type: str = "general",
        provider: ProviderType | None = None,
    ) -> LLMResponse:
        """
        Specialized method for financial data analysis.
        
        Uses the Sentinel system prompt optimized for financial analysis.
        Prefers Anthropic (Claude Opus 4.5) for high-effort reasoning.
        
        Args:
            data: Financial data to analyze
            analysis_type: Type of analysis ("general", "extraction", "risk")
            provider: Override provider selection
            
        Returns:
            LLMResponse with financial analysis
        """
        from .tokenizer import SENTINEL_SYSTEM_PROMPT, FINANCIAL_EXTRACTION_PROMPT
        
        # Select appropriate system prompt
        if analysis_type == "extraction":
            system_prompt = FINANCIAL_EXTRACTION_PROMPT
        else:
            system_prompt = SENTINEL_SYSTEM_PROMPT
        
        # Prefer Claude for complex financial analysis
        if provider is None and self.config.get_provider_config(ProviderType.ANTHROPIC).enabled:
            provider = ProviderType.ANTHROPIC
        
        return await self.complete(
            prompt=data,
            system_prompt=system_prompt,
            provider=provider,
            temperature=0.3,  # Lower temperature for precision
            max_tokens=8192,
        )
    
    async def close(self) -> None:
        """Close all provider connections."""
        for provider in self._providers.values():
            if hasattr(provider, 'close'):
                await provider.close()
        self._providers.clear()
    
    async def __aenter__(self) -> "LLMManager":
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()
