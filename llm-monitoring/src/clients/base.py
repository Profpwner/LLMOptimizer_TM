"""
Base interface for LLM clients.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, AsyncIterator, Union, Any
from dataclasses import dataclass
from enum import Enum
import asyncio
from datetime import datetime


class LLMPlatform(Enum):
    """Supported LLM platforms."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    PERPLEXITY = "perplexity"
    GOOGLE = "google"
    COHERE = "cohere"
    MISTRAL = "mistral"


class MessageRole(Enum):
    """Message roles in conversations."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"


@dataclass
class Message:
    """Represents a message in a conversation."""
    role: MessageRole
    content: str
    name: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format."""
        data = {
            "role": self.role.value,
            "content": self.content
        }
        if self.name:
            data["name"] = self.name
        if self.function_call:
            data["function_call"] = self.function_call
        return data


@dataclass
class LLMResponse:
    """Unified response format from LLM platforms."""
    platform: LLMPlatform
    model: str
    content: str
    raw_response: Dict[str, Any]
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None
    created_at: datetime = None
    response_time_ms: Optional[float] = None
    citations: Optional[List[Dict[str, Any]]] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class StreamChunk:
    """Represents a chunk in streaming response."""
    content: str
    is_final: bool = False
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None


@dataclass
class LLMConfig:
    """Configuration for LLM clients."""
    api_key: str
    model: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    custom_headers: Optional[Dict[str, str]] = None
    base_url: Optional[str] = None


class RateLimitInfo:
    """Rate limit information for API calls."""
    def __init__(self, 
                 requests_limit: int,
                 requests_remaining: int,
                 requests_reset: datetime,
                 tokens_limit: Optional[int] = None,
                 tokens_remaining: Optional[int] = None,
                 tokens_reset: Optional[datetime] = None):
        self.requests_limit = requests_limit
        self.requests_remaining = requests_remaining
        self.requests_reset = requests_reset
        self.tokens_limit = tokens_limit
        self.tokens_remaining = tokens_remaining
        self.tokens_reset = tokens_reset


class BaseLLMClient(ABC):
    """Base class for all LLM clients."""
    
    def __init__(self, config: LLMConfig):
        """Initialize the LLM client with configuration."""
        self.config = config
        self.platform = self._get_platform()
        self._rate_limit_info: Optional[RateLimitInfo] = None
        self._total_cost = 0.0
        self._request_count = 0
        
    @abstractmethod
    def _get_platform(self) -> LLMPlatform:
        """Get the platform identifier."""
        pass
    
    @abstractmethod
    async def complete(self, 
                      messages: List[Message],
                      **kwargs) -> LLMResponse:
        """
        Send a completion request to the LLM.
        
        Args:
            messages: List of messages in the conversation
            **kwargs: Additional platform-specific parameters
            
        Returns:
            LLMResponse object with the completion
        """
        pass
    
    @abstractmethod
    async def stream_complete(self,
                            messages: List[Message],
                            **kwargs) -> AsyncIterator[StreamChunk]:
        """
        Stream a completion response from the LLM.
        
        Args:
            messages: List of messages in the conversation
            **kwargs: Additional platform-specific parameters
            
        Yields:
            StreamChunk objects as they arrive
        """
        pass
    
    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in a text.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        pass
    
    @abstractmethod
    def estimate_cost(self, 
                     input_tokens: int, 
                     output_tokens: int) -> float:
        """
        Estimate the cost for a request.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        pass
    
    async def health_check(self) -> bool:
        """
        Check if the LLM service is available.
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            # Send a minimal request to check availability
            response = await self.complete([
                Message(role=MessageRole.USER, content="Hi")
            ], max_tokens=5)
            return bool(response.content)
        except Exception:
            return False
    
    def get_rate_limit_info(self) -> Optional[RateLimitInfo]:
        """Get current rate limit information."""
        return self._rate_limit_info
    
    def get_total_cost(self) -> float:
        """Get total cost of all requests."""
        return self._total_cost
    
    def get_request_count(self) -> int:
        """Get total number of requests made."""
        return self._request_count
    
    def _update_rate_limit_info(self, headers: Dict[str, str]):
        """Update rate limit info from response headers."""
        # This is a common pattern but implementations may vary
        pass
    
    def _increment_counters(self, cost: float):
        """Increment request and cost counters."""
        self._request_count += 1
        self._total_cost += cost
    
    async def close(self):
        """Clean up resources."""
        pass
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


class LLMClientError(Exception):
    """Base exception for LLM client errors."""
    pass


class RateLimitError(LLMClientError):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class AuthenticationError(LLMClientError):
    """Raised when authentication fails."""
    pass


class ModelNotFoundError(LLMClientError):
    """Raised when requested model is not found."""
    pass


class TokenLimitError(LLMClientError):
    """Raised when token limit is exceeded."""
    pass