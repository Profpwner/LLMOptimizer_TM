"""
Unified interface for all LLM platforms.
"""

import asyncio
from typing import Dict, List, Optional, AsyncIterator, Union, Type, Any
from contextlib import asynccontextmanager
import logging

from .base import (
    BaseLLMClient, LLMPlatform, LLMResponse, StreamChunk,
    Message, MessageRole, LLMConfig, LLMClientError
)
from .openai_client import OpenAIClient
from .anthropic_client import AnthropicClient
from .perplexity_client import PerplexityClient
from .google_client import GoogleClient


logger = logging.getLogger(__name__)


class UnifiedLLMClient:
    """
    Unified interface for managing multiple LLM platforms.
    Provides a single API for interacting with different LLM providers.
    """
    
    # Registry of available client implementations
    CLIENT_REGISTRY: Dict[LLMPlatform, Type[BaseLLMClient]] = {
        LLMPlatform.OPENAI: OpenAIClient,
        LLMPlatform.ANTHROPIC: AnthropicClient,
        LLMPlatform.PERPLEXITY: PerplexityClient,
        LLMPlatform.GOOGLE: GoogleClient,
    }
    
    # Platform-specific model mappings
    PLATFORM_MODELS = {
        LLMPlatform.OPENAI: [
            "gpt-4-0125-preview", "gpt-4-1106-preview", "gpt-4", "gpt-4-32k",
            "gpt-3.5-turbo-0125", "gpt-3.5-turbo", "gpt-3.5-turbo-16k"
        ],
        LLMPlatform.ANTHROPIC: [
            "claude-3-opus-20240229", "claude-3-sonnet-20240229", 
            "claude-3-haiku-20240307", "claude-2.1", "claude-2.0", 
            "claude-instant-1.2"
        ],
        LLMPlatform.PERPLEXITY: [
            "pplx-7b-online", "pplx-70b-online", "pplx-7b-chat", "pplx-70b-chat",
            "llama-3.1-sonar-small-128k-online", "llama-3.1-sonar-large-128k-online",
            "llama-3.1-sonar-huge-128k-online"
        ],
        LLMPlatform.GOOGLE: [
            "gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.0-pro",
            "gemini-pro", "gemini-pro-vision"
        ]
    }
    
    def __init__(self):
        """Initialize the unified client."""
        self._clients: Dict[LLMPlatform, BaseLLMClient] = {}
        self._default_platform: Optional[LLMPlatform] = None
    
    def register_client(self, platform: LLMPlatform, config: LLMConfig) -> None:
        """
        Register a new LLM client.
        
        Args:
            platform: The LLM platform
            config: Configuration for the client
        """
        if platform not in self.CLIENT_REGISTRY:
            raise ValueError(f"Unsupported platform: {platform}")
        
        client_class = self.CLIENT_REGISTRY[platform]
        self._clients[platform] = client_class(config)
        
        # Set as default if it's the first client
        if self._default_platform is None:
            self._default_platform = platform
        
        logger.info(f"Registered {platform.value} client with model {config.model}")
    
    def set_default_platform(self, platform: LLMPlatform) -> None:
        """
        Set the default platform for requests.
        
        Args:
            platform: The platform to set as default
        """
        if platform not in self._clients:
            raise ValueError(f"Platform {platform} not registered")
        
        self._default_platform = platform
        logger.info(f"Set default platform to {platform.value}")
    
    def get_client(self, platform: Optional[LLMPlatform] = None) -> BaseLLMClient:
        """
        Get a specific LLM client.
        
        Args:
            platform: The platform to get client for (uses default if None)
            
        Returns:
            The requested LLM client
        """
        if platform is None:
            platform = self._default_platform
        
        if platform is None:
            raise ValueError("No platform specified and no default platform set")
        
        if platform not in self._clients:
            raise ValueError(f"Platform {platform} not registered")
        
        return self._clients[platform]
    
    @classmethod
    def detect_platform_from_model(cls, model: str) -> Optional[LLMPlatform]:
        """
        Detect the platform from a model name.
        
        Args:
            model: The model name
            
        Returns:
            The detected platform or None
        """
        model_lower = model.lower()
        
        # Check each platform's models
        for platform, models in cls.PLATFORM_MODELS.items():
            if any(model_lower.startswith(m.lower()) for m in models):
                return platform
        
        # Additional pattern matching
        if "gpt" in model_lower:
            return LLMPlatform.OPENAI
        elif "claude" in model_lower:
            return LLMPlatform.ANTHROPIC
        elif "pplx" in model_lower or "perplexity" in model_lower:
            return LLMPlatform.PERPLEXITY
        elif "gemini" in model_lower:
            return LLMPlatform.GOOGLE
        
        return None
    
    async def complete(self,
                      messages: List[Message],
                      platform: Optional[LLMPlatform] = None,
                      **kwargs) -> LLMResponse:
        """
        Send a completion request to the specified platform.
        
        Args:
            messages: List of messages in the conversation
            platform: The platform to use (uses default if None)
            **kwargs: Additional platform-specific parameters
            
        Returns:
            LLMResponse object with the completion
        """
        client = self.get_client(platform)
        return await client.complete(messages, **kwargs)
    
    async def stream_complete(self,
                            messages: List[Message],
                            platform: Optional[LLMPlatform] = None,
                            **kwargs) -> AsyncIterator[StreamChunk]:
        """
        Stream a completion response from the specified platform.
        
        Args:
            messages: List of messages in the conversation
            platform: The platform to use (uses default if None)
            **kwargs: Additional platform-specific parameters
            
        Yields:
            StreamChunk objects as they arrive
        """
        client = self.get_client(platform)
        async for chunk in client.stream_complete(messages, **kwargs):
            yield chunk
    
    async def complete_all(self,
                          messages: List[Message],
                          platforms: Optional[List[LLMPlatform]] = None,
                          **kwargs) -> Dict[LLMPlatform, Union[LLMResponse, Exception]]:
        """
        Send completion requests to multiple platforms concurrently.
        
        Args:
            messages: List of messages in the conversation
            platforms: List of platforms to query (uses all if None)
            **kwargs: Additional parameters
            
        Returns:
            Dictionary mapping platforms to responses or exceptions
        """
        if platforms is None:
            platforms = list(self._clients.keys())
        
        async def _complete_with_platform(platform: LLMPlatform):
            try:
                return await self.complete(messages, platform, **kwargs)
            except Exception as e:
                logger.error(f"Error with {platform.value}: {str(e)}")
                return e
        
        # Execute all requests concurrently
        tasks = [_complete_with_platform(platform) for platform in platforms]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return dict(zip(platforms, results))
    
    async def health_check(self,
                          platform: Optional[LLMPlatform] = None) -> Dict[LLMPlatform, bool]:
        """
        Check health status of LLM services.
        
        Args:
            platform: Specific platform to check (checks all if None)
            
        Returns:
            Dictionary mapping platforms to health status
        """
        platforms = [platform] if platform else list(self._clients.keys())
        
        async def _check_platform(p: LLMPlatform):
            try:
                client = self.get_client(p)
                return await client.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {p.value}: {str(e)}")
                return False
        
        tasks = [_check_platform(p) for p in platforms]
        results = await asyncio.gather(*tasks)
        
        return dict(zip(platforms, results))
    
    def get_platform_info(self, 
                         platform: Optional[LLMPlatform] = None) -> Dict[str, Any]:
        """
        Get information about registered platforms.
        
        Args:
            platform: Specific platform to get info for (gets all if None)
            
        Returns:
            Platform information including models, pricing, etc.
        """
        if platform:
            client = self.get_client(platform)
            return {
                "platform": platform.value,
                "model": client.config.model,
                "total_cost": client.get_total_cost(),
                "request_count": client.get_request_count(),
                "rate_limit_info": client.get_rate_limit_info()
            }
        
        # Return info for all platforms
        info = {}
        for p, client in self._clients.items():
            info[p.value] = {
                "model": client.config.model,
                "total_cost": client.get_total_cost(),
                "request_count": client.get_request_count(),
                "rate_limit_info": client.get_rate_limit_info()
            }
        
        return info
    
    async def count_tokens(self,
                          text: str,
                          platform: Optional[LLMPlatform] = None) -> int:
        """
        Count tokens for a given text.
        
        Args:
            text: Text to count tokens for
            platform: Platform to use for counting (uses default if None)
            
        Returns:
            Number of tokens
        """
        client = self.get_client(platform)
        return await client.count_tokens(text)
    
    def estimate_cost(self,
                     input_tokens: int,
                     output_tokens: int,
                     platform: Optional[LLMPlatform] = None) -> float:
        """
        Estimate cost for a request.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            platform: Platform to estimate for (uses default if None)
            
        Returns:
            Estimated cost in USD
        """
        client = self.get_client(platform)
        return client.estimate_cost(input_tokens, output_tokens)
    
    async def close_all(self):
        """Close all registered clients."""
        for client in self._clients.values():
            await client.close()
        self._clients.clear()
        self._default_platform = None
    
    @asynccontextmanager
    async def client_context(self, 
                           platform: LLMPlatform, 
                           config: LLMConfig):
        """
        Context manager for temporary client registration.
        
        Args:
            platform: The platform to register
            config: Configuration for the client
        """
        self.register_client(platform, config)
        try:
            yield self.get_client(platform)
        finally:
            if platform in self._clients:
                await self._clients[platform].close()
                del self._clients[platform]
                
                # Reset default platform if it was the one removed
                if self._default_platform == platform:
                    self._default_platform = (
                        list(self._clients.keys())[0] 
                        if self._clients else None
                    )


# Convenience function for creating a pre-configured unified client
def create_unified_client(configs: Dict[LLMPlatform, LLMConfig]) -> UnifiedLLMClient:
    """
    Create a unified client with multiple platforms pre-configured.
    
    Args:
        configs: Dictionary mapping platforms to their configurations
        
    Returns:
        Configured UnifiedLLMClient instance
    """
    client = UnifiedLLMClient()
    
    for platform, config in configs.items():
        client.register_client(platform, config)
    
    return client