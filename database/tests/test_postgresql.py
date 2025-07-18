"""Tests for PostgreSQL database operations."""

import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import datetime, timedelta

from shared.database.manager import db_manager
from database.schemas.postgresql.models import (
    Organization, User, Content, ContentOptimization,
    APIKey, UserSession, PlanType, ContentStatus
)


class TestPostgreSQLCRUD:
    """Test PostgreSQL CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_create_organization(self, db_setup):
        """Test creating an organization."""
        org_id = str(uuid4())
        org = Organization(
            id=org_id,
            name="Test Organization",
            slug="test-org",
            plan_type=PlanType.PROFESSIONAL,
            max_users=50,
            is_active=True
        )
        
        created = await db_manager.postgresql.create(org)
        
        assert created.id == org_id
        assert created.name == "Test Organization"
        assert created.created_at is not None
        
        # Cleanup
        await db_manager.postgresql.delete(created, soft_delete=False)
    
    @pytest.mark.asyncio
    async def test_get_organization(self, test_tenant):
        """Test retrieving an organization."""
        org = await db_manager.postgresql.get(Organization, test_tenant)
        
        assert org is not None
        assert str(org.id) == test_tenant
        assert org.is_active is True
    
    @pytest.mark.asyncio
    async def test_update_organization(self, test_tenant):
        """Test updating an organization."""
        org = await db_manager.postgresql.get(Organization, test_tenant)
        
        updates = {
            "max_users": 100,
            "plan_type": PlanType.ENTERPRISE
        }
        
        updated = await db_manager.postgresql.update(org, updates, test_tenant)
        
        assert updated.max_users == 100
        assert updated.plan_type == PlanType.ENTERPRISE
        assert updated.updated_at > org.updated_at
    
    @pytest.mark.asyncio
    async def test_soft_delete(self, test_tenant):
        """Test soft delete functionality."""
        # Create content
        content = Content(
            id=str(uuid4()),
            org_id=test_tenant,
            title="Test Content for Deletion",
            slug="test-delete",
            content_type="article"
        )
        created = await db_manager.postgresql.create(content, test_tenant)
        
        # Soft delete
        await db_manager.postgresql.delete(created, test_tenant, soft_delete=True)
        
        # Verify soft deleted
        deleted = await db_manager.postgresql.get(Content, created.id, test_tenant)
        assert deleted.is_deleted is True
        assert deleted.deleted_at is not None
    
    @pytest.mark.asyncio
    async def test_batch_create(self, test_tenant):
        """Test creating multiple records at once."""
        contents = []
        for i in range(5):
            content = Content(
                id=str(uuid4()),
                org_id=test_tenant,
                title=f"Batch Content {i}",
                slug=f"batch-content-{i}",
                content_type="article"
            )
            contents.append(content)
        
        created = await db_manager.postgresql.create_many(contents, test_tenant)
        
        assert len(created) == 5
        for i, content in enumerate(created):
            assert content.title == f"Batch Content {i}"


class TestMultiTenancy:
    """Test multi-tenant functionality."""
    
    @pytest.mark.asyncio
    async def test_tenant_isolation(self, db_setup):
        """Test that tenants cannot access each other's data."""
        # Create two tenants
        tenant1_id = str(uuid4())
        tenant2_id = str(uuid4())
        
        for tenant_id in [tenant1_id, tenant2_id]:
            org_data = {
                "name": f"Tenant {tenant_id[:8]}",
                "slug": f"tenant-{tenant_id[:8]}",
                "plan_type": "professional"
            }
            await db_manager.create_tenant(tenant_id, org_data)
        
        # Create content for tenant 1
        content1 = Content(
            id=str(uuid4()),
            org_id=tenant1_id,
            title="Tenant 1 Content",
            slug="tenant-1-content",
            content_type="article"
        )
        await db_manager.postgresql.create(content1, tenant1_id)
        
        # Try to access from tenant 2 context
        content = await db_manager.postgresql.get(
            Content, content1.id, tenant2_id
        )
        assert content is None
        
        # Verify tenant 1 can access
        content = await db_manager.postgresql.get(
            Content, content1.id, tenant1_id
        )
        assert content is not None
        assert content.title == "Tenant 1 Content"
        
        # Cleanup
        await db_manager.delete_tenant(tenant1_id)
        await db_manager.delete_tenant(tenant2_id)
    
    @pytest.mark.asyncio
    async def test_cross_tenant_update_protection(self, db_setup):
        """Test that tenants cannot update each other's data."""
        # Create two tenants
        tenant1_id = str(uuid4())
        tenant2_id = str(uuid4())
        
        for tenant_id in [tenant1_id, tenant2_id]:
            org_data = {
                "name": f"Tenant {tenant_id[:8]}",
                "slug": f"tenant-{tenant_id[:8]}",
                "plan_type": "professional"
            }
            await db_manager.create_tenant(tenant_id, org_data)
        
        # Create content for tenant 1
        content = Content(
            id=str(uuid4()),
            org_id=tenant1_id,
            title="Protected Content",
            slug="protected-content",
            content_type="article"
        )
        created = await db_manager.postgresql.create(content, tenant1_id)
        
        # Try to update from tenant 2 context
        with pytest.raises(PermissionError):
            await db_manager.postgresql.update(
                created,
                {"title": "Hacked!"},
                tenant2_id
            )
        
        # Cleanup
        await db_manager.delete_tenant(tenant1_id)
        await db_manager.delete_tenant(tenant2_id)


