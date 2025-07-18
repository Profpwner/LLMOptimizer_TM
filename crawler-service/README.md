# Crawler Service

Intelligent website crawler with distributed architecture, robots.txt compliance, and advanced queue management.

## Features

- **Priority-based URL Queue Management**
  - Redis-backed distributed queue
  - Bloom filter for duplicate detection
  - Domain-specific rate limiting
  - Queue persistence and recovery

- **Advanced Robots.txt Parser**
  - Complex directive parsing
  - User-agent specific rules
  - Crawl-delay handling
  - Sitemap discovery
  - Caching with TTL

- **Distributed Crawling Architecture**
  - Asyncio-based concurrent crawling
  - Multi-process worker pool
  - Load balancing
  - Fault tolerance
  - Comprehensive monitoring

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   FastAPI API   │────▶│  Orchestrator   │────▶│  Worker Pool    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                        │
         ▼                       ▼                        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Redis Queue    │     │  Robots Cache   │     │   Web Crawler   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## API Endpoints

### Create Crawl Job
```bash
POST /crawl
{
    "start_urls": ["https://example.com"],
    "allowed_domains": ["example.com"],
    "max_depth": 10,
    "max_pages": 1000,
    "include_sitemaps": true,
    "follow_robots": true,
    "rate_limit_rps": 1.0
}
```

### Get Job Status
```bash
GET /crawl/{job_id}
```

### Get Crawl Results
```bash
GET /crawl/{job_id}/results?offset=0&limit=100
```

### List Jobs
```bash
GET /jobs?status=running&limit=50
```

### System Statistics
```bash
GET /stats
```

### Domain Statistics
```bash
GET /stats/domain/{domain}
```

### Check Robots.txt
```bash
POST /robots/check?url=https://example.com/page
```

## Configuration

Environment variables:

- `REDIS_URL`: Redis connection URL (default: `redis://localhost:6379`)
- `ENABLE_WORKERS`: Enable worker pool (default: `true`)
- `NUM_WORKERS`: Number of worker processes (default: `4`)
- `PORT`: Service port (default: `8003`)
- `HOST`: Service host (default: `0.0.0.0`)

## Queue Priority Levels

1. **CRITICAL** - Sitemap URLs, important pages
2. **HIGH** - Internal links, high-value content
3. **MEDIUM** - Regular pages
4. **LOW** - External links, low-priority content
5. **DEFERRED** - Rate-limited or problematic URLs

## Rate Limiting

The crawler respects:
- Robots.txt crawl-delay directives
- Custom per-domain rate limits
- Automatic backoff on errors

## Monitoring

Prometheus metrics available at `/metrics`:

- `crawler_urls_crawled_total` - Total URLs crawled
- `crawler_errors_total` - Total crawl errors
- `crawler_crawl_duration_seconds` - Crawl duration histogram
- `crawler_queue_size` - Current queue sizes
- `crawler_active_crawls` - Number of active crawls
- `crawler_active_workers` - Number of active workers

## Development

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Run the service
python main.py
```

### Running Tests

```bash
pytest tests/
```

### Docker

```bash
# Build image
docker build -t crawler-service .

# Run container
docker run -p 8003:8003 \
  -e REDIS_URL=redis://redis:6379 \
  crawler-service
```

## Integration with Content Service

The crawler service integrates with the content service by:

1. Accepting crawl jobs via API
2. Crawling websites respecting robots.txt
3. Extracting content and metadata
4. Sending results to content service for processing

Example integration flow:

```python
# 1. Create crawl job
response = requests.post("http://crawler:8003/crawl", json={
    "start_urls": ["https://example.com"],
    "max_pages": 100
})
job_id = response.json()["job_id"]

# 2. Monitor job progress
while True:
    status = requests.get(f"http://crawler:8003/crawl/{job_id}")
    if status.json()["status"] in ["completed", "failed"]:
        break
    time.sleep(5)

# 3. Get results
results = requests.get(f"http://crawler:8003/crawl/{job_id}/results")
for result in results.json()["results"]:
    # Send to content service
    content_api.process_content(result)
```

## Performance Tuning

- Adjust `concurrent_crawls_per_worker` for more parallelism
- Increase `NUM_WORKERS` for more throughput
- Configure Redis persistence for reliability
- Use bloom filter size based on expected URL count
- Set appropriate `max_content_length` limits

## Security Considerations

- Respects robots.txt by default
- Rate limiting prevents aggressive crawling
- Content size limits prevent DoS
- Runs as non-root user in container
- Validates and normalizes all URLs