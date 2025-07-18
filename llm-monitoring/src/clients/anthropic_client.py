"""
Anthropic (Claude) client implementation with streaming support.
"""

import asyncio
import time
from typing import Dict, List, Optional, AsyncIterator, Any
from datetime import datetime
import anthropic
from anthropic import AsyncAnthropic, HUMAN_PROMPT, AI_PROMPT
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import (
    BaseLLMClient, LLMPlatform, LLMResponse, StreamChunk,
    Message, MessageRole, LLMConfig, RateLimitInfo,
    RateLimitError, AuthenticationError, ModelNotFoundError, TokenLimitError
)


class AnthropicClient(BaseLLMClient):
    """Anthropic API client with async support and streaming."""
    
    # Model pricing per 1K tokens (as of 2024)
    PRICING = {
        "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
        "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
        "claude-2.1": {"input": 0.008, "output": 0.024},
        "claude-2.0": {"input": 0.008, "output": 0.024},
        "claude-instant-1.2": {"input": 0.0008, "output": 0.0024},
    }
    
    def __init__(self, config: LLMConfig):
        """Initialize Anthropic client."""
        super().__init__(config)
        self.client = AsyncAnthropic(
            api_key=config.api_key,
            timeout=config.timeout,
            max_retries=0  # We handle retries ourselves
        )
    
    def _get_platform(self) -> LLMPlatform:
        """Get the platform identifier."""
        return LLMPlatform.ANTHROPIC
    
    def _convert_messages_to_anthropic_format(self, messages: List[Message]) -> str:
        """Convert messages to Anthropic's expected format."""
        formatted_messages = []
        
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                # Anthropic doesn't have a system role, prepend to first user message
                continue
            elif msg.role == MessageRole.USER:
                formatted_messages.append(f"{HUMAN_PROMPT} {msg.content}")
            elif msg.role == MessageRole.ASSISTANT:
                formatted_messages.append(f"{AI_PROMPT} {msg.content}")
        
        # Add final AI prompt to indicate Claude should respond
        formatted_messages.append(AI_PROMPT)
        
        # Handle system messages by prepending to the conversation
        system_messages = [msg.content for msg in messages if msg.role == MessageRole.SYSTEM]
        if system_messages:
            system_context = "\n".join(system_messages)
            formatted_messages.insert(0, f"{HUMAN_PROMPT} {system_context}")
            formatted_messages.insert(1, f"{AI_PROMPT} I understand the context.")
        
        return "".join(formatted_messages)
    
    def _convert_messages_to_claude3_format(self, messages: List[Message]) -> tuple[Optional[str], List[Dict]]:
        """Convert messages to Claude 3 format (system + messages)."""
        system_content = None
        claude_messages = []
        
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_content = msg.content
            else:
                role = "user" if msg.role == MessageRole.USER else "assistant"
                claude_messages.append({
                    "role": role,
                    "content": msg.content
                })
        
        return system_content, claude_messages
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((RateLimitError, asyncio.TimeoutError))
    )
    async def complete(self, 
                      messages: List[Message],
                      **kwargs) -> LLMResponse:
        """
        Send a completion request to Anthropic.
        
        Args:
            messages: List of messages in the conversation
            **kwargs: Additional Anthropic-specific parameters
            
        Returns:
            LLMResponse object with the completion
        """
        start_time = time.time()
        
        # Check if using Claude 3 models
        is_claude3 = self.config.model.startswith("claude-3")
        
        # Prepare parameters
        params = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens or 4096,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
        }
        
        if is_claude3:
            # Use new message format for Claude 3
            system_content, claude_messages = self._convert_messages_to_claude3_format(messages)
            params["messages"] = claude_messages
            if system_content:
                params["system"] = system_content
        else:
            # Use legacy format for older models
            params["prompt"] = self._convert_messages_to_anthropic_format(messages)
        
        params.update(kwargs)
        
        try:
            if is_claude3:
                response = await self.client.messages.create(**params)
            else:
                response = await self.client.completions.create(**params)
            
            # Calculate response time
            response_time_ms = (time.time() - start_time) * 1000
            
            # Extract content based on response type
            if is_claude3:
                content = response.content[0].text if response.content else ""
                usage = {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                }
            else:
                content = response.completion
                # Estimate tokens for older models
                input_tokens = await self.count_tokens(params["prompt"])
                output_tokens = await self.count_tokens(content)
                usage = {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens
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
                content=content,
                raw_response=response.model_dump() if hasattr(response, 'model_dump') else response.__dict__,
                usage=usage,
                finish_reason=response.stop_reason if hasattr(response, 'stop_reason') else None,
                response_time_ms=response_time_ms
            )
            
        except anthropic.RateLimitError as e:
            retry_after = None
            if hasattr(e, 'response') and e.response:
                retry_after = e.response.headers.get('retry-after')
            raise RateLimitError(str(e), retry_after=int(retry_after) if retry_after else None)
        
        except anthropic.AuthenticationError as e:
            raise AuthenticationError(f"Anthropic authentication failed: {str(e)}")
        
        except anthropic.NotFoundError as e:
            raise ModelNotFoundError(f"Model not found: {str(e)}")
        
        except anthropic.BadRequestError as e:
            if "maximum" in str(e).lower() and "token" in str(e).lower():
                raise TokenLimitError(f"Token limit exceeded: {str(e)}")
            raise
        
        except Exception as e:
            raise Exception(f"Anthropic API error: {str(e)}")
    
    async def stream_complete(self,
                            messages: List[Message],
                            **kwargs) -> AsyncIterator[StreamChunk]:
        """
        Stream a completion response from Anthropic.
        
        Args:
            messages: List of messages in the conversation
            **kwargs: Additional Anthropic-specific parameters
            
        Yields:
            StreamChunk objects as they arrive
        """
        # Check if using Claude 3 models
        is_claude3 = self.config.model.startswith("claude-3")
        
        # Prepare parameters
        params = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens or 4096,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "stream": True
        }
        
        if is_claude3:
            # Use new message format for Claude 3
            system_content, claude_messages = self._convert_messages_to_claude3_format(messages)
            params["messages"] = claude_messages
            if system_content:
                params["system"] = system_content
        else:
            # Use legacy format for older models
            params["prompt"] = self._convert_messages_to_anthropic_format(messages)
        
        params.update(kwargs)
        
        try:
            accumulated_content = ""
            
            if is_claude3:
                async with self.client.messages.stream(**params) as stream:
                    async for event in stream:
                        if event.type == "content_block_delta":
                            content = event.delta.text
                            accumulated_content += content
                            yield StreamChunk(content=content, is_final=False)
                        elif event.type == "message_stop":
                            yield StreamChunk(
                                content="",
                                is_final=True,
                                finish_reason="stop"
                            )
            else:
                # Streaming for older models
                stream = await self.client.completions.create(**params)
                async for chunk in stream:
                    if hasattr(chunk, 'completion'):
                        content = chunk.completion
                        accumulated_content += content
                        yield StreamChunk(content=content, is_final=False)
                    elif hasattr(chunk, 'stop_reason'):
                        yield StreamChunk(
                            content="",
                            is_final=True,
                            finish_reason=chunk.stop_reason
                        )
            
            # Estimate tokens for cost calculation
            if accumulated_content:
                if is_claude3:
                    input_text = " ".join([msg.content for msg in messages])
                else:
                    input_text = params["prompt"]
                
                input_tokens = await self.count_tokens(input_text)
                output_tokens = await self.count_tokens(accumulated_content)
                cost = self.estimate_cost(input_tokens, output_tokens)
                self._increment_counters(cost)
                
        except anthropic.RateLimitError as e:
            retry_after = None
            if hasattr(e, 'response') and e.response:
                retry_after = e.response.headers.get('retry-after')
            raise RateLimitError(str(e), retry_after=int(retry_after) if retry_after else None)
        
        except anthropic.AuthenticationError as e:
            raise AuthenticationError(f"Anthropic authentication failed: {str(e)}")
        
        except Exception as e:
            raise Exception(f"Anthropic streaming error: {str(e)}")
    
    async def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in a text.
        Note: This is an approximation as Anthropic doesn't provide
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
        pricing = self.PRICING.get(self.config.model, self.PRICING["claude-2.1"])
        
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost
    
    async def close(self):
        """Clean up resources."""
        await self.client.close()