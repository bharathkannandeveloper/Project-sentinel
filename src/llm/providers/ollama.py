"""
Ollama LLM Provider (Local LLMs)

Supports running local models via Ollama server.
No API key required - just needs Ollama running locally.
"""
import logging
import time
from typing import Any, AsyncIterator

import httpx

from ..base import LLMProvider, LLMResponse, Message, ModelInfo, ProviderType
from ..config import get_llm_config

logger = logging.getLogger("sentinel.llm.ollama")


class OllamaProvider(LLMProvider):
    """
    Ollama provider for local LLM inference.
    
    Connects to a locally running Ollama server to run models
    like Llama, Mistral, Phi, and others without API keys.
    """
    
    provider_type = ProviderType.OLLAMA
    
    def __init__(self) -> None:
        """Initialize the Ollama provider."""
        config = get_llm_config()
        provider_config = config.get_provider_config(ProviderType.OLLAMA)
        
        self.base_url = provider_config.base_url or "http://localhost:11434"
        self._default_model = provider_config.default_model or "llama3.1:8b"
        self.timeout = provider_config.timeout or 120.0  # Longer timeout for local inference
        
        self._client: httpx.AsyncClient | None = None
        self._is_available: bool | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client
    
    @property
    def default_model(self) -> str:
        """Return the default model."""
        return self._default_model
    
    @property
    def is_available(self) -> bool:
        """Check if Ollama server is reachable."""
        # Can't do async check here, so return True and let health_check validate
        return True
    
    async def complete(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion using Ollama API."""
        model = model or self._default_model
        client = await self._get_client()
        
        start_time = time.perf_counter()
        
        # Convert messages to Ollama format
        ollama_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
        
        payload = {
            "model": model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if stop:
            payload["options"]["stop"] = stop
        
        try:
            response = await client.post("/api/chat", json=payload)
            
            # Handle Model Not Found (404) by falling back to first available model
            if response.status_code == 404:
                logger.warning(f"Model {model} not found. Attempting to find available models...")
                available = await self.list_models()
                if available:
                    fallback_model = available[0].id
                    logger.info(f"Falling back to model: {fallback_model}")
                    payload["model"] = fallback_model
                    response = await client.post("/api/chat", json=payload)
                    # Update default for this session to avoid repeated lookups
                    self._default_model = fallback_model
            
            response.raise_for_status()
            data = response.json()
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            return LLMResponse(
                content=data.get("message", {}).get("content", ""),
                model=data.get("model", model),
                provider=ProviderType.OLLAMA,
                finish_reason=data.get("done_reason", "stop"),
                prompt_tokens=data.get("prompt_eval_count", 0),
                completion_tokens=data.get("eval_count", 0),
                total_tokens=data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                latency_ms=latency_ms,
                raw_response=data,
            )
        except httpx.ConnectError:
            logger.error("Cannot connect to Ollama server. Is it running?")
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Make sure Ollama is running: `ollama serve`"
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama API error: {e.response.status_code}")
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
        """Stream a completion using Ollama API."""
        model = model or self._default_model
        client = await self._get_client()
        
        ollama_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
        
        payload = {
            "model": model,
            "messages": ollama_messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if stop:
            payload["options"]["stop"] = stop
        
        try:
            async with client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    
                    import json
                    try:
                        data = json.loads(line)
                        if content := data.get("message", {}).get("content"):
                            yield content
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
        except httpx.ConnectError:
            raise ConnectionError(f"Cannot connect to Ollama at {self.base_url}")
    
    async def list_models(self) -> list[ModelInfo]:
        """List available models from Ollama."""
        client = await self._get_client()
        
        try:
            response = await client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            
            models = []
            for model_data in data.get("models", []):
                name = model_data.get("name", "")
                
                # Parse model details
                details = model_data.get("details", {})
                
                models.append(ModelInfo(
                    id=name,
                    name=name,
                    provider=ProviderType.OLLAMA,
                    context_length=details.get("context_length", 4096),
                    supports_streaming=True,
                    description=f"Size: {model_data.get('size', 'unknown')}",
                ))
            
            return models
        except httpx.ConnectError:
            logger.warning("Ollama not available")
            return []
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []
    
    async def pull_model(self, model: str) -> bool:
        """Pull a model from Ollama library."""
        client = await self._get_client()
        
        try:
            response = await client.post(
                "/api/pull",
                json={"name": model},
                timeout=None,  # Pulling can take a while
            )
            response.raise_for_status()
            logger.info(f"Successfully pulled model: {model}")
            return True
        except Exception as e:
            logger.error(f"Failed to pull model {model}: {e}")
            return False
    
    async def validate_api_key(self) -> bool:
        """Ollama doesn't need an API key - check if server is reachable."""
        return await self.health_check()
    
    async def health_check(self) -> bool:
        """Check if Ollama server is responsive."""
        client = await self._get_client()
        
        try:
            response = await client.get("/api/tags", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
