"""Tests for MongoDB database operations."""

import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import datetime, timedelta

from shared.database.manager import db_manager
from database.schemas.mongodb.models import (
    ContentDocument, ContentVersion, OptimizationResult,
    OptimizationSuggestion, AnalyticsEvent, ContentPerformance,
    AIModelUsage, ContentType, OptimizationType
)


class TestMongoDBCRUD:
    """Test MongoDB CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_create_content_document(self, test_tenant):
        """Test creating a content document."""
        doc = ContentDocument(
            org_id=test_tenant,
            postgres_content_id=str(uuid4()),
            title="Test MongoDB Content",
            slug="test-mongodb-content",
            content_type=ContentType.ARTICLE,
            tags=["test", "mongodb"],
            categories=["Testing"]
        )
        
        created = await db_manager.mongodb.create(doc, test_tenant)
        
        assert created.id is not None
        assert created.org_id == test_tenant
        assert created.title == "Test MongoDB Content"
        assert len(created.tags) == 2
    
    @pytest.mark.asyncio
    async def test_get_document(self, test_tenant):
        """Test retrieving a document."""
        # Create document
        doc = ContentDocument(
            org_id=test_tenant,
            postgres_content_id=str(uuid4()),
            title="Retrieve Test",
            slug="retrieve-test",
            content_type=ContentType.BLOG_POST
        )
        created = await db_manager.mongodb.create(doc, test_tenant)
        
        # Retrieve
        retrieved = await db_manager.mongodb.get(
            ContentDocument, str(created.id), test_tenant
        )
        
        assert retrieved is not None
        assert retrieved.title == "Retrieve Test"
        assert retrieved.content_type == ContentType.BLOG_POST
    
    @pytest.mark.asyncio
    async def test_update_document(self, test_tenant):
        """Test updating a document."""
        # Create document
        doc = ContentDocument(
            org_id=test_tenant,
            postgres_content_id=str(uuid4()),
            title="Update Test",
            slug="update-test",
            content_type=ContentType.ARTICLE
        )
        created = await db_manager.mongodb.create(doc, test_tenant)
        
        # Update
        updates = {
            "title": "Updated Title",
            "tags": ["updated", "test"],
            "current_version": 2
        }
        updated = await db_manager.mongodb.update(created, updates, test_tenant)
        
        assert updated.title == "Updated Title"
        assert updated.tags == ["updated", "test"]
        assert updated.current_version == 2
        assert updated.updated_at > created.updated_at
    
    @pytest.mark.asyncio
    async def test_delete_document(self, test_tenant):
        """Test deleting a document."""
        # Create document
        doc = ContentDocument(
            org_id=test_tenant,
            postgres_content_id=str(uuid4()),
            title="Delete Test",
            slug="delete-test",
            content_type=ContentType.ARTICLE
        )
        created = await db_manager.mongodb.create(doc, test_tenant)
        
        # Delete
        result = await db_manager.mongodb.delete(created, test_tenant)
        assert result is True
        
        # Verify deleted
        retrieved = await db_manager.mongodb.get(
            ContentDocument, str(created.id), test_tenant
        )
        assert retrieved is None
    
    @pytest.mark.asyncio
    async def test_query_documents(self, test_tenant):
        """Test querying documents with filters."""
        # Create multiple documents
        for i in range(5):
            doc = ContentDocument(
                org_id=test_tenant,
                postgres_content_id=str(uuid4()),
                title=f"Query Test {i}",
                slug=f"query-test-{i}",
                content_type=ContentType.ARTICLE if i % 2 == 0 else ContentType.BLOG_POST,
                tags=["test", f"tag{i}"]
            )
            await db_manager.mongodb.create(doc, test_tenant)
        
        # Query by content type
        articles = await db_manager.mongodb.get_many(
            ContentDocument,
            {"content_type": ContentType.ARTICLE},
            test_tenant
        )
        assert len(articles) == 3
        
        # Query with pagination
        paginated = await db_manager.mongodb.get_many(
            ContentDocument,
            {},
            test_tenant,
            limit=2,
            skip=1
        )
        assert len(paginated) == 2


class TestContentVersioning:
    """Test content versioning functionality."""
    
    @pytest.mark.asyncio
    async def test_add_content_version(self, test_tenant):
        """Test adding versions to content."""
        # Create content
        doc = ContentDocument(
            org_id=test_tenant,
            postgres_content_id=str(uuid4()),
            title="Version Test",
            slug="version-test",
            content_type=ContentType.ARTICLE
        )
        created = await db_manager.mongodb.create(doc, test_tenant)
        
        # Add version
        version_data = {
            "created_by": str(uuid4()),
            "title": "Version Test",
            "content": "This is version 1 content",
            "word_count": 5,
            "keywords": ["version", "test"]
        }
        
        result = await db_manager.mongodb.add_content_version(
            str(created.id), version_data, test_tenant
        )
        assert result is True
        
        # Verify version added
        updated = await db_manager.mongodb.get(
            ContentDocument, str(created.id), test_tenant
        )
        assert len(updated.versions) == 1
        assert updated.versions[0].version_number == 1
        assert updated.versions[0].content == "This is version 1 content"
        assert updated.current_version == 1
    
    @pytest.mark.asyncio
    async def test_multiple_versions(self, test_tenant):
        """Test managing multiple content versions."""
        # Create content with initial version
        doc = ContentDocument(
            org_id=test_tenant,
            postgres_content_id=str(uuid4()),
            title="Multi Version Test",
            slug="multi-version-test",
            content_type=ContentType.ARTICLE,
            versions=[
                ContentVersion(
                    version_number=1,
                    created_by=str(uuid4()),
                    title="Initial Version",
                    content="Initial content",
                    word_count=2
                )
            ]
        )
        created = await db_manager.mongodb.create(doc, test_tenant)
        
        # Add more versions
        for i in range(2, 5):
            version_data = {
                "created_by": str(uuid4()),
                "title": f"Version {i}",
                "content": f"Content for version {i}",
                "word_count": 4,
                "change_summary": f"Updated to version {i}"
            }
            await db_manager.mongodb.add_content_version(
                str(created.id), version_data, test_tenant
            )
        
        # Verify all versions
        final = await db_manager.mongodb.get(
            ContentDocument, str(created.id), test_tenant
        )
        assert len(final.versions) == 4
        assert final.current_version == 4
        assert final.versions[-1].title == "Version 4"
    
    @pytest.mark.asyncio
    async def test_get_latest_version(self, test_tenant):
        """Test retrieving the latest version."""
        # Create content with versions
        doc = ContentDocument(
            org_id=test_tenant,
            postgres_content_id=str(uuid4()),
            title="Latest Version Test",
            slug="latest-version-test",
            content_type=ContentType.ARTICLE,
            versions=[
                ContentVersion(
                    version_number=1,
                    created_by=str(uuid4()),
                    title="V1",
                    content="Version 1"
                ),
                ContentVersion(
                    version_number=2,
                    created_by=str(uuid4()),
                    title="V2",
                    content="Version 2 - Latest"
                )
            ],
            current_version=2
        )
        created = await db_manager.mongodb.create(doc, test_tenant)
        
        # Get latest version
        latest = await db_manager.mongodb.get_latest_content_version(
            str(created.id), test_tenant
        )
        
        assert latest is not None
        assert latest["title"] == "V2"
        assert latest["content"] == "Version 2 - Latest"


class TestOptimizationResults:
    """Test optimization result storage."""
    
    @pytest.mark.asyncio
    async def test_store_optimization_result(self, test_tenant):
        """Test storing optimization results with suggestions."""
        result = OptimizationResult(
            org_id=test_tenant,
            content_id=str(uuid4()),
            optimization_type=OptimizationType.SEO,
            model_name="gpt-4",
            model_parameters={"temperature": 0.7},
            before_scores={"seo": 65.0, "readability": 70.0},
            after_scores={"seo": 85.0, "readability": 75.0},
            processing_time_ms=1250,
            tokens_used=500,
            api_cost=0.025
        )
        
        # Add suggestions
        result.suggestions = [
            OptimizationSuggestion(
                type=OptimizationType.SEO,
                priority="high",
                description="Add meta description",
                expected_score_improvement=10.0,
                confidence=0.9
            ),
            OptimizationSuggestion(
                type=OptimizationType.KEYWORDS,
                priority="medium",
                description="Include target keywords in H2 tags",
                original_text="Current heading",
                suggested_text="Current heading with keyword",
                confidence=0.85
            )
        ]
        
        created = await db_manager.mongodb.create(result, test_tenant)
        
        assert created.id is not None
        assert len(created.suggestions) == 2
        assert created.after_scores["seo"] == 85.0
        assert created.processing_time_ms == 1250
    
    @pytest.mark.asyncio
    async def test_query_optimization_history(self, test_tenant):
        """Test querying optimization history for content."""
        content_id = str(uuid4())
        
        # Create multiple optimization results
        optimization_types = [
            OptimizationType.SEO,
            OptimizationType.READABILITY,
            OptimizationType.AI_REWRITE
        ]
        
        for opt_type in optimization_types:
            result = OptimizationResult(
                org_id=test_tenant,
                content_id=content_id,
                optimization_type=opt_type,
                model_name="gpt-4",
                before_scores={str(opt_type): 60.0},
                after_scores={str(opt_type): 80.0}
            )
            await db_manager.mongodb.create(result, test_tenant)
        
        # Query by content ID
        results = await db_manager.mongodb.get_many(
            OptimizationResult,
            {"content_id": content_id},
            test_tenant
        )
        
        assert len(results) == 3
        opt_types = [r.optimization_type for r in results]
        assert set(opt_types) == set(optimization_types)


class TestAnalytics:
    """Test analytics event tracking."""
    
    @pytest.mark.asyncio
    async def test_track_analytics_event(self, test_tenant):
        """Test tracking analytics events."""
        event = AnalyticsEvent(
            org_id=test_tenant,
            event_type="page_view",
            event_name="content_viewed",
            user_id=str(uuid4()),
            content_id=str(uuid4()),
            session_id="session123",
            properties={
                "page_title": "Test Content",
                "time_on_page": 45.2,
                "scroll_depth": 0.75
            },
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0...",
            country="US",
            region="CA",
            city="San Francisco"
        )
        
        created = await db_manager.mongodb.track_event(event.dict(), test_tenant)
        
        assert created.id is not None
        assert created.event_type == "page_view"
        assert created.properties["time_on_page"] == 45.2
    
    @pytest.mark.asyncio
    async def test_aggregate_content_analytics(self, test_tenant):
        """Test aggregating analytics for content."""
        content_id = str(uuid4())
        user_ids = [str(uuid4()) for _ in range(3)]
        
        # Create various events
        events = [
            {"event_type": "page_view", "user_id": user_ids[0]},
            {"event_type": "page_view", "user_id": user_ids[1]},
            {"event_type": "page_view", "user_id": user_ids[0]},  # Same user
            {"event_type": "click", "user_id": user_ids[0]},
            {"event_type": "click", "user_id": user_ids[2]},
            {"event_type": "conversion", "user_id": user_ids[1]}
        ]
        
        for event_data in events:
            event = AnalyticsEvent(
                org_id=test_tenant,
                event_name="test_event",
                content_id=content_id,
                **event_data
            )
            await db_manager.mongodb.create(event, test_tenant)
        
        # Aggregate analytics
        start_date = datetime.utcnow() - timedelta(hours=1)
        end_date = datetime.utcnow() + timedelta(hours=1)
        
        analytics = await db_manager.mongodb.get_content_analytics(
            content_id, test_tenant, start_date, end_date
        )
        
        # Verify aggregation
        event_summary = {item["event_type"]: item for item in analytics}
        
        assert event_summary["page_view"]["count"] == 3
        assert event_summary["page_view"]["unique_users"] == 2  # Two unique users
        assert event_summary["click"]["count"] == 2
        assert event_summary["conversion"]["count"] == 1


class TestTextSearch:
    """Test full-text search functionality."""
    
    @pytest.mark.asyncio
    async def test_text_search(self, test_tenant):
        """Test full-text search on content."""
        # Create content with searchable text
        contents = [
            {
                "title": "Introduction to Machine Learning",
                "search_content": "Machine learning is a subset of artificial intelligence that enables systems to learn from data."
            },
            {
                "title": "Deep Learning Fundamentals",
                "search_content": "Deep learning uses neural networks with multiple layers to process complex patterns."
            },
            {
                "title": "Natural Language Processing",
                "search_content": "NLP enables machines to understand and process human language effectively."
            }
        ]
        
        for content_data in contents:
            doc = ContentDocument(
                org_id=test_tenant,
                postgres_content_id=str(uuid4()),
                title=content_data["title"],
                slug=content_data["title"].lower().replace(" ", "-"),
                content_type=ContentType.ARTICLE,
                search_content=content_data["search_content"]
            )
            await db_manager.mongodb.create(doc, test_tenant)
        
        # Search for "learning"
        results = await db_manager.mongodb.text_search(
            ContentDocument, "learning", test_tenant
        )
        
        # Should find machine learning and deep learning articles
        assert len(results) >= 2
        titles = [r.title for r in results]
        assert any("Machine Learning" in title for title in titles)
        assert any("Deep Learning" in title for title in titles)


class TestPerformanceMetrics:
    """Test storing and querying performance metrics."""
    
    @pytest.mark.asyncio
    async def test_content_performance_tracking(self, test_tenant):
        """Test tracking content performance metrics."""
        content_id = str(uuid4())
        
        # Create hourly performance metric
        perf = ContentPerformance(
            org_id=test_tenant,
            content_id=content_id,
            period_type="hourly",
            period_start=datetime.utcnow().replace(minute=0, second=0, microsecond=0),
            period_end=datetime.utcnow(),
            views=150,
            unique_views=120,
            average_time_on_page=45.5,
            bounce_rate=0.35,
            clicks=25,
            conversions=5,
            conversion_rate=0.033,
            organic_traffic=80,
            device_breakdown={"desktop": 90, "mobile": 50, "tablet": 10},
            country_breakdown={"US": 100, "UK": 30, "CA": 20}
        )
        
        created = await db_manager.mongodb.create(perf, test_tenant)
        
        assert created.views == 150
        assert created.conversion_rate == 0.033
        assert created.device_breakdown["desktop"] == 90
    
    @pytest.mark.asyncio
    async def test_ai_usage_tracking(self, test_tenant):
        """Test tracking AI model usage."""
        usage = AIModelUsage(
            org_id=test_tenant,
            period_type="daily",
            period_start=datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
            period_end=datetime.utcnow(),
            model_provider="openai",
            model_name="gpt-4",
            request_count=100,
            success_count=98,
            error_count=2,
            prompt_tokens=50000,
            completion_tokens=25000,
            total_tokens=75000,
            prompt_cost=1.5,
            completion_cost=1.5,
            total_cost=3.0,
            average_latency_ms=850.5,
            error_types={"rate_limit": 1, "timeout": 1}
        )
        
        created = await db_manager.mongodb.create(usage, test_tenant)
        
        assert created.request_count == 100
        assert created.success_count == 98
        assert created.total_cost == 3.0
        assert created.error_types["rate_limit"] == 1


class TestBulkOperations:
    """Test bulk operations in MongoDB."""
    
    @pytest.mark.asyncio
    async def test_bulk_insert(self, test_tenant):
        """Test bulk document insertion."""
        documents = []
        for i in range(100):
            doc = ContentDocument(
                org_id=test_tenant,
                postgres_content_id=str(uuid4()),
                title=f"Bulk Test {i}",
                slug=f"bulk-test-{i}",
                content_type=ContentType.ARTICLE,
                tags=[f"bulk", f"tag{i % 10}"]
            )
            documents.append(doc)
        
        created = await db_manager.mongodb.create_many(documents, test_tenant)
        
        assert len(created) == 100
        
        # Verify they were created
        count = await db_manager.mongodb.get_many(
            ContentDocument,
            {"tags": "bulk"},
            test_tenant,
            limit=200
        )
        assert len(count) == 100
    
    @pytest.mark.asyncio
    async def test_bulk_update(self, test_tenant):
        """Test bulk update operations."""
        # Create test documents
        for i in range(10):
            doc = ContentDocument(
                org_id=test_tenant,
                postgres_content_id=str(uuid4()),
                title=f"Update Test {i}",
                slug=f"update-test-{i}",
                content_type=ContentType.ARTICLE,
                tags=["needs-update"]
            )
            await db_manager.mongodb.create(doc, test_tenant)
        
        # Bulk update
        updated_count = await db_manager.mongodb.update_many(
            ContentDocument,
            {"tags": "needs-update"},
            {"$set": {"tags": ["updated"], "$currentDate": {"updated_at": True}}},
            test_tenant
        )
        
        assert updated_count == 10
        
        # Verify updates
        updated = await db_manager.mongodb.get_many(
            ContentDocument,
            {"tags": "updated"},
            test_tenant
        )
        assert len(updated) == 10