class TestRelationships:
    """Test database relationships."""
    
    @pytest.mark.asyncio
    async def test_user_organization_relationship(self, test_tenant, test_user):
        """Test many-to-many relationship between users and organizations."""
        # Query user's organizations
        query = """
        SELECT o.* FROM organizations o
        JOIN user_organizations uo ON o.id = uo.organization_id
        WHERE uo.user_id = $1
        """
        
        orgs = await db_manager.postgresql.execute_query(
            query, {"user_id": test_user.id}
        )
        
        assert len(orgs) == 1
        assert str(orgs[0]["id"]) == test_tenant
    
    @pytest.mark.asyncio
    async def test_content_optimization_relationship(self, test_tenant, test_content):
        """Test one-to-many relationship for content optimizations."""
        # Create optimization
        optimization = ContentOptimization(
            id=str(uuid4()),
            org_id=test_tenant,
            content_id=test_content.id,
            optimization_type="seo",
            before_score=65.0,
            after_score=85.0,
            improvement_percentage=30.77
        )
        
        created = await db_manager.postgresql.create(optimization, test_tenant)
        
        # Query optimizations for content
        query = """
        SELECT * FROM content_optimizations
        WHERE content_id = $1 AND org_id = $2
        ORDER BY created_at DESC
        """
        
        optimizations = await db_manager.postgresql.execute_query(
            query, {"content_id": test_content.id, "org_id": test_tenant}
        )
        
        assert len(optimizations) == 1
        assert optimizations[0]["optimization_type"] == "seo"
        assert float(optimizations[0]["improvement_percentage"]) == pytest.approx(30.77)


