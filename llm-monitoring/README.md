# LLM Monitoring Service

A comprehensive multi-platform LLM monitoring and API integration service for tracking brand visibility across ChatGPT, Claude, Perplexity, Gemini, and other LLM platforms.

## Features

### LLM Client Integration
- **Unified Interface**: Single API for interacting with multiple LLM providers
- **Platform Support**: OpenAI (ChatGPT), Anthropic (Claude), Perplexity, Google (Gemini)
- **Streaming Support**: Real-time streaming responses from all platforms
- **Async Operations**: Built with async/await for high-performance concurrent requests

### Key Capabilities
- **Citation Extraction**: NLP-based detection of citations and brand mentions
- **Sentiment Analysis**: Analyze sentiment around brand mentions
- **Cost Tracking**: Monitor API usage and costs across platforms
- **Rate Limiting**: Intelligent rate limiting with token bucket algorithm
- **Distributed Processing**: Celery-based task queue for scalable processing
- **Webhook Support**: Real-time notifications and event processing
- **Health Monitoring**: Platform availability and health checks

## Architecture

```
llm-monitoring/
├── src/
│   ├── api/           # FastAPI routes and endpoints
│   ├── clients/       # LLM platform client implementations
│   ├── citation/      # Citation extraction engine
│   ├── tasks/         # Celery task definitions
│   ├── monitoring/    # Metrics and monitoring
│   ├── webhooks/      # Webhook handling
│   └── utils/         # Utility functions
├── tests/             # Test suite
└── examples/          # Usage examples
```

## Installation

1. Clone the repository and navigate to the service directory:
```bash
cd llm-monitoring
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy and configure environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

5. Install required NLP models:
```bash
python -m spacy download en_core_web_sm
```

## Configuration

### Required API Keys
At least one LLM provider API key is required:
- `OPENAI_API_KEY`: For ChatGPT integration
- `ANTHROPIC_API_KEY`: For Claude integration
- `PERPLEXITY_API_KEY`: For Perplexity integration (with online search)
- `GOOGLE_API_KEY`: For Gemini integration

### Redis Setup
Redis is required for Celery task queue:
```bash
# Using Docker
docker run -d -p 6379:6379 redis:alpine

# Or install locally
# Ubuntu/Debian: sudo apt-get install redis-server
# macOS: brew install redis
```

## Usage

### Basic Client Usage

```python
from src.clients import UnifiedLLMClient, LLMConfig, LLMPlatform, Message, MessageRole

# Initialize client
client = UnifiedLLMClient()

# Register OpenAI
client.register_client(
    LLMPlatform.OPENAI,
    LLMConfig(
        api_key="your-api-key",
        model="gpt-3.5-turbo",
        temperature=0.7
    )
)

# Send a completion request
messages = [
    Message(role=MessageRole.USER, content="What is machine learning?")
]

response = await client.complete(messages)
print(f"Response: {response.content}")
print(f"Tokens used: {response.usage}")
print(f"Cost: ${client.estimate_cost(response.usage['prompt_tokens'], response.usage['completion_tokens'])}")
```

### Streaming Responses

```python
# Stream responses
async for chunk in client.stream_complete(messages):
    print(chunk.content, end="", flush=True)
    if chunk.is_final:
        print(f"\nFinished: {chunk.finish_reason}")
```

### Multi-Platform Queries

```python
# Query multiple platforms concurrently
results = await client.complete_all(messages)

for platform, response in results.items():
    if isinstance(response, Exception):
        print(f"{platform}: Error - {response}")
    else:
        print(f"{platform}: {response.content[:100]}...")
```

### Perplexity Online Search

```python
from src.clients.perplexity_client import PerplexityClient

client = PerplexityClient(config)
response = await client.search(
    "Latest AI developments in 2024",
    search_recency_filter="month"
)

print(f"Results: {response.content}")
print(f"Citations: {response.citations}")
```

## Running the Service

### Start the API Server
```bash
uvicorn main:app --host 0.0.0.0 --port 8004 --reload
```

### Start Celery Worker
```bash
celery -A src.tasks worker --loglevel=info
```

### Start Celery Beat (for scheduled tasks)
```bash
celery -A src.tasks beat --loglevel=info
```

## API Endpoints

### Health Check
```bash
GET /health
```

### Platform Status
```bash
GET /api/v1/platforms/status
```

### Send Completion
```bash
POST /api/v1/completions
{
  "messages": [
    {"role": "user", "content": "Your question here"}
  ],
  "platform": "openai",
  "stream": false
}
```

### Monitor Brand
```bash
POST /api/v1/monitor/brand
{
  "brand_name": "YourBrand",
  "platforms": ["openai", "anthropic", "perplexity"],
  "queries": ["Tell me about YourBrand"]
}
```

## Rate Limiting

The service implements sophisticated rate limiting:
- Per-platform rate limits
- Token-based rate limiting
- Request-based rate limiting
- Automatic retry with exponential backoff

## Cost Tracking

Monitor API usage costs:
```python
# Get platform statistics
info = client.get_platform_info()
for platform, stats in info.items():
    print(f"{platform}: ${stats['total_cost']:.4f}")
```

## Error Handling

The service provides specific exception types:
- `RateLimitError`: When rate limits are exceeded
- `AuthenticationError`: Invalid API keys
- `ModelNotFoundError`: Requested model not available
- `TokenLimitError`: Token limits exceeded

## Testing

Run the test suite:
```bash
pytest tests/ -v
```

Run with coverage:
```bash
pytest tests/ --cov=src --cov-report=html
```

## Docker Support

Build and run with Docker:
```bash
docker build -t llm-monitoring .
docker run -p 8004:8004 --env-file .env llm-monitoring
```

## Monitoring

The service exposes Prometheus metrics on port 9094:
- Request counts by platform
- Response times
- Error rates
- Token usage
- Cost metrics

## Contributing

1. Follow the existing code structure
2. Add tests for new features
3. Update documentation
4. Ensure all tests pass
5. Submit a pull request

## License

[Your License Here]