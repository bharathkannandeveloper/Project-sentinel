"""
OpenAI LLM Provider

Supports GPT-4o, GPT-4, GPT-3.5-turbo and other OpenAI models.
"""
import logging
import time
from typing import Any, AsyncIterator

from ..base import LLMProvider, LLMResponse, Message, ModelInfo, ProviderType
from ..config import get_llm_config

logger = logging.getLogger("sentinel.llm.openai")


OPENAI_MODELS = {
    "gpt-4o": ModelInfo(
        id="gpt-4o",
        name="GPT-4o",
        provider=ProviderType.OPENAI,
        context_length=128000,
        max_output_tokens=16384,
        supports_streaming=True,
        supports_function_calling=True,
        supports_vision=True,
        description="Most capable GPT-4 model, multimodal",
    ),
    "gpt-4o-mini": ModelInfo(
        id="gpt-4o-mini",
        name="GPT-4o Mini",
        provider=ProviderType.OPENAI,
        context_length=128000,
        max_output_tokens=16384,
        supports_streaming=True,
        supports_function_calling=True,
        supports_vision=True,
        description="Fast and efficient GPT-4 variant",
    ),
    "gpt-4-turbo": ModelInfo(
        id="gpt-4-turbo",
        name="GPT-4 Turbo",
        provider=ProviderType.OPENAI,
        context_length=128000,
        max_output_tokens=4096,
        supports_streaming=True,
        supports_function_calling=True,
        supports_vision=True,
        description="GPT-4 Turbo with vision",
    ),
    "gpt-3.5-turbo": ModelInfo(
        id="gpt-3.5-turbo",
        name="GPT-3.5 Turbo",
        provider=ProviderType.OPENAI,
        context_length=16385,
        max_output_tokens=4096,
        supports_streaming=True,
        supports_function_calling=True,
        description="Fast and cost-effective",
    ),
}


class OpenAIProvider(LLMProvider):
    """
    OpenAI LLM provider.
    
    Uses the official OpenAI Python SDK for API access.
    """
    
    provider_type = ProviderType.OPENAI
    
    def __init__(self) -> None:
        """Initialize the OpenAI provider."""
        config = get_llm_config()
        provider_config = config.get_provider_config(ProviderType.OPENAI)
        
        self.api_key = provider_config.api_key
        self._default_model = provider_config.default_model or "gpt-4o"
        
        self._client = None
    
    async def _get_client(self):
        """Get or create the OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai package required: pip install openai")
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
        """Generate a completion using OpenAI API."""
        model = model or self._default_model
        client = await self._get_client()
        
        start_time = time.perf_counter()
        
        response = await client.chat.completions.create(
            model=model,
            messages=[m.to_dict() for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
            **kwargs,
        )
        
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        choice = response.choices[0]
        
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            provider=ProviderType.OPENAI,
            finish_reason=choice.finish_reason or "stop",
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            total_tokens=response.usage.total_tokens if response.usage else 0,
            latency_ms=latency_ms,
            raw_response=response.model_dump(),
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
        """Stream a completion using OpenAI API."""
        model = model or self._default_model
        client = await self._get_client()
        
        stream = await client.chat.completions.create(
            model=model,
            messages=[m.to_dict() for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
            stream=True,
            **kwargs,
        )
        
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    async def list_models(self) -> list[ModelInfo]:
        """List available models from OpenAI."""
        if not self.is_available:
            return []
        
        client = await self._get_client()
        
        try:
            response = await client.models.list()
            
            models = []
            for model in response.data:
                if model.id in OPENAI_MODELS:
                    models.append(OPENAI_MODELS[model.id])
                elif model.id.startswith("gpt"):
                    models.append(ModelInfo(
                        id=model.id,
                        name=model.id,
                        provider=ProviderType.OPENAI,
                    ))
            
            return models if models else list(OPENAI_MODELS.values())
        except Exception as e:
            logger.error(f"Failed to list OpenAI models: {e}")
            return list(OPENAI_MODELS.values())
    
    async def validate_api_key(self) -> bool:
        """Validate the API key."""
        if not self.api_key:
            return False
        
        try:
            client = await self._get_client()
            await client.models.list()
            return True
        except Exception:
            return False
    
    async def health_check(self) -> bool:
        return await self.validate_api_key()