class TestPerformance:
    """Test performance-related features."""
    
    @pytest.mark.asyncio
    async def test_connection_pooling(self, test_tenant):
        """Test connection pool behavior."""
        # Get initial stats
        initial_stats = await db_manager.postgresql.get_connection_stats()
        
        # Perform multiple concurrent operations
        tasks = []
        for i in range(20):
            content = Content(
                id=str(uuid4()),
                org_id=test_tenant,
                title=f"Concurrent Content {i}",
                slug=f"concurrent-{i}",
                content_type="article"
            )
            task = db_manager.postgresql.create(content, test_tenant)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # Check pool stats
        final_stats = await db_manager.postgresql.get_connection_stats()
        
        assert len(results) == 20
        assert final_stats["pool"]["pool_size"] >= initial_stats["pool"]["pool_size"]
    
    @pytest.mark.asyncio
    async def test_bulk_operations_performance(self, test_tenant):
        """Test performance of bulk operations."""
        import time
        
        # Single inserts
        start_time = time.time()
        single_contents = []
        for i in range(100):
            content = Content(
                id=str(uuid4()),
                org_id=test_tenant,
                title=f"Single Content {i}",
                slug=f"single-{i}",
                content_type="article"
            )
            await db_manager.postgresql.create(content, test_tenant)
        single_time = time.time() - start_time
        
        # Bulk insert
        bulk_contents = []
        for i in range(100):
            content = Content(
                id=str(uuid4()),
                org_id=test_tenant,
                title=f"Bulk Content {i}",
                slug=f"bulk-{i}",
                content_type="article"
            )
            bulk_contents.append(content)
        
        start_time = time.time()
        await db_manager.postgresql.create_many(bulk_contents, test_tenant)
        bulk_time = time.time() - start_time
        
        # Bulk should be significantly faster
        assert bulk_time < single_time * 0.5  # At least 2x faster
    
    @pytest.mark.asyncio
    async def test_slow_query_detection(self, test_tenant):
        """Test slow query detection."""
        # Execute a potentially slow query
        query = """
        SELECT c1.*, c2.title as related_title
        FROM content c1
        CROSS JOIN content c2
        WHERE c1.org_id = $1 AND c2.org_id = $1
        LIMIT 1000
        """
        
        await db_manager.postgresql.execute_query(
            query, {"org_id": test_tenant}
        )
        
        # Check slow queries
        slow_queries = await db_manager.postgresql.get_slow_queries(
            threshold_ms=1
        )
        
        # Should detect some queries (may include our query or others)
        assert isinstance(slow_queries, list)


class TestTransactions:
    """Test transaction handling."""
    
    @pytest.mark.asyncio
    async def test_transaction_commit(self, test_tenant):
        """Test successful transaction commit."""
        content_id = str(uuid4())
        
        async with db_manager.postgresql.transaction(test_tenant) as session:
            # Create content
            content = Content(
                id=content_id,
                org_id=test_tenant,
                title="Transaction Test",
                slug="transaction-test",
                content_type="article"
            )
            session.add(content)
            
            # Create optimization
            optimization = ContentOptimization(
                id=str(uuid4()),
                org_id=test_tenant,
                content_id=content_id,
                optimization_type="seo",
                before_score=50.0,
                after_score=80.0
            )
            session.add(optimization)
        
        # Verify both were created
        content = await db_manager.postgresql.get(Content, content_id, test_tenant)
        assert content is not None
        assert content.title == "Transaction Test"
        
        optimizations = await db_manager.postgresql.get_many(
            ContentOptimization,
            {"content_id": content_id},
            test_tenant
        )
        assert len(optimizations) == 1
    
    @pytest.mark.asyncio
    async def test_transaction_rollback(self, test_tenant):
        """Test transaction rollback on error."""
        content_id = str(uuid4())
        
        try:
            async with db_manager.postgresql.transaction(test_tenant) as session:
                # Create content
                content = Content(
                    id=content_id,
                    org_id=test_tenant,
                    title="Rollback Test",
                    slug="rollback-test",
                    content_type="article"
                )
                session.add(content)
                
                # Force an error
                raise Exception("Simulated error")
        except Exception:
            pass
        
        # Verify nothing was created
        content = await db_manager.postgresql.get(Content, content_id, test_tenant)
        assert content is None


class TestQuotasAndLimits:
    """Test quota enforcement."""
    
    @pytest.mark.asyncio
    async def test_content_quota_enforcement(self, test_tenant):
        """Test that content creation respects quotas."""
        # Get organization and set low quota
        org = await db_manager.postgresql.get(Organization, test_tenant)
        await db_manager.postgresql.update(
            org,
            {"max_content_items": 3},
            test_tenant
        )
        
        # Create content up to limit
        for i in range(3):
            content = Content(
                id=str(uuid4()),
                org_id=test_tenant,
                title=f"Quota Test {i}",
                slug=f"quota-test-{i}",
                content_type="article"
            )
            await db_manager.postgresql.create(content, test_tenant)
        
        # Verify quota check
        from database.utils.validation import TenantQuotaValidator
        can_create = await TenantQuotaValidator.check_content_quota(test_tenant)
        assert can_create is False
        
        # Try to create one more (should be prevented at application level)
        can_create = await TenantQuotaValidator.check_content_quota(test_tenant, 1)
        assert can_create is False