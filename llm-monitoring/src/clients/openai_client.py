"""
OpenAI (ChatGPT) client implementation with streaming support.
"""

import asyncio
import time
from typing import Dict, List, Optional, AsyncIterator, Any
from datetime import datetime
import tiktoken
import openai
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import (
    BaseLLMClient, LLMPlatform, LLMResponse, StreamChunk,
    Message, MessageRole, LLMConfig, RateLimitInfo,
    RateLimitError, AuthenticationError, ModelNotFoundError, TokenLimitError
)


class OpenAIClient(BaseLLMClient):
    """OpenAI API client with async support and streaming."""
    
    # Model pricing per 1K tokens (as of 2024)
    PRICING = {
        "gpt-4-0125-preview": {"input": 0.01, "output": 0.03},
        "gpt-4-1106-preview": {"input": 0.01, "output": 0.03},
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-32k": {"input": 0.06, "output": 0.12},
        "gpt-3.5-turbo-0125": {"input": 0.0005, "output": 0.0015},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "gpt-3.5-turbo-16k": {"input": 0.003, "output": 0.004},
    }
    
    def __init__(self, config: LLMConfig):
        """Initialize OpenAI client."""
        super().__init__(config)
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            timeout=config.timeout,
            max_retries=0  # We handle retries ourselves
        )
        
        # Initialize tokenizer for the model
        try:
            self.encoding = tiktoken.encoding_for_model(config.model)
        except KeyError:
            # Fallback to cl100k_base encoding for newer models
            self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def _get_platform(self) -> LLMPlatform:
        """Get the platform identifier."""
        return LLMPlatform.OPENAI
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((RateLimitError, asyncio.TimeoutError))
    )
    async def complete(self, 
                      messages: List[Message],
                      **kwargs) -> LLMResponse:
        """
        Send a completion request to OpenAI.
        
        Args:
            messages: List of messages in the conversation
            **kwargs: Additional OpenAI-specific parameters
            
        Returns:
            LLMResponse object with the completion
        """
        start_time = time.time()
        
        # Convert messages to OpenAI format
        openai_messages = [msg.to_dict() for msg in messages]
        
        # Merge config with kwargs
        params = {
            "model": self.config.model,
            "messages": openai_messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
            "frequency_penalty": self.config.frequency_penalty,
            "presence_penalty": self.config.presence_penalty,
        }
        params.update(kwargs)
        
        try:
            response = await self.client.chat.completions.create(**params)
            
            # Extract rate limit info from headers if available
            if hasattr(response, '_headers'):
                self._update_rate_limit_info(response._headers)
            
            # Calculate response time
            response_time_ms = (time.time() - start_time) * 1000
            
            # Extract usage information
            usage = None
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
                
                # Calculate and update cost
                cost = self.estimate_cost(
                    usage["prompt_tokens"], 
                    usage["completion_tokens"]
                )
                self._increment_counters(cost)
            
            # Create unified response
            return LLMResponse(
                platform=self.platform,
                model=response.model,
                content=response.choices[0].message.content,
                raw_response=response.model_dump(),
                usage=usage,
                finish_reason=response.choices[0].finish_reason,
                response_time_ms=response_time_ms
            )
            
        except openai.RateLimitError as e:
            retry_after = None
            if hasattr(e, 'response') and e.response:
                retry_after = e.response.headers.get('Retry-After')
            raise RateLimitError(str(e), retry_after=int(retry_after) if retry_after else None)
        
        except openai.AuthenticationError as e:
            raise AuthenticationError(f"OpenAI authentication failed: {str(e)}")
        
        except openai.NotFoundError as e:
            raise ModelNotFoundError(f"Model not found: {str(e)}")
        
        except openai.BadRequestError as e:
            if "maximum context length" in str(e):
                raise TokenLimitError(f"Token limit exceeded: {str(e)}")
            raise
        
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")
    
    async def stream_complete(self,
                            messages: List[Message],
                            **kwargs) -> AsyncIterator[StreamChunk]:
        """
        Stream a completion response from OpenAI.
        
        Args:
            messages: List of messages in the conversation
            **kwargs: Additional OpenAI-specific parameters
            
        Yields:
            StreamChunk objects as they arrive
        """
        # Convert messages to OpenAI format
        openai_messages = [msg.to_dict() for msg in messages]
        
        # Merge config with kwargs
        params = {
            "model": self.config.model,
            "messages": openai_messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
            "frequency_penalty": self.config.frequency_penalty,
            "presence_penalty": self.config.presence_penalty,
            "stream": True
        }
        params.update(kwargs)
        
        try:
            stream = await self.client.chat.completions.create(**params)
            
            accumulated_content = ""
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    accumulated_content += content
                    
                    # Check if this is the final chunk
                    is_final = chunk.choices[0].finish_reason is not None
                    
                    yield StreamChunk(
                        content=content,
                        is_final=is_final,
                        finish_reason=chunk.choices[0].finish_reason
                    )
                    
                elif chunk.choices[0].finish_reason:
                    # Final chunk with no content
                    yield StreamChunk(
                        content="",
                        is_final=True,
                        finish_reason=chunk.choices[0].finish_reason
                    )
            
            # Estimate tokens for cost calculation
            if accumulated_content:
                input_tokens = await self.count_tokens(
                    " ".join([msg.content for msg in messages])
                )
                output_tokens = await self.count_tokens(accumulated_content)
                cost = self.estimate_cost(input_tokens, output_tokens)
                self._increment_counters(cost)
                
        except openai.RateLimitError as e:
            retry_after = None
            if hasattr(e, 'response') and e.response:
                retry_after = e.response.headers.get('Retry-After')
            raise RateLimitError(str(e), retry_after=int(retry_after) if retry_after else None)
        
        except openai.AuthenticationError as e:
            raise AuthenticationError(f"OpenAI authentication failed: {str(e)}")
        
        except Exception as e:
            raise Exception(f"OpenAI streaming error: {str(e)}")
    
    async def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in a text using tiktoken.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        return len(self.encoding.encode(text))
    
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
        pricing = self.PRICING.get(self.config.model, self.PRICING["gpt-3.5-turbo"])
        
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost
    
    def _update_rate_limit_info(self, headers: Dict[str, str]):
        """Update rate limit info from OpenAI response headers."""
        try:
            requests_limit = int(headers.get('x-ratelimit-limit-requests', 0))
            requests_remaining = int(headers.get('x-ratelimit-remaining-requests', 0))
            requests_reset = headers.get('x-ratelimit-reset-requests')
            
            tokens_limit = int(headers.get('x-ratelimit-limit-tokens', 0))
            tokens_remaining = int(headers.get('x-ratelimit-remaining-tokens', 0))
            tokens_reset = headers.get('x-ratelimit-reset-tokens')
            
            if requests_limit and requests_reset:
                self._rate_limit_info = RateLimitInfo(
                    requests_limit=requests_limit,
                    requests_remaining=requests_remaining,
                    requests_reset=datetime.fromtimestamp(int(requests_reset)),
                    tokens_limit=tokens_limit,
                    tokens_remaining=tokens_remaining,
                    tokens_reset=datetime.fromtimestamp(int(tokens_reset)) if tokens_reset else None
                )
        except (ValueError, TypeError):
            # Invalid headers, ignore
            pass
    
    async def list_models(self) -> List[str]:
        """List available models."""
        try:
            models = await self.client.models.list()
            return [model.id for model in models.data if model.id.startswith(('gpt-', 'text-'))]
        except Exception as e:
            raise Exception(f"Failed to list models: {str(e)}")
    
    async def close(self):
        """Clean up resources."""
        await self.client.close()