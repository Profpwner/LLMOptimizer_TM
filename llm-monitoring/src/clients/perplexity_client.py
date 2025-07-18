"""
Perplexity client implementation with online search capabilities.
"""

import asyncio
import time
import json
from typing import Dict, List, Optional, AsyncIterator, Any
from datetime import datetime
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import (
    BaseLLMClient, LLMPlatform, LLMResponse, StreamChunk,
    Message, MessageRole, LLMConfig, RateLimitInfo,
    RateLimitError, AuthenticationError, ModelNotFoundError, TokenLimitError
)


class PerplexityClient(BaseLLMClient):
    """Perplexity API client with async support and online search."""
    
    # Model pricing per 1K tokens (as of 2024)
    PRICING = {
        "pplx-7b-online": {"input": 0.0, "output": 0.0028},
        "pplx-70b-online": {"input": 0.001, "output": 0.001},
        "pplx-7b-chat": {"input": 0.0, "output": 0.0028},
        "pplx-70b-chat": {"input": 0.001, "output": 0.001},
        "llama-3.1-sonar-small-128k-online": {"input": 0.0002, "output": 0.0002},
        "llama-3.1-sonar-large-128k-online": {"input": 0.001, "output": 0.001},
        "llama-3.1-sonar-huge-128k-online": {"input": 0.005, "output": 0.005},
    }
    
    BASE_URL = "https://api.perplexity.ai"
    
    def __init__(self, config: LLMConfig):
        """Initialize Perplexity client."""
        super().__init__(config)
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
                **(config.custom_headers or {})
            },
            timeout=config.timeout
        )
    
    def _get_platform(self) -> LLMPlatform:
        """Get the platform identifier."""
        return LLMPlatform.PERPLEXITY
    
    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, str]]:
        """Convert messages to Perplexity format."""
        perplexity_messages = []
        
        for msg in messages:
            role = msg.role.value
            # Perplexity uses 'system' role differently, convert to user
            if role == "system":
                role = "user"
            
            perplexity_messages.append({
                "role": role,
                "content": msg.content
            })
        
        return perplexity_messages
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((RateLimitError, asyncio.TimeoutError))
    )
    async def complete(self, 
                      messages: List[Message],
                      **kwargs) -> LLMResponse:
        """
        Send a completion request to Perplexity.
        
        Args:
            messages: List of messages in the conversation
            **kwargs: Additional Perplexity-specific parameters
                     - search_domain_filter: List of domains to search
                     - return_citations: Whether to return citations
                     - search_recency_filter: Time filter for search results
            
        Returns:
            LLMResponse object with the completion
        """
        start_time = time.time()
        
        # Convert messages to Perplexity format
        perplexity_messages = self._convert_messages(messages)
        
        # Prepare request payload
        payload = {
            "model": self.config.model,
            "messages": perplexity_messages,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "frequency_penalty": self.config.frequency_penalty,
            "presence_penalty": self.config.presence_penalty,
        }
        
        if self.config.max_tokens:
            payload["max_tokens"] = self.config.max_tokens
        
        # Add Perplexity-specific parameters
        if "search_domain_filter" in kwargs:
            payload["search_domain_filter"] = kwargs["search_domain_filter"]
        if "return_citations" in kwargs:
            payload["return_citations"] = kwargs["return_citations"]
        if "search_recency_filter" in kwargs:
            payload["search_recency_filter"] = kwargs["search_recency_filter"]
        
        # Remove Perplexity-specific kwargs before passing remaining
        for key in ["search_domain_filter", "return_citations", "search_recency_filter"]:
            kwargs.pop(key, None)
        
        payload.update(kwargs)
        
        try:
            response = await self.client.post(
                "/chat/completions",
                json=payload
            )
            
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                raise RateLimitError(
                    "Rate limit exceeded",
                    retry_after=int(retry_after) if retry_after else None
                )
            
            if response.status_code == 401:
                raise AuthenticationError("Invalid API key")
            
            if response.status_code == 404:
                raise ModelNotFoundError(f"Model {self.config.model} not found")
            
            response.raise_for_status()
            
            data = response.json()
            
            # Calculate response time
            response_time_ms = (time.time() - start_time) * 1000
            
            # Extract usage information
            usage = None
            if "usage" in data:
                usage = {
                    "prompt_tokens": data["usage"].get("prompt_tokens", 0),
                    "completion_tokens": data["usage"].get("completion_tokens", 0),
                    "total_tokens": data["usage"].get("total_tokens", 0)
                }
                
                # Calculate and update cost
                cost = self.estimate_cost(
                    usage["prompt_tokens"], 
                    usage["completion_tokens"]
                )
                self._increment_counters(cost)
            
            # Extract citations if available
            citations = None
            if "citations" in data:
                citations = data["citations"]
            elif data["choices"][0].get("message", {}).get("citations"):
                citations = data["choices"][0]["message"]["citations"]
            
            # Create unified response
            return LLMResponse(
                platform=self.platform,
                model=data["model"],
                content=data["choices"][0]["message"]["content"],
                raw_response=data,
                usage=usage,
                finish_reason=data["choices"][0].get("finish_reason"),
                response_time_ms=response_time_ms,
                citations=citations
            )
            
        except httpx.HTTPStatusError as e:
            if "token" in str(e).lower() and "limit" in str(e).lower():
                raise TokenLimitError(f"Token limit exceeded: {str(e)}")
            raise Exception(f"Perplexity API error: {str(e)}")
        
        except Exception as e:
            if isinstance(e, (RateLimitError, AuthenticationError, ModelNotFoundError, TokenLimitError)):
                raise
            raise Exception(f"Perplexity API error: {str(e)}")
    
    async def stream_complete(self,
                            messages: List[Message],
                            **kwargs) -> AsyncIterator[StreamChunk]:
        """
        Stream a completion response from Perplexity.
        
        Args:
            messages: List of messages in the conversation
            **kwargs: Additional Perplexity-specific parameters
            
        Yields:
            StreamChunk objects as they arrive
        """
        # Convert messages to Perplexity format
        perplexity_messages = self._convert_messages(messages)
        
        # Prepare request payload
        payload = {
            "model": self.config.model,
            "messages": perplexity_messages,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "frequency_penalty": self.config.frequency_penalty,
            "presence_penalty": self.config.presence_penalty,
            "stream": True
        }
        
        if self.config.max_tokens:
            payload["max_tokens"] = self.config.max_tokens
        
        # Add Perplexity-specific parameters
        if "search_domain_filter" in kwargs:
            payload["search_domain_filter"] = kwargs["search_domain_filter"]
        if "return_citations" in kwargs:
            payload["return_citations"] = kwargs["return_citations"]
        if "search_recency_filter" in kwargs:
            payload["search_recency_filter"] = kwargs["search_recency_filter"]
        
        # Remove Perplexity-specific kwargs before passing remaining
        for key in ["search_domain_filter", "return_citations", "search_recency_filter"]:
            kwargs.pop(key, None)
        
        payload.update(kwargs)
        
        try:
            accumulated_content = ""
            
            async with self.client.stream(
                "POST",
                "/chat/completions",
                json=payload
            ) as response:
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    raise RateLimitError(
                        "Rate limit exceeded",
                        retry_after=int(retry_after) if retry_after else None
                    )
                
                if response.status_code == 401:
                    raise AuthenticationError("Invalid API key")
                
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            yield StreamChunk(
                                content="",
                                is_final=True,
                                finish_reason="stop"
                            )
                            break
                        
                        try:
                            data = json.loads(data_str)
                            if data["choices"][0]["delta"].get("content"):
                                content = data["choices"][0]["delta"]["content"]
                                accumulated_content += content
                                yield StreamChunk(content=content, is_final=False)
                            
                            if data["choices"][0].get("finish_reason"):
                                yield StreamChunk(
                                    content="",
                                    is_final=True,
                                    finish_reason=data["choices"][0]["finish_reason"]
                                )
                        except json.JSONDecodeError:
                            continue
            
            # Estimate tokens for cost calculation
            if accumulated_content:
                input_tokens = await self.count_tokens(
                    " ".join([msg.content for msg in messages])
                )
                output_tokens = await self.count_tokens(accumulated_content)
                cost = self.estimate_cost(input_tokens, output_tokens)
                self._increment_counters(cost)
                
        except httpx.HTTPStatusError as e:
            raise Exception(f"Perplexity streaming error: {str(e)}")
        
        except Exception as e:
            if isinstance(e, (RateLimitError, AuthenticationError)):
                raise
            raise Exception(f"Perplexity streaming error: {str(e)}")
    
    async def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in a text.
        Note: This is an approximation as Perplexity doesn't provide
        a public tokenizer. We estimate ~4 characters per token.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens (estimated)
        """
        # Rough estimation: ~4 characters per token
        return len(text) // 4
    
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
        pricing = self.PRICING.get(
            self.config.model, 
            {"input": 0.001, "output": 0.001}  # Default pricing
        )
        
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost
    
    async def search(self, 
                    query: str,
                    search_domain_filter: Optional[List[str]] = None,
                    search_recency_filter: Optional[str] = None) -> LLMResponse:
        """
        Perform a search query using Perplexity's online models.
        
        Args:
            query: Search query
            search_domain_filter: List of domains to search
            search_recency_filter: Time filter ('day', 'week', 'month', 'year')
            
        Returns:
            LLMResponse with search results and citations
        """
        messages = [Message(role=MessageRole.USER, content=query)]
        
        kwargs = {
            "return_citations": True
        }
        if search_domain_filter:
            kwargs["search_domain_filter"] = search_domain_filter
        if search_recency_filter:
            kwargs["search_recency_filter"] = search_recency_filter
        
        return await self.complete(messages, **kwargs)
    
    async def close(self):
        """Clean up resources."""
        await self.client.aclose()