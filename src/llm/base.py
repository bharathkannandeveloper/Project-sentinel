"""
Base LLM Provider Interface

Defines the abstract base class that all LLM providers must implement.
Ensures consistent interface across Groq, Ollama, OpenAI, Anthropic, etc.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, AsyncIterator


class ProviderType(str, Enum):
    """Supported LLM provider types."""
    GROQ = "groq"
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    GROK = "grok"
    TOGETHER = "together"
    OPENROUTER = "openrouter"


@dataclass
class ModelInfo:
    """Information about an available model."""
    id: str
    name: str
    provider: ProviderType
    context_length: int = 4096
    max_output_tokens: int = 4096
    supports_streaming: bool = True
    supports_function_calling: bool = False
    supports_vision: bool = False
    input_cost_per_million: Decimal = Decimal("0")
    output_cost_per_million: Decimal = Decimal("0")
    description: str = ""
    
    def __str__(self) -> str:
        return f"{self.provider.value}:{self.id}"


@dataclass
class LLMResponse:
    """Response from an LLM completion request."""
    content: str
    model: str
    provider: ProviderType
    finish_reason: str = "stop"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    raw_response: dict[str, Any] = field(default_factory=dict)
    
    @property
    def cost(self) -> Decimal:
        """Calculate the cost of this response."""
        # This would need model pricing info to calculate accurately
        return Decimal("0")


@dataclass
class Message:
    """A chat message."""
    role: str  # "system", "user", "assistant"
    content: str
    name: str | None = None
    
    def to_dict(self) -> dict[str, str]:
        """Convert to API-compatible dictionary."""
        d = {"role": self.role, "content": self.content}
        if self.name:
            d["name"] = self.name
        return d


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All providers must implement these methods to ensure consistent
    behavior across different LLM backends.
    """
    
    provider_type: ProviderType
    
    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate a completion for the given messages.
        
        Args:
            messages: List of chat messages
            model: Model ID to use (uses default if not specified)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            stop: Stop sequences
            **kwargs: Provider-specific parameters
            
        Returns:
            LLMResponse with the completion
        """
        pass
    
    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        Stream a completion for the given messages.
        
        Args:
            messages: List of chat messages
            model: Model ID to use (uses default if not specified)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            stop: Stop sequences
            **kwargs: Provider-specific parameters
            
        Yields:
            String chunks as they are generated
        """
        pass
    
    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """
        List all available models from this provider.
        
        Returns:
            List of ModelInfo objects describing available models
        """
        pass
    
    @abstractmethod
    async def validate_api_key(self) -> bool:
        """
        Validate that the API key is valid.
        
        Returns:
            True if the API key is valid, False otherwise
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the provider is available and responding.
        
        Returns:
            True if the provider is healthy, False otherwise
        """
        pass
    
    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return the default model for this provider."""
        pass
    
    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider is configured and available."""
        pass
    
    def create_message(
        self,
        role: str,
        content: str,
        name: str | None = None
    ) -> Message:
        """Helper to create a Message object."""
        return Message(role=role, content=content, name=name)
    
    def system_message(self, content: str) -> Message:
        """Create a system message."""
        return self.create_message("system", content)
    
    def user_message(self, content: str) -> Message:
        """Create a user message."""
        return self.create_message("user", content)
    
    def assistant_message(self, content: str) -> Message:
        """Create an assistant message."""
        return self.create_message("assistant", content)
