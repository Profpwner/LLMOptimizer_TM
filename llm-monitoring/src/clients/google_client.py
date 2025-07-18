"""
Google (Gemini) client implementation with streaming support.
"""

import asyncio
import time
from typing import Dict, List, Optional, AsyncIterator, Any
from datetime import datetime
import google.generativeai as genai
from google.generativeai.types import GenerationConfig, SafetySettings
from google.api_core import retry as google_retry
from google.api_core.exceptions import ResourceExhausted, Unauthenticated, NotFound
import httpx

from .base import (
    BaseLLMClient, LLMPlatform, LLMResponse, StreamChunk,
    Message, MessageRole, LLMConfig, RateLimitInfo,
    RateLimitError, AuthenticationError, ModelNotFoundError, TokenLimitError
)


class GoogleClient(BaseLLMClient):
    """Google Gemini API client with async support and streaming."""
    
    # Model pricing per 1K tokens (as of 2024)
    PRICING = {
        "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
        "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
        "gemini-1.0-pro": {"input": 0.0005, "output": 0.0015},
        "gemini-pro": {"input": 0.0005, "output": 0.0015},
        "gemini-pro-vision": {"input": 0.0005, "output": 0.0015},
    }
    
    def __init__(self, config: LLMConfig):
        """Initialize Google Gemini client."""
        super().__init__(config)
        genai.configure(api_key=config.api_key)
        self.model = genai.GenerativeModel(config.model)
        self._async_client = httpx.AsyncClient(timeout=config.timeout)
    
    def _get_platform(self) -> LLMPlatform:
        """Get the platform identifier."""
        return LLMPlatform.GOOGLE
    
    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, str]]:
        """Convert messages to Gemini format."""
        gemini_messages = []
        system_instruction = None
        
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                # Gemini uses system instructions separately
                system_instruction = msg.content
            else:
                role = "user" if msg.role == MessageRole.USER else "model"
                gemini_messages.append({
                    "role": role,
                    "parts": [{"text": msg.content}]
                })
        
        return gemini_messages, system_instruction
    
    @google_retry.Retry(
        predicate=google_retry.if_exception_type(ResourceExhausted),
        initial=1.0,
        maximum=60.0,
        multiplier=2.0,
        deadline=300.0
    )
    async def complete(self, 
                      messages: List[Message],
                      **kwargs) -> LLMResponse:
        """
        Send a completion request to Google Gemini.
        
        Args:
            messages: List of messages in the conversation
            **kwargs: Additional Gemini-specific parameters
            
        Returns:
            LLMResponse object with the completion
        """
        start_time = time.time()
        
        # Convert messages to Gemini format
        gemini_messages, system_instruction = self._convert_messages(messages)
        
        # Create generation config
        generation_config = GenerationConfig(
            temperature=self.config.temperature,
            top_p=self.config.top_p,
            max_output_tokens=self.config.max_tokens,
        )
        
        # Safety settings (can be customized)
        safety_settings = kwargs.pop("safety_settings", None)
        
        try:
            # Create a new model instance with system instruction if provided
            if system_instruction:
                model = genai.GenerativeModel(
                    self.config.model,
                    system_instruction=system_instruction
                )
            else:
                model = self.model
            
            # Generate response
            # Note: Gemini's async support is limited, so we run in executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content(
                    gemini_messages,
                    generation_config=generation_config,
                    safety_settings=safety_settings,
                    **kwargs
                )
            )
            
            # Calculate response time
            response_time_ms = (time.time() - start_time) * 1000
            
            # Extract content
            content = response.text if hasattr(response, 'text') else ""
            
            # Extract usage information
            usage = None
            if hasattr(response, 'usage_metadata'):
                usage = {
                    "prompt_tokens": response.usage_metadata.prompt_token_count,
                    "completion_tokens": response.usage_metadata.candidates_token_count,
                    "total_tokens": response.usage_metadata.total_token_count
                }
                
                # Calculate and update cost
                cost = self.estimate_cost(
                    usage["prompt_tokens"], 
                    usage["completion_tokens"]
                )
                self._increment_counters(cost)
            else:
                # Estimate tokens if not provided
                input_tokens = await self.count_tokens(
                    " ".join([msg.content for msg in messages])
                )
                output_tokens = await self.count_tokens(content)
                usage = {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens
                }
                cost = self.estimate_cost(input_tokens, output_tokens)
                self._increment_counters(cost)
            
            # Create unified response
            return LLMResponse(
                platform=self.platform,
                model=self.config.model,
                content=content,
                raw_response=response.__dict__ if hasattr(response, '__dict__') else str(response),
                usage=usage,
                finish_reason=response.candidates[0].finish_reason.name if response.candidates else None,
                response_time_ms=response_time_ms
            )
            
        except ResourceExhausted as e:
            raise RateLimitError(f"Rate limit exceeded: {str(e)}")
        
        except Unauthenticated as e:
            raise AuthenticationError(f"Google authentication failed: {str(e)}")
        
        except NotFound as e:
            raise ModelNotFoundError(f"Model not found: {str(e)}")
        
        except Exception as e:
            if "maximum context length" in str(e).lower():
                raise TokenLimitError(f"Token limit exceeded: {str(e)}")
            raise Exception(f"Google Gemini API error: {str(e)}")
    
    async def stream_complete(self,
                            messages: List[Message],
                            **kwargs) -> AsyncIterator[StreamChunk]:
        """
        Stream a completion response from Google Gemini.
        
        Args:
            messages: List of messages in the conversation
            **kwargs: Additional Gemini-specific parameters
            
        Yields:
            StreamChunk objects as they arrive
        """
        # Convert messages to Gemini format
        gemini_messages, system_instruction = self._convert_messages(messages)
        
        # Create generation config
        generation_config = GenerationConfig(
            temperature=self.config.temperature,
            top_p=self.config.top_p,
            max_output_tokens=self.config.max_tokens,
        )
        
        # Safety settings (can be customized)
        safety_settings = kwargs.pop("safety_settings", None)
        
        try:
            # Create a new model instance with system instruction if provided
            if system_instruction:
                model = genai.GenerativeModel(
                    self.config.model,
                    system_instruction=system_instruction
                )
            else:
                model = self.model
            
            # Generate streaming response
            # Note: Gemini's async streaming is limited, so we handle it carefully
            loop = asyncio.get_event_loop()
            response_stream = await loop.run_in_executor(
                None,
                lambda: model.generate_content(
                    gemini_messages,
                    generation_config=generation_config,
                    safety_settings=safety_settings,
                    stream=True,
                    **kwargs
                )
            )
            
            accumulated_content = ""
            
            # Process stream chunks
            for chunk in response_stream:
                if chunk.text:
                    content = chunk.text
                    accumulated_content += content
                    
                    # Check if this is the final chunk
                    is_final = (
                        hasattr(chunk, 'candidates') and 
                        chunk.candidates and 
                        chunk.candidates[0].finish_reason is not None
                    )
                    
                    yield StreamChunk(
                        content=content,
                        is_final=is_final,
                        finish_reason=chunk.candidates[0].finish_reason.name if is_final else None
                    )
            
            # Estimate tokens for cost calculation
            if accumulated_content:
                input_tokens = await self.count_tokens(
                    " ".join([msg.content for msg in messages])
                )
                output_tokens = await self.count_tokens(accumulated_content)
                cost = self.estimate_cost(input_tokens, output_tokens)
                self._increment_counters(cost)
                
        except ResourceExhausted as e:
            raise RateLimitError(f"Rate limit exceeded: {str(e)}")
        
        except Unauthenticated as e:
            raise AuthenticationError(f"Google authentication failed: {str(e)}")
        
        except Exception as e:
            raise Exception(f"Google Gemini streaming error: {str(e)}")
    
    async def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in a text using Gemini's token counter.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        try:
            # Use Gemini's built-in token counter
            loop = asyncio.get_event_loop()
            token_count = await loop.run_in_executor(
                None,
                lambda: self.model.count_tokens(text).total_tokens
            )
            return token_count
        except Exception:
            # Fallback to estimation if token counting fails
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
            self.PRICING.get("gemini-pro", {"input": 0.0005, "output": 0.0015})
        )
        
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost
    
    async def list_models(self) -> List[str]:
        """List available Gemini models."""
        try:
            loop = asyncio.get_event_loop()
            models = await loop.run_in_executor(
                None,
                lambda: list(genai.list_models())
            )
            return [
                model.name.split('/')[-1] 
                for model in models 
                if 'generateContent' in model.supported_generation_methods
            ]
        except Exception as e:
            raise Exception(f"Failed to list models: {str(e)}")
    
    async def close(self):
        """Clean up resources."""
        await self._async_client.aclose()