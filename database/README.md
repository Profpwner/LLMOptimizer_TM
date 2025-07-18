# Multi-Tenant Database Architecture

This directory contains the complete multi-tenant database architecture for the LLMOptimizer platform, supporting PostgreSQL, MongoDB, Redis, and Neo4j.

## Overview

The database layer implements a sophisticated multi-tenant architecture with:
- **PostgreSQL**: Structured data (users, organizations, permissions)
- **MongoDB**: Content and analytics data with versioning
- **Redis**: Caching, sessions, and rate limiting
- **Neo4j**: Knowledge graph for content relationships

## Directory Structure

```
database/
├── schemas/               # Database schemas and models
│   ├── postgresql/       # SQLAlchemy models
│   ├── mongodb/          # Beanie/Pydantic models
│   └── neo4j/           # Graph database models
├── migrations/           # Database migrations
│   └── alembic/         # PostgreSQL migrations
├── seeds/               # Seed data scripts
├── utils/               # Database utilities
│   ├── backup.py       # Backup/restore functionality
│   ├── monitoring.py   # Performance monitoring
│   └── validation.py   # Data validation schemas
├── tests/              # Comprehensive test suite
└── init_databases.py   # Database initialization script
```

## Multi-Tenancy Implementation

### Row-Level Security (PostgreSQL)
```sql
-- Automatic RLS policies for tenant isolation
CREATE POLICY tenant_isolation ON content
FOR ALL
USING (org_id = current_setting('app.current_tenant')::uuid)
WITH CHECK (org_id = current_setting('app.current_tenant')::uuid);
```

### Tenant Isolation Strategies
1. **PostgreSQL**: Row-level security with org_id filtering
2. **MongoDB**: Document-level filtering by org_id
3. **Redis**: Key prefixing (tenant:{tenant_id}:*)
4. **Neo4j**: Node property filtering

## Database Clients

### PostgreSQL Client
```python
from shared.database.manager import db_manager

# Create with tenant context
content = await db_manager.postgresql.create(content_model, tenant_id)

# Query with automatic tenant filtering
results = await db_manager.postgresql.get_many(
    Content,
    {"status": "published"},
    tenant_id
)
```

### MongoDB Client
```python
# Create document with versioning
doc = await db_manager.mongodb.create(content_doc, tenant_id)

# Add content version
await db_manager.mongodb.add_content_version(
    content_id, version_data, tenant_id
)

# Full-text search
results = await db_manager.mongodb.text_search(
    ContentDocument, "search terms", tenant_id
)
```

### Redis Client
```python
# Caching with tenant isolation
await db_manager.redis.set_json(
    "cache_key", data, tenant_id, ttl=3600
)

# Session management
await db_manager.redis.create_session(
    session_id, session_data, ttl=3600, tenant_id
)

# Rate limiting
allowed, remaining = await db_manager.redis.check_rate_limit(
    "api_key", limit=100, window=3600, tenant_id
)
```

### Neo4j Client
```python
# Create knowledge graph nodes
content_node = await db_manager.neo4j.create_node(
    node_data, ["Content"], tenant_id
)

# Create relationships
await db_manager.neo4j.create_relationship(
    content_id, "Content",
    topic_id, "Topic",
    "HAS_TOPIC",
    {"relevance_score": 0.95},
    tenant_id
)

# Find similar content
similar = await db_manager.neo4j.find_similar_content(
    content_id, tenant_id, similarity_threshold=0.7
)
```

## Key Features

### 1. Connection Pooling
- PostgreSQL: Async connection pooling with SQLAlchemy
- MongoDB: Motor async driver with configurable pool
- Redis: Connection pool with automatic retry
- Neo4j: Driver-level connection pooling

### 2. Transaction Support
```python
# Distributed transaction pattern
async with db_manager.distributed_transaction(tenant_id) as tx:
    # PostgreSQL operations
    await tx["postgresql"].add(content)
    
    # Neo4j operations
    await tx["neo4j"].run(query)
    
    # Commits on success, rollbacks on error
```

### 3. Performance Monitoring
```python
# Collect metrics
metrics = await db_monitor.collect_metrics()

# Get slow queries
slow_queries = await db_manager.postgresql.get_slow_queries()

# Generate performance report
report = await db_monitor.generate_report(hours=24)
```

### 4. Backup and Restore
```python
# Backup all databases for a tenant
backup_results = await db_backup.backup_all(tenant_id)

# Restore from backup
await db_backup.restore_all(backup_path)
```

