"""
Anthropic Claude LLM Provider

Supports Claude 4.5 Opus with "High Effort" reasoning mode.
"""
import logging
import time
from typing import Any, AsyncIterator

from ..base import LLMProvider, LLMResponse, Message, ModelInfo, ProviderType
from ..config import get_llm_config

logger = logging.getLogger("sentinel.llm.anthropic")


ANTHROPIC_MODELS = {
    "claude-opus-4-5-20250220": ModelInfo(
        id="claude-opus-4-5-20250220",
        name="Claude 4.5 Opus",
        provider=ProviderType.ANTHROPIC,
        context_length=200000,
        max_output_tokens=32768,
        supports_streaming=True,
        supports_function_calling=True,
        description="Most capable Claude model with High Effort reasoning",
    ),
    "claude-sonnet-4-20250514": ModelInfo(
        id="claude-sonnet-4-20250514",
        name="Claude 4 Sonnet",
        provider=ProviderType.ANTHROPIC,
        context_length=200000,
        max_output_tokens=16384,
        supports_streaming=True,
        supports_function_calling=True,
        description="Balanced performance and speed",
    ),
    "claude-3-5-sonnet-20241022": ModelInfo(
        id="claude-3-5-sonnet-20241022",
        name="Claude 3.5 Sonnet",
        provider=ProviderType.ANTHROPIC,
        context_length=200000,
        max_output_tokens=8192,
        supports_streaming=True,
        supports_function_calling=True,
        description="Latest 3.5 Sonnet",
    ),
    "claude-3-haiku-20240307": ModelInfo(
        id="claude-3-haiku-20240307",
        name="Claude 3 Haiku",
        provider=ProviderType.ANTHROPIC,
        context_length=200000,
        max_output_tokens=4096,
        supports_streaming=True,
        description="Fastest Claude model",
    ),
}


class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude LLM provider.
    
    Uses the official Anthropic Python SDK. Supports Claude's
    unique features including extended thinking (High Effort mode).
    """
    
    provider_type = ProviderType.ANTHROPIC
    
    def __init__(self) -> None:
        """Initialize the Anthropic provider."""
        config = get_llm_config()
        provider_config = config.get_provider_config(ProviderType.ANTHROPIC)
        
        self.api_key = provider_config.api_key
        self._default_model = provider_config.default_model or "claude-opus-4-5-20250220"
        self.high_effort = provider_config.extra.get("high_effort", True)
        
        self._client = None
    
    async def _get_client(self):
        """Get or create the Anthropic client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic package required: pip install anthropic")
        return self._client
    
    @property
    def default_model(self) -> str:
        return self._default_model
    
    @property
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    async def complete(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion using Anthropic API."""
        model = model or self._default_model
        client = await self._get_client()
        
        start_time = time.perf_counter()
        
        # Separate system message from conversation
        system_msg = None
        conversation = []
        
        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            else:
                conversation.append({"role": msg.role, "content": msg.content})
        
        # Build request parameters
        request_params = {
            "model": model,
            "messages": conversation,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        if system_msg:
            request_params["system"] = system_msg
        
        if stop:
            request_params["stop_sequences"] = stop
        
        # Enable extended thinking for High Effort mode on Opus 4.5
        if self.high_effort and "opus-4-5" in model:
            request_params["thinking"] = {
                "type": "enabled",
                "budget_tokens": 10000,  # Allow deep reasoning
            }
        
        response = await client.messages.create(**request_params)
        
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        # Extract content from response
        content = ""
        for block in response.content:
            if hasattr(block, 'text'):
                content += block.text
        
        return LLMResponse(
            content=content,
            model=response.model,
            provider=ProviderType.ANTHROPIC,
            finish_reason=response.stop_reason or "stop",
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            latency_ms=latency_ms,
            raw_response=response.model_dump() if hasattr(response, 'model_dump') else {},
        )
    
    async def stream(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a completion using Anthropic API."""
        model = model or self._default_model
        client = await self._get_client()
        
        system_msg = None
        conversation = []
        
        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            else:
                conversation.append({"role": msg.role, "content": msg.content})
        
        request_params = {
            "model": model,
            "messages": conversation,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        if system_msg:
            request_params["system"] = system_msg
        
        if stop:
            request_params["stop_sequences"] = stop
        
        async with client.messages.stream(**request_params) as stream:
            async for text in stream.text_stream:
                yield text
    
    async def list_models(self) -> list[ModelInfo]:
        """List available Claude models."""
        return list(ANTHROPIC_MODELS.values())
    
    async def validate_api_key(self) -> bool:
        """Validate the API key with a minimal request."""
        if not self.api_key:
            return False
        
        try:
            client = await self._get_client()
            await client.messages.create(
                model="claude-3-haiku-20240307",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False
    
    async def health_check(self) -> bool:
        return await self.validate_api_key()
