"""
Example usage of the unified LLM client interface.
"""

import asyncio
import os
from dotenv import load_dotenv

from src.clients import (
    UnifiedLLMClient, 
    LLMConfig, 
    LLMPlatform,
    Message,
    MessageRole,
    create_unified_client
)


async def basic_example():
    """Basic example of using individual platform clients."""
    # Load environment variables
    load_dotenv()
    
    # Create unified client
    client = UnifiedLLMClient()
    
    # Register OpenAI client
    if openai_key := os.getenv("OPENAI_API_KEY"):
        client.register_client(
            LLMPlatform.OPENAI,
            LLMConfig(
                api_key=openai_key,
                model="gpt-3.5-turbo",
                temperature=0.7,
                max_tokens=100
            )
        )
    
    # Register Anthropic client
    if anthropic_key := os.getenv("ANTHROPIC_API_KEY"):
        client.register_client(
            LLMPlatform.ANTHROPIC,
            LLMConfig(
                api_key=anthropic_key,
                model="claude-3-haiku-20240307",
                temperature=0.7,
                max_tokens=100
            )
        )
    
    # Create messages
    messages = [
        Message(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        Message(role=MessageRole.USER, content="What is the capital of France?")
    ]
    
    # Get completion from default platform
    try:
        response = await client.complete(messages)
        print(f"\nResponse from {response.platform.value}:")
        print(f"Model: {response.model}")
        print(f"Content: {response.content}")
        print(f"Tokens: {response.usage}")
        print(f"Response time: {response.response_time_ms:.2f}ms")
    except Exception as e:
        print(f"Error: {e}")
    
    # Clean up
    await client.close_all()


async def streaming_example():
    """Example of streaming responses."""
    load_dotenv()
    
    client = UnifiedLLMClient()
    
    # Register OpenAI for streaming
    if openai_key := os.getenv("OPENAI_API_KEY"):
        client.register_client(
            LLMPlatform.OPENAI,
            LLMConfig(
                api_key=openai_key,
                model="gpt-3.5-turbo",
                temperature=0.7
            )
        )
    
    messages = [
        Message(role=MessageRole.USER, content="Write a short story about a robot.")
    ]
    
    print("\nStreaming response:")
    try:
        async for chunk in client.stream_complete(messages, max_tokens=200):
            print(chunk.content, end="", flush=True)
            if chunk.is_final:
                print(f"\n\nFinish reason: {chunk.finish_reason}")
    except Exception as e:
        print(f"\nStreaming error: {e}")
    
    await client.close_all()


async def multi_platform_example():
    """Example of querying multiple platforms concurrently."""
    load_dotenv()
    
    # Create configurations for multiple platforms
    configs = {}
    
    if openai_key := os.getenv("OPENAI_API_KEY"):
        configs[LLMPlatform.OPENAI] = LLMConfig(
            api_key=openai_key,
            model="gpt-3.5-turbo",
            temperature=0.7,
            max_tokens=50
        )
    
    if anthropic_key := os.getenv("ANTHROPIC_API_KEY"):
        configs[LLMPlatform.ANTHROPIC] = LLMConfig(
            api_key=anthropic_key,
            model="claude-3-haiku-20240307",
            temperature=0.7,
            max_tokens=50
        )
    
    if perplexity_key := os.getenv("PERPLEXITY_API_KEY"):
        configs[LLMPlatform.PERPLEXITY] = LLMConfig(
            api_key=perplexity_key,
            model="llama-3.1-sonar-small-128k-online",
            temperature=0.7,
            max_tokens=50
        )
    
    if google_key := os.getenv("GOOGLE_API_KEY"):
        configs[LLMPlatform.GOOGLE] = LLMConfig(
            api_key=google_key,
            model="gemini-pro",
            temperature=0.7,
            max_tokens=50
        )
    
    # Create unified client with all platforms
    client = create_unified_client(configs)
    
    messages = [
        Message(role=MessageRole.USER, content="What are the benefits of renewable energy?")
    ]
    
    print("\nQuerying multiple platforms concurrently...")
    results = await client.complete_all(messages)
    
    for platform, result in results.items():
        print(f"\n{platform.value}:")
        if isinstance(result, Exception):
            print(f"  Error: {result}")
        else:
            print(f"  Model: {result.model}")
            print(f"  Response: {result.content[:100]}...")
            print(f"  Response time: {result.response_time_ms:.2f}ms")
    
    # Show platform statistics
    print("\nPlatform Statistics:")
    info = client.get_platform_info()
    for platform, stats in info.items():
        print(f"\n{platform}:")
        print(f"  Total requests: {stats['request_count']}")
        print(f"  Total cost: ${stats['total_cost']:.4f}")
    
    await client.close_all()


async def perplexity_search_example():
    """Example of using Perplexity's search capabilities."""
    load_dotenv()
    
    if not (api_key := os.getenv("PERPLEXITY_API_KEY")):
        print("Perplexity API key not found")
        return
    
    from src.clients.perplexity_client import PerplexityClient
    
    config = LLMConfig(
        api_key=api_key,
        model="llama-3.1-sonar-large-128k-online",
        temperature=0.7
    )
    
    client = PerplexityClient(config)
    
    print("\nPerplexity Search Example:")
    response = await client.search(
        "What are the latest developments in quantum computing in 2024?",
        search_recency_filter="month"
    )
    
    print(f"Response: {response.content}")
    if response.citations:
        print("\nCitations:")
        for i, citation in enumerate(response.citations, 1):
            print(f"  [{i}] {citation}")
    
    await client.close()


async def health_check_example():
    """Example of checking platform health status."""
    load_dotenv()
    
    configs = {}
    
    # Add available platforms
    for platform, env_var in [
        (LLMPlatform.OPENAI, "OPENAI_API_KEY"),
        (LLMPlatform.ANTHROPIC, "ANTHROPIC_API_KEY"),
        (LLMPlatform.PERPLEXITY, "PERPLEXITY_API_KEY"),
        (LLMPlatform.GOOGLE, "GOOGLE_API_KEY")
    ]:
        if api_key := os.getenv(env_var):
            model = {
                LLMPlatform.OPENAI: "gpt-3.5-turbo",
                LLMPlatform.ANTHROPIC: "claude-3-haiku-20240307",
                LLMPlatform.PERPLEXITY: "llama-3.1-sonar-small-128k-online",
                LLMPlatform.GOOGLE: "gemini-pro"
            }[platform]
            
            configs[platform] = LLMConfig(api_key=api_key, model=model)
    
    client = create_unified_client(configs)
    
    print("\nChecking platform health status...")
    health_status = await client.health_check()
    
    for platform, is_healthy in health_status.items():
        status = "✅ Healthy" if is_healthy else "❌ Unhealthy"
        print(f"{platform.value}: {status}")
    
    await client.close_all()


async def main():
    """Run all examples."""
    print("=" * 50)
    print("LLM Client Examples")
    print("=" * 50)
    
    # Run examples based on available API keys
    examples = [
        ("Basic Example", basic_example),
        ("Streaming Example", streaming_example),
        ("Multi-Platform Example", multi_platform_example),
        ("Perplexity Search Example", perplexity_search_example),
        ("Health Check Example", health_check_example)
    ]
    
    for name, example_func in examples:
        print(f"\n{'=' * 50}")
        print(f"Running: {name}")
        print("=" * 50)
        try:
            await example_func()
        except Exception as e:
            print(f"Example failed: {e}")
        
        # Small delay between examples
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())