### 5. Data Validation
```python
from database.utils.validation import ContentSchema, OrganizationSchema

# Validate before storage
content_data = ContentSchema(**user_input)
org_data = OrganizationSchema(**org_input)

# Check quotas
can_create = await TenantQuotaValidator.check_content_quota(tenant_id)
```

## Database Schemas

### PostgreSQL Models
- **Organization**: Multi-tenant root entity
- **User**: User accounts with multi-org support
- **Content**: Core content metadata
- **ContentOptimization**: Optimization history
- **APIKey**: API access management
- **UserSession**: Session tracking

### MongoDB Collections
- **ContentDocument**: Full content with versions
- **OptimizationResult**: AI optimization results
- **AnalyticsEvent**: User behavior tracking
- **ContentPerformance**: Aggregated metrics
- **AIModelUsage**: AI usage tracking

### Neo4j Nodes
- **Content**: Content nodes in knowledge graph
- **Topic**: Topic taxonomy
- **Keyword**: SEO keywords
- **Concept**: Abstract concepts
- **Audience**: Target audience segments
- **Competitor**: Competitive analysis

## Setup and Initialization

### 1. Install Dependencies
```bash
pip install -r database/requirements.txt
```

### 2. Configure Environment
```bash
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=llmoptimizer
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure_password

# MongoDB
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DB=llmoptimizer

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=optional_password

# Neo4j
NEO4J_HOST=localhost
NEO4J_BOLT_PORT=7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=secure_password
```

### 3. Initialize Databases
```bash
python database/init_databases.py
```

This will:
- Create PostgreSQL schema and tables
- Enable row-level security
- Create MongoDB indexes
- Set up Neo4j constraints
- Create demo tenant and data

### 4. Run Migrations
```bash
cd database/migrations
alembic upgrade head
```

## Testing

### Run All Tests
```bash
pytest database/tests/ -v
```

### Run Specific Test Suite
```bash
# PostgreSQL tests
pytest database/tests/test_postgresql.py -v

# MongoDB tests
pytest database/tests/test_mongodb.py -v

# Multi-tenancy tests
pytest database/tests/test_postgresql.py::TestMultiTenancy -v
```

## Performance Considerations

### 1. Query Optimization
- Proper indexes on all frequently queried fields
- Composite indexes for complex queries
- Full-text search indexes in MongoDB and Neo4j

### 2. Connection Management
- Connection pooling for all databases
- Configurable pool sizes based on load
- Automatic connection retry with exponential backoff

### 3. Caching Strategy
- Redis caching for frequently accessed data
- TTL-based cache expiration
- Cache warming for critical data

### 4. Monitoring
- Slow query detection and logging
- Connection pool statistics
- Memory usage tracking
- Performance metrics aggregation

## Security Features

### 1. Tenant Isolation
- Row-level security in PostgreSQL
- Tenant ID validation on all operations
- Cross-tenant access prevention

### 2. Data Encryption
- Encryption at rest (database-level)
- TLS for all database connections
- Sensitive data hashing (passwords, API keys)

### 3. Input Validation
- Pydantic schemas for all inputs
- SQL injection prevention
- NoSQL injection prevention
- XSS sanitization for content

### 4. Audit Logging
- All data modifications tracked
- User and timestamp recording
- Soft delete with retention

## Maintenance

### Regular Tasks
1. **Daily**: Monitor slow queries and connection pools
2. **Weekly**: Analyze performance metrics
3. **Monthly**: Database optimization and vacuum
4. **Quarterly**: Review and update indexes

### Backup Schedule
- **Continuous**: Redis snapshots
- **Hourly**: Incremental backups
- **Daily**: Full database backups
- **Weekly**: Offsite backup replication

## Troubleshooting

### Common Issues

1. **Connection Pool Exhaustion**
   - Increase pool size in config
   - Check for connection leaks
   - Monitor long-running queries

2. **Slow Queries**
   - Check query execution plans
   - Add missing indexes
   - Optimize complex aggregations

3. **Tenant Data Leakage**
   - Verify RLS policies
   - Check tenant context setting
   - Audit query filters

4. **Memory Issues**
   - Monitor Redis memory usage
   - Implement data expiration
   - Archive old analytics data

## Future Enhancements

1. **Sharding Support**: Horizontal scaling for large tenants
2. **Read Replicas**: Separate read/write workloads
3. **Time-Series Database**: Dedicated analytics storage
4. **GraphQL Integration**: Unified query interface
5. **Real-time Sync**: CDC for cross-database consistency