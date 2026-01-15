"""
Groq LLM Provider (Default)

High-speed inference using Groq's custom LPU hardware.
Supports Llama, Mixtral, and other open models.
"""
import logging
import time
from typing import Any, AsyncIterator

import httpx

from ..base import LLMProvider, LLMResponse, Message, ModelInfo, ProviderType
from ..config import get_llm_config

logger = logging.getLogger("sentinel.llm.groq")


# Groq model definitions
GROQ_MODELS = {
    "llama-3.3-70b-versatile": ModelInfo(
        id="llama-3.3-70b-versatile",
        name="Llama 3.3 70B Versatile",
        provider=ProviderType.GROQ,
        context_length=131072,
        max_output_tokens=32768,
        supports_streaming=True,
        supports_function_calling=True,
        description="Latest and most capable Llama model with 128K context",
    ),
    "llama-3.1-70b-versatile": ModelInfo(
        id="llama-3.1-70b-versatile",
        name="Llama 3.1 70B Versatile",
        provider=ProviderType.GROQ,
        context_length=131072,
        max_output_tokens=32768,
        supports_streaming=True,
        supports_function_calling=True,
        description="Powerful Llama 3.1 with extended context",
    ),
    "llama-3.1-8b-instant": ModelInfo(
        id="llama-3.1-8b-instant",
        name="Llama 3.1 8B Instant",
        provider=ProviderType.GROQ,
        context_length=131072,
        max_output_tokens=8192,
        supports_streaming=True,
        description="Fast, efficient model for quick tasks",
    ),
    "mixtral-8x7b-32768": ModelInfo(
        id="mixtral-8x7b-32768",
        name="Mixtral 8x7B",
        provider=ProviderType.GROQ,
        context_length=32768,
        max_output_tokens=32768,
        supports_streaming=True,
        description="Mixture of experts model",
    ),
    "gemma2-9b-it": ModelInfo(
        id="gemma2-9b-it",
        name="Gemma 2 9B IT",
        provider=ProviderType.GROQ,
        context_length=8192,
        max_output_tokens=8192,
        supports_streaming=True,
        description="Google's Gemma 2 instruction-tuned",
    ),
}


class GroqProvider(LLMProvider):
    """
    Groq LLM provider for high-speed inference.
    
    Uses Groq's OpenAI-compatible API with their custom LPU hardware
    for ultra-fast inference on open models like Llama and Mixtral.
    """
    
    provider_type = ProviderType.GROQ
    
    def __init__(self) -> None:
        """Initialize the Groq provider."""
        config = get_llm_config()
        provider_config = config.get_provider_config(ProviderType.GROQ)
        
        self.api_key = provider_config.api_key
        self.base_url = provider_config.base_url or "https://api.groq.com/openai/v1"
        self._default_model = provider_config.default_model or "llama-3.3-70b-versatile"
        self.timeout = provider_config.timeout
        
        self._client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client
    
    @property
    def default_model(self) -> str:
        """Return the default model."""
        return self._default_model
    
    @property
    def is_available(self) -> bool:
        """Check if provider is configured."""
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
        """Generate a completion using Groq API."""
        model = model or self._default_model
        client = await self._get_client()
        
        start_time = time.perf_counter()
        
        payload = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if stop:
            payload["stop"] = stop
        
        try:
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            choice = data["choices"][0]
            usage = data.get("usage", {})
            
            return LLMResponse(
                content=choice["message"]["content"],
                model=data.get("model", model),
                provider=ProviderType.GROQ,
                finish_reason=choice.get("finish_reason", "stop"),
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                latency_ms=latency_ms,
                raw_response=data,
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"Groq API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Groq request failed: {e}")
            raise
    
    async def stream(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a completion using Groq API."""
        model = model or self._default_model
        client = await self._get_client()
        
        payload = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if stop:
            payload["stop"] = stop
        
        try:
            async with client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        
                        import json
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0].get("delta", {})
                            if content := delta.get("content"):
                                yield content
                        except json.JSONDecodeError:
                            continue
        except httpx.HTTPStatusError as e:
            logger.error(f"Groq streaming error: {e.response.status_code}")
            raise
    
    async def list_models(self) -> list[ModelInfo]:
        """List available models from Groq API."""
        if not self.is_available:
            return []
        
        client = await self._get_client()
        
        try:
            response = await client.get("/models")
            response.raise_for_status()
            data = response.json()
            
            models = []
            for model_data in data.get("data", []):
                model_id = model_data.get("id", "")
                
                # Use predefined info if available
                if model_id in GROQ_MODELS:
                    models.append(GROQ_MODELS[model_id])
                else:
                    # Create basic model info for unknown models
                    models.append(ModelInfo(
                        id=model_id,
                        name=model_id,
                        provider=ProviderType.GROQ,
                        context_length=model_data.get("context_window", 4096),
                    ))
            
            return models
        except Exception as e:
            logger.error(f"Failed to list Groq models: {e}")
            return list(GROQ_MODELS.values())
    
    async def validate_api_key(self) -> bool:
        """Validate the API key by listing models."""
        if not self.api_key:
            return False
        
        try:
            models = await self.list_models()
            return len(models) > 0
        except Exception:
            return False
    
    async def health_check(self) -> bool:
        """Check if Groq API is responsive."""
        return await self.validate_api_key()
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
