# Content Input API Documentation

## Overview

The Content Input System provides multiple methods for users to submit content for LLM optimization:
- Direct content input with rich text editor
- URL-based content extraction
- Batch file upload (CSV, TXT, JSON)
- Real-time processing updates via WebSocket

## API Endpoints

### 1. Direct Content Submission

**Endpoint:** `POST /api/content_input/direct`

Submit content directly for processing.

**Request Body:**
```json
{
  "title": "Article Title",
  "content_type": "article",
  "original_content": "<p>HTML content...</p>",
  "target_audience": "Tech professionals",
  "keywords": ["seo", "optimization"],
  "metadata": {
    "custom_field": "value"
  }
}
```

**Response:**
```json
{
  "id": "content_id",
  "status": "accepted",
  "message": "Content submitted successfully for optimization"
}
```

### 2. URL Submission

**Endpoint:** `POST /api/content_input/urls`

Submit URLs for content extraction and processing.

**Request Body:**
```json
{
  "urls": [
    "https://example.com/article1",
    "https://example.com/article2"
  ],
  "content_type": "article",
  "metadata": {}
}
```

**Response:**
```json
{
  "job_id": "job_123",
  "status": "processing"
}
```

### 3. Batch Upload

**Endpoint:** `POST /api/content_input/batch`

Upload files containing multiple content items.

**Request:** Multipart form data
- `file`: CSV, TXT, or JSON file
- `content_type`: Default content type for items

**CSV Format:**
```csv
title,content,keywords,target_audience
"Article 1","Content text here","keyword1,keyword2","audience"
"Article 2","More content","keyword3","developers"
```

**JSON Format:**
```json
[
  {
    "title": "Article 1",
    "content": "Content text",
    "keywords": ["keyword1", "keyword2"],
    "target_audience": "audience"
  }
]
```

**Response:**
```json
{
  "job_id": "job_456",
  "status": "processing"
}
```

### 4. Job Status

**Endpoint:** `GET /api/content_input/jobs/{job_id}`

Check the status of a processing job.

**Response:**
```json
{
  "_id": "job_id",
  "status": "completed",
  "items_processed": 10,
  "items_failed": 0,
  "results": [...]
}
```

## WebSocket API

**Endpoint:** `WS /ws/{user_id}`

Real-time updates for content processing.

### Message Types

**Job Update:**
```json
{
  "type": "job_update",
  "job_id": "job_123",
  "status": "processing",
  "progress": 0.75,
  "data": {
    "total_urls": 5,
    "processed": 3
  }
}
```

**Content Update:**
```json
{
  "type": "content_update",
  "content_id": "content_456",
  "update_type": "optimization_complete",
  "data": {
    "optimization_score": 0.85
  }
}
```

## Frontend Integration

### React Components

1. **ContentInputTabs**: Main container with tabs for different input methods
2. **DirectContentInput**: Rich text editor for direct content submission
3. **URLContentInput**: URL submission with real-time progress
4. **BatchUpload**: Drag-and-drop file upload interface
5. **ContentPreview**: Preview component for submitted content

### Services

- **contentApi.ts**: RTK Query API for content endpoints
- **contentWebSocket.ts**: WebSocket service for real-time updates

## Content Processing Pipeline

1. **Content Validation**
   - Minimum/maximum length checks
   - HTML sanitization
   - Content format detection

2. **Language Detection**
   - Automatic language detection using langdetect
   - Support for multiple languages

3. **Metadata Extraction**
   - Title extraction from HTML
   - Image and link extraction
   - Content statistics calculation

4. **Content Classification**
   - Automatic content type detection based on:
     - Word count
     - Sentence structure
     - Content patterns

## Security Features

- HTML sanitization using bleach
- XSS protection
- URL validation
- File type and size validation
- User authentication (JWT-based)

## Testing

Run the test script to verify endpoints:
```bash
python test_endpoints.py
```

## Environment Variables

- `MONGODB_URL`: MongoDB connection string
- `REDIS_URL`: Redis connection string
- `REACT_APP_CONTENT_SERVICE_URL`: Content service URL for frontend
- `REACT_APP_CONTENT_WS_URL`: WebSocket URL for frontend