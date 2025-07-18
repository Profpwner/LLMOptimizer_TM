# LLMOptimizer Integration Service

## Overview

The Integration Service provides a unified framework for connecting LLMOptimizer with enterprise applications. It supports OAuth 2.0, API key authentication, webhooks, and bidirectional data synchronization.

## Supported Integrations

### 1. HubSpot Integration
- **Authentication**: OAuth 2.0
- **Entities**: Contacts, Companies, Deals
- **Features**:
  - Full CRUD operations
  - Webhook support for real-time updates
  - Pagination handling for large datasets
  - Custom field mapping

### 2. Salesforce Integration
- **Authentication**: OAuth 2.0 + JWT Bearer flow
- **Entities**: Leads, Accounts, Opportunities, Contacts, Custom Objects
- **Features**:
  - SOQL query support
  - Bulk API for large data operations
  - Change Data Capture (CDC) for real-time sync
  - Composite API for efficient batch operations
  - Custom object support

### 3. WordPress Integration
- **Authentication**: REST API with Application Passwords
- **Entities**: Posts, Pages, Media, Users, Categories, Tags, Custom Post Types
- **Features**:
  - Gutenberg block parsing
  - Custom post type support
  - Meta fields and taxonomies
  - Media library management
  - Plugin-based webhook notifications

### 4. GitHub Integration
- **Authentication**: OAuth 2.0 + GitHub App
- **Entities**: Repositories, Issues, Pull Requests, Commits, Releases, Workflows
- **Features**:
  - GitHub Actions integration
  - Webhook event handling
  - Code search capabilities
  - Organization management
  - Rate limit handling

## Core Services

### 1. Sync Service
Manages asynchronous data synchronization jobs with features:
- Incremental sync support
- Conflict resolution strategies
- Data deduplication
- Progress tracking and logging
- Scheduled sync jobs
- Bidirectional sync

### 2. Webhook Service
Handles incoming webhooks with:
- Event routing and processing
- Signature verification
- Automatic retry logic
- Dead letter queue for failed events
- Custom event handlers
- Rate limiting

### 3. Transformation Service
Provides data mapping and transformation:
- Field mapping configurations
- Data type conversions
- Custom transformation functions
- Validation rules
- Template-based transformations
- Conditional logic

## Architecture

```
┌─────────────────────┐
│   Client Apps       │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│   API Gateway       │
├─────────────────────┤
│  - Authentication   │
│  - Rate Limiting    │
│  - Request Routing  │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│ Integration Service │
├─────────────────────┤
│  - OAuth Flows      │
│  - Webhook Handler  │
│  - Sync Jobs        │
└──────────┬──────────┘
           │
    ┌──────┴──────┬──────────┬──────────┐
    │             │          │          │
┌───▼───┐   ┌────▼────┐ ┌───▼───┐ ┌───▼────┐
│HubSpot│   │Salesforce│ │WordPress│ │GitHub  │
└───────┘   └──────────┘ └─────────┘ └────────┘
```

## Configuration

### Environment Variables

```env
# Service Configuration
SERVICE_NAME=integrations-service
PORT=8000
ENVIRONMENT=production

# Security
SECRET_KEY=your-secret-key
ENCRYPTION_KEY=your-encryption-key

# OAuth Credentials
HUBSPOT_CLIENT_ID=your-hubspot-client-id
HUBSPOT_CLIENT_SECRET=your-hubspot-client-secret
SALESFORCE_CLIENT_ID=your-salesforce-client-id
SALESFORCE_CLIENT_SECRET=your-salesforce-client-secret
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret

# Webhook Configuration
WEBHOOK_SECRET=your-webhook-secret
WEBHOOK_BASE_URL=https://api.yourdomain.com/webhooks
```

## Usage Examples

### Creating an Integration

```python
from app.services import IntegrationService
from app.models import IntegrationType

service = IntegrationService()

# Create HubSpot integration
integration = await service.create_integration(
    user_id="user-123",
    organization_id="org-456",
    integration_type=IntegrationType.HUBSPOT,
    name="My HubSpot CRM"
)

# Get OAuth URL
auth_url = await service.get_authorization_url(
    integration_id=integration.id,
    state="random-state"
)
```

### Setting Up Data Sync

```python
from app.services import sync_service
from app.models import SyncDirection

# Create sync job
job = await sync_service.create_sync_job(
    integration_id=integration.id,
    user_id="user-123",
    organization_id="org-456",
    entity_types=["contacts", "companies"],
    direction=SyncDirection.BIDIRECTIONAL,
    filters={"status": "active"}
)
```

### Configuring Field Mappings

```python
from app.services import transformation_service
from app.services import FieldMapping, DataType, TransformationType

# Define mappings
mappings = [
    FieldMapping(
        source_field="properties.email",
        target_field="Email",
        transformation_type=TransformationType.FUNCTION,
        transformation_config={"function": "email_normalize"},
        data_type=DataType.STRING
    ),
    FieldMapping(
        source_field="properties.phone",
        target_field="Phone",
        transformation_type=TransformationType.FUNCTION,
        transformation_config={"function": "phone_normalize"},
        data_type=DataType.STRING
    )
]

# Transform data
transformed = await transformation_service.transform_data(
    source_data,
    mappings
)
```

## Webhook Endpoints

### HubSpot
```
POST /api/v1/webhooks/hubspot/{integration_id}
Headers:
  X-HubSpot-Signature: {signature}
```

### Salesforce
```
POST /api/v1/webhooks/salesforce/{integration_id}
Headers:
  X-Salesforce-Signature: {signature}
```

### WordPress
```
POST /api/v1/webhooks/wordpress/{integration_id}
Headers:
  X-WordPress-Signature: {signature}
```

### GitHub
```
POST /api/v1/webhooks/github/{integration_id}
Headers:
  X-Hub-Signature-256: {signature}
  X-GitHub-Event: {event_type}
```

## Error Handling

The service implements comprehensive error handling:

1. **Integration Errors**: Connection failures, API errors
2. **Authentication Errors**: Invalid tokens, expired credentials
3. **Rate Limit Errors**: API rate limit exceeded
4. **Validation Errors**: Data validation failures
5. **Transformation Errors**: Field mapping errors

## Testing

Run the test suite:

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Full test suite with coverage
pytest --cov=app tests/
```

## Deployment

The service is containerized and can be deployed to:
- Kubernetes (EKS/GKE)
- Docker Swarm
- AWS ECS
- Cloud Run

See `/infrastructure/terraform/` for infrastructure as code.

## Monitoring

Key metrics to monitor:
- Sync job success/failure rates
- Webhook processing times
- API rate limit usage
- Error rates by integration type
- Data transformation performance

## Security Considerations

1. **Token Encryption**: All OAuth tokens are encrypted at rest
2. **Webhook Verification**: All webhooks signatures are verified
3. **Rate Limiting**: Prevents abuse and respects API limits
4. **Audit Logging**: All operations are logged for compliance
5. **Data Privacy**: PII is handled according to regulations

## Future Enhancements

1. Additional integrations (Slack, Microsoft 365, Stripe)
2. GraphQL API support
3. Event streaming with Kafka
4. Machine learning for intelligent field mapping
5. Multi-region deployment support