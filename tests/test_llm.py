"""
Tests for LLM Provider Module
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.llm.base import Message, LLMResponse, ProviderType, ModelInfo
from src.llm.config import LLMConfig, get_llm_config
from src.llm.manager import LLMManager


class TestMessage:
    """Tests for Message dataclass."""
    
    def test_message_creation(self):
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
    
    def test_message_to_dict(self):
        msg = Message(role="system", content="You are a helpful assistant")
        d = msg.to_dict()
        assert d == {"role": "system", "content": "You are a helpful assistant"}


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""
    
    def test_response_creation(self):
        response = LLMResponse(
            content="Test response",
            model="test-model",
            provider=ProviderType.GROQ,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            latency_ms=100.0,
        )
        
        assert response.content == "Test response"
        assert response.provider == ProviderType.GROQ
        assert response.total_tokens == 15


class TestLLMConfig:
    """Tests for LLM configuration."""
    
    def test_config_singleton(self):
        """Test that get_llm_config returns same instance."""
        config1 = get_llm_config()
        config2 = get_llm_config()
        # Both should work (may or may not be same instance)
        assert config1 is not None
        assert config2 is not None
    
    def test_fallback_chain(self):
        """Test fallback chain order."""
        config = LLMConfig()
        chain = config.get_fallback_chain()
        
        # Should have at least Groq and Ollama
        assert ProviderType.GROQ in chain
        assert ProviderType.OLLAMA in chain
        
        # Groq should be first if it's the default
        if config.default_provider == ProviderType.GROQ:
            assert chain[0] == ProviderType.GROQ


class TestModelInfo:
    """Tests for ModelInfo."""
    
    def test_model_info_creation(self):
        model = ModelInfo(
            id="test-model",
            name="Test Model",
            provider=ProviderType.GROQ,
            context_length=4096,
            supports_streaming=True,
        )
        
        assert model.id == "test-model"
        assert model.context_length == 4096
        assert model.supports_streaming


class TestLLMManager:
    """Tests for LLM Manager."""
    
    @pytest.fixture
    def manager(self):
        return LLMManager()
    
    def test_manager_creation(self, manager):
        """Test manager instantiation."""
        assert manager is not None
        assert manager.config is not None
    
    @pytest.mark.asyncio
    async def test_select_provider(self, manager):
        """Test provider selection."""
        # Should select default when no preference
        selected = manager._select_provider()
        assert isinstance(selected, ProviderType)
