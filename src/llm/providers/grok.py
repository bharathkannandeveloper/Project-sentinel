"""
xAI Grok LLM Provider

Access to Grok models with real-time information.
"""
import logging
import time
from typing import Any, AsyncIterator

import httpx

from ..base import LLMProvider, LLMResponse, Message, ModelInfo, ProviderType
from ..config import get_llm_config

logger = logging.getLogger("sentinel.llm.grok")


GROK_MODELS = {
    "grok-2": ModelInfo(
        id="grok-2",
        name="Grok 2",
        provider=ProviderType.GROK,
        context_length=131072,
        max_output_tokens=8192,
        supports_streaming=True,
        description="Latest Grok model with reasoning",
    ),
    "grok-2-mini": ModelInfo(
        id="grok-2-mini",
        name="Grok 2 Mini",
        provider=ProviderType.GROK,
        context_length=131072,
        max_output_tokens=8192,
        supports_streaming=True,
        description="Fast and efficient Grok",
    ),
}


class GrokProvider(LLMProvider):
    """
    xAI Grok LLM provider.
    
    OpenAI-compatible API for Grok models.
    """
    
    provider_type = ProviderType.GROK
    
    def __init__(self) -> None:
        config = get_llm_config()
        provider_config = config.get_provider_config(ProviderType.GROK)
        
        self.api_key = provider_config.api_key
        self.base_url = provider_config.base_url or "https://api.x.ai/v1"
        self._default_model = provider_config.default_model or "grok-2"
        self.timeout = provider_config.timeout
        
        self._client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
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
        
        response = await client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        
        latency_ms = (time.perf_counter() - start_time) * 1000
        choice = data["choices"][0]
        usage = data.get("usage", {})
        
        return LLMResponse(
            content=choice["message"]["content"],
            model=data.get("model", model),
            provider=ProviderType.GROK,
            finish_reason=choice.get("finish_reason", "stop"),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency_ms=latency_ms,
            raw_response=data,
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
    
    async def list_models(self) -> list[ModelInfo]:
        return list(GROK_MODELS.values())
    
    async def validate_api_key(self) -> bool:
        if not self.api_key:
            return False
        try:
            client = await self._get_client()
            response = await client.get("/models")
            return response.status_code == 200
        except Exception:
            return False
    
    async def health_check(self) -> bool:
        return await self.validate_api_key()
    
    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
