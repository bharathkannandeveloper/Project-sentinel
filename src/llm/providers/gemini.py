"""
Google Gemini LLM Provider

Supports Gemini Pro, Ultra, and Flash models.
"""
import logging
import time
from typing import Any, AsyncIterator

from ..base import LLMProvider, LLMResponse, Message, ModelInfo, ProviderType
from ..config import get_llm_config

logger = logging.getLogger("sentinel.llm.gemini")


GEMINI_MODELS = {
    "gemini-2.0-flash": ModelInfo(
        id="gemini-2.0-flash",
        name="Gemini 2.0 Flash",
        provider=ProviderType.GEMINI,
        context_length=1000000,
        max_output_tokens=8192,
        supports_streaming=True,
        supports_vision=True,
        description="Latest Gemini with 1M context",
    ),
    "gemini-1.5-pro": ModelInfo(
        id="gemini-1.5-pro",
        name="Gemini 1.5 Pro",
        provider=ProviderType.GEMINI,
        context_length=2000000,
        max_output_tokens=8192,
        supports_streaming=True,
        supports_vision=True,
        description="Most capable Gemini with 2M context",
    ),
    "gemini-1.5-flash": ModelInfo(
        id="gemini-1.5-flash",
        name="Gemini 1.5 Flash",
        provider=ProviderType.GEMINI,
        context_length=1000000,
        max_output_tokens=8192,
        supports_streaming=True,
        supports_vision=True,
        description="Fast and efficient",
    ),
}


class GeminiProvider(LLMProvider):
    """
    Google Gemini LLM provider.
    
    Uses the Google Generative AI SDK.
    """
    
    provider_type = ProviderType.GEMINI
    
    def __init__(self) -> None:
        """Initialize the Gemini provider."""
        config = get_llm_config()
        provider_config = config.get_provider_config(ProviderType.GEMINI)
        
        self.api_key = provider_config.api_key
        self._default_model = provider_config.default_model or "gemini-2.0-flash"
        
        self._configured = False
    
    def _configure(self) -> None:
        """Configure the Gemini SDK."""
        if not self._configured and self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._configured = True
            except ImportError:
                raise ImportError("google-generativeai package required")
    
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
        """Generate a completion using Gemini API."""
        self._configure()
        import google.generativeai as genai
        
        model_name = model or self._default_model
        start_time = time.perf_counter()
        
        # Convert messages to Gemini format
        system_instruction = None
        history = []
        current_content = None
        
        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "user":
                current_content = msg.content
            elif msg.role == "assistant":
                history.append({"role": "model", "parts": [msg.content]})
        
        # Create model with system instruction
        gen_model = genai.GenerativeModel(
            model_name,
            system_instruction=system_instruction,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                stop_sequences=stop,
            ),
        )
        
        # Start chat with history
        chat = gen_model.start_chat(history=history)
        
        # Generate response
        response = await chat.send_message_async(current_content or "")
        
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        return LLMResponse(
            content=response.text,
            model=model_name,
            provider=ProviderType.GEMINI,
            finish_reason="stop",
            prompt_tokens=response.usage_metadata.prompt_token_count if response.usage_metadata else 0,
            completion_tokens=response.usage_metadata.candidates_token_count if response.usage_metadata else 0,
            total_tokens=response.usage_metadata.total_token_count if response.usage_metadata else 0,
            latency_ms=latency_ms,
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
        """Stream a completion using Gemini API."""
        self._configure()
        import google.generativeai as genai
        
        model_name = model or self._default_model
        
        system_instruction = None
        history = []
        current_content = None
        
        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "user":
                current_content = msg.content
            elif msg.role == "assistant":
                history.append({"role": "model", "parts": [msg.content]})
        
        gen_model = genai.GenerativeModel(
            model_name,
            system_instruction=system_instruction,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                stop_sequences=stop,
            ),
        )
        
        chat = gen_model.start_chat(history=history)
        
        response = await chat.send_message_async(current_content or "", stream=True)
        
        async for chunk in response:
            if chunk.text:
                yield chunk.text
    
    async def list_models(self) -> list[ModelInfo]:
        """List available Gemini models."""
        if not self.is_available:
            return []
        
        self._configure()
        
        try:
            import google.generativeai as genai
            models = []
            
            for model in genai.list_models():
                if "generateContent" in model.supported_generation_methods:
                    model_id = model.name.replace("models/", "")
                    if model_id in GEMINI_MODELS:
                        models.append(GEMINI_MODELS[model_id])
                    else:
                        models.append(ModelInfo(
                            id=model_id,
                            name=model.display_name,
                            provider=ProviderType.GEMINI,
                            context_length=model.input_token_limit or 32000,
                        ))
            
            return models if models else list(GEMINI_MODELS.values())
        except Exception as e:
            logger.error(f"Failed to list Gemini models: {e}")
            return list(GEMINI_MODELS.values())
    
    async def validate_api_key(self) -> bool:
        """Validate the API key."""
        if not self.api_key:
            return False
        
        try:
            self._configure()
            models = await self.list_models()
            return len(models) > 0
        except Exception:
            return False
    
    async def health_check(self) -> bool:
        return await self.validate_api_key()
