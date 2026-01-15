"""
Together AI LLM Provider

Access to open-source models with high-speed inference.
"""
import logging
import time
from typing import Any, AsyncIterator

import httpx

from ..base import LLMProvider, LLMResponse, Message, ModelInfo, ProviderType
from ..config import get_llm_config

logger = logging.getLogger("sentinel.llm.together")


TOGETHER_MODELS = {
    "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo": ModelInfo(
        id="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        name="Llama 3.1 70B Turbo",
        provider=ProviderType.TOGETHER,
        context_length=131072,
        supports_streaming=True,
    ),
    "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo": ModelInfo(
        id="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        name="Llama 3.1 8B Turbo",
        provider=ProviderType.TOGETHER,
        context_length=131072,
        supports_streaming=True,
    ),
    "mistralai/Mixtral-8x7B-Instruct-v0.1": ModelInfo(
        id="mistralai/Mixtral-8x7B-Instruct-v0.1",
        name="Mixtral 8x7B",
        provider=ProviderType.TOGETHER,
        context_length=32768,
        supports_streaming=True,
    ),
}


class TogetherProvider(LLMProvider):
    """
    Together AI LLM provider.
    
    OpenAI-compatible API for open-source models.
    """
    
    provider_type = ProviderType.TOGETHER
    
    def __init__(self) -> None:
        config = get_llm_config()
        provider_config = config.get_provider_config(ProviderType.TOGETHER)
        
        self.api_key = provider_config.api_key
        self.base_url = provider_config.base_url or "https://api.together.xyz/v1"
        self._default_model = provider_config.default_model or "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"
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
            provider=ProviderType.TOGETHER,
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
                if model_id in TOGETHER_MODELS:
                    models.append(TOGETHER_MODELS[model_id])
                else:
                    models.append(ModelInfo(
                        id=model_id,
                        name=model_id.split("/")[-1] if "/" in model_id else model_id,
                        provider=ProviderType.TOGETHER,
                    ))
            return models
        except Exception as e:
            logger.error(f"Failed to list Together models: {e}")
            return list(TOGETHER_MODELS.values())
    
    async def validate_api_key(self) -> bool:
        if not self.api_key:
            return False
        try:
            models = await self.list_models()
            return len(models) > 0
        except Exception:
            return False
    
    async def health_check(self) -> bool:
        return await self.validate_api_key()
    
    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
