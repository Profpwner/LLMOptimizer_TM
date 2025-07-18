"""Synchronization service for managing data sync jobs."""

import asyncio
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid
from collections import defaultdict

from app.models import Integration, SyncJob, SyncStatus, SyncDirection, SyncLog
from app.integrations.registry import IntegrationRegistry
from app.core.database import get_collection
from app.utils.rate_limiter import RateLimiter
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ConflictResolution(str, Enum):
    """Conflict resolution strategies."""
    SOURCE_WINS = "source_wins"
    TARGET_WINS = "target_wins"
    MERGE = "merge"
    MANUAL = "manual"
    SKIP = "skip"


class SyncService:
    """Service for managing synchronization jobs."""
    
    def __init__(self):
        self.running_jobs: Dict[str, asyncio.Task] = {}
        self.job_queues: Dict[str, asyncio.Queue] = defaultdict(lambda: asyncio.Queue())
        self.rate_limiter = RateLimiter(
            redis_url=settings.redis_url,
            prefix="sync_service"
        )
        self._deduplication_cache: Dict[str, Set[str]] = defaultdict(set)
        self._shutdown = False
        
    async def create_sync_job(
        self,
        integration_id: str,
        user_id: str,
        organization_id: str,
        entity_types: List[str],
        direction: SyncDirection = SyncDirection.BIDIRECTIONAL,
        filters: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None,
        scheduled_at: Optional[datetime] = None,
    ) -> SyncJob:
        """Create a new sync job."""
        job = SyncJob(
            id=str(uuid.uuid4()),
            integration_id=integration_id,
            user_id=user_id,
            organization_id=organization_id,
            status=SyncStatus.PENDING,
            direction=direction,
            entity_types=entity_types,
            filters=filters or {},
            options=options or {},
            scheduled_at=scheduled_at,
            created_at=datetime.utcnow()
        )
        
        # Save to database
        collection = await get_collection("sync_jobs")
        await collection.insert_one(job.dict(by_alias=True))
        
        # Queue for processing if not scheduled
        if not scheduled_at or scheduled_at <= datetime.utcnow():
            await self.job_queues[integration_id].put(job)
        
        logger.info(f"Created sync job {job.id} for integration {integration_id}")
        return job
    
    async def start_processing(self):
        """Start processing sync jobs."""
        logger.info("Starting sync service...")
        
        # Start workers for each integration type
        workers = []
        for integration_type in ["hubspot", "salesforce", "wordpress", "github"]:
            for i in range(2):  # 2 workers per integration type
                worker = asyncio.create_task(
                    self._process_jobs(f"{integration_type}_worker_{i}")
                )
                workers.append(worker)
        
        # Start scheduled job processor
        scheduler = asyncio.create_task(self._process_scheduled_jobs())
        workers.append(scheduler)
        
        # Wait for shutdown or worker failure
        try:
            await asyncio.gather(*workers)
        except Exception as e:
            logger.error(f"Worker failed: {e}")
            self._shutdown = True
    
    async def stop_processing(self):
        """Stop processing sync jobs."""
        logger.info("Stopping sync service...")
        self._shutdown = True
        
        # Cancel running jobs
        for job_id, task in self.running_jobs.items():
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled job {job_id}")
        
        # Wait for tasks to complete
        if self.running_jobs:
            await asyncio.gather(*self.running_jobs.values(), return_exceptions=True)
    
    async def _process_jobs(self, worker_name: str):
        """Process sync jobs from queues."""
        logger.info(f"Worker {worker_name} started")
        
        while not self._shutdown:
            try:
                # Get job from any queue
                job = None
                for queue in self.job_queues.values():
                    try:
                        job = await asyncio.wait_for(queue.get(), timeout=1.0)
                        break
                    except asyncio.TimeoutError:
                        continue
                
                if not job:
                    continue
                
                # Process job
                logger.info(f"Worker {worker_name} processing job {job.id}")
                task = asyncio.create_task(self._execute_sync_job(job))
                self.running_jobs[job.id] = task
                
                # Wait for completion
                await task
                
                # Remove from running jobs
                self.running_jobs.pop(job.id, None)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")
                await asyncio.sleep(5)
        
        logger.info(f"Worker {worker_name} stopped")
    
    async def _process_scheduled_jobs(self):
        """Process scheduled sync jobs."""
        logger.info("Scheduled job processor started")
        
        while not self._shutdown:
            try:
                # Find scheduled jobs that are ready
                collection = await get_collection("sync_jobs")
                now = datetime.utcnow()
                
                cursor = collection.find({
                    "status": SyncStatus.PENDING.value,
                    "scheduled_at": {"$lte": now}
                })
                
                async for doc in cursor:
                    job = SyncJob(**doc)
                    
                    # Queue for processing
                    await self.job_queues[job.integration_id].put(job)
                    
                    # Update status
                    await collection.update_one(
                        {"_id": job.id},
                        {"$set": {"status": SyncStatus.RUNNING.value}}
                    )
                
                # Wait before next check
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduled job processor error: {e}")
                await asyncio.sleep(60)
        
        logger.info("Scheduled job processor stopped")
    
    async def _execute_sync_job(self, job: SyncJob):
        """Execute a sync job."""
        try:
            # Update job status
            await self._update_job_status(job.id, SyncStatus.RUNNING, started_at=datetime.utcnow())
            
            # Get integration
            integrations_collection = await get_collection("integrations")
            integration_doc = await integrations_collection.find_one({"_id": job.integration_id})
            if not integration_doc:
                raise ValueError(f"Integration {job.integration_id} not found")
            
            integration = Integration(**integration_doc)
            
            # Get integration handler
            handler_class = IntegrationRegistry.get(integration.integration_type)
            if not handler_class:
                raise ValueError(f"No handler for integration type {integration.integration_type}")
            
            # Create handler instance
            async with handler_class(integration) as handler:
                # Test connection
                if not await handler.test_connection():
                    raise ConnectionError("Integration connection test failed")
                
                # Clear deduplication cache for this job
                self._deduplication_cache[job.id].clear()
                
                # Execute sync based on direction
                if job.direction == SyncDirection.INBOUND:
                    results = await self._sync_inbound(handler, job)
                elif job.direction == SyncDirection.OUTBOUND:
                    results = await self._sync_outbound(handler, job)
                else:  # BIDIRECTIONAL
                    results = await self._sync_bidirectional(handler, job)
                
                # Update job with results
                await self._update_job_status(
                    job.id,
                    SyncStatus.COMPLETED,
                    completed_at=datetime.utcnow(),
                    total_records=results["total_processed"],
                    processed_records=results["total_processed"],
                    created_records=results["created"],
                    updated_records=results["updated"],
                    error_records=results["errors"]
                )
                
                # Update integration last sync time
                await integrations_collection.update_one(
                    {"_id": integration.id},
                    {
                        "$set": {
                            "last_sync_at": datetime.utcnow(),
                            "total_syncs": integration.total_syncs + 1,
                            "successful_syncs": integration.successful_syncs + 1
                        }
                    }
                )
                
                logger.info(f"Sync job {job.id} completed successfully: {results}")
                
        except Exception as e:
            logger.error(f"Sync job {job.id} failed: {e}")
            
            # Update job status
            await self._update_job_status(
                job.id,
                SyncStatus.FAILED,
                completed_at=datetime.utcnow(),
                error_message=str(e)
            )
            
            # Update integration error count
            if 'integration' in locals():
                await integrations_collection.update_one(
                    {"_id": integration.id},
                    {
                        "$set": {
                            "error_message": str(e),
                            "failed_syncs": integration.failed_syncs + 1
                        }
                    }
                )
            
            # Log error
            await self._log_sync_error(job.id, job.integration_id, str(e))
    
    async def _sync_inbound(self, handler, job: SyncJob) -> Dict[str, Any]:
        """Sync data from integration to our system."""
        results = await handler.sync_data(job)
        
        # Apply conflict resolution if needed
        if job.options.get("conflict_resolution"):
            results = await self._resolve_conflicts(
                results,
                job.options["conflict_resolution"],
                SyncDirection.INBOUND
            )
        
        return results
    
    async def _sync_outbound(self, handler, job: SyncJob) -> Dict[str, Any]:
        """Sync data from our system to integration."""
        # This would need to be implemented based on your data model
        # For now, return empty results
        return {
            "total_processed": 0,
            "created": 0,
            "updated": 0,
            "errors": 0,
            "entity_results": {}
        }
    
    async def _sync_bidirectional(self, handler, job: SyncJob) -> Dict[str, Any]:
        """Sync data in both directions."""
        # First sync inbound
        inbound_results = await self._sync_inbound(handler, job)
        
        # Then sync outbound
        outbound_results = await self._sync_outbound(handler, job)
        
        # Combine results
        return {
            "total_processed": inbound_results["total_processed"] + outbound_results["total_processed"],
            "created": inbound_results["created"] + outbound_results["created"],
            "updated": inbound_results["updated"] + outbound_results["updated"],
            "errors": inbound_results["errors"] + outbound_results["errors"],
            "entity_results": {
                "inbound": inbound_results["entity_results"],
                "outbound": outbound_results["entity_results"]
            }
        }
    
    async def _resolve_conflicts(
        self,
        results: Dict[str, Any],
        strategy: str,
        direction: SyncDirection
    ) -> Dict[str, Any]:
        """Resolve conflicts based on strategy."""
        if strategy == ConflictResolution.SOURCE_WINS:
            # Source data always wins
            return results
        elif strategy == ConflictResolution.TARGET_WINS:
            # Target data wins, skip updates
            results["skipped_records"] = results.get("updated", 0)
            results["updated"] = 0
            return results
        elif strategy == ConflictResolution.MERGE:
            # Merge logic would be implemented here
            return results
        elif strategy == ConflictResolution.MANUAL:
            # Queue for manual review
            await self._queue_manual_conflicts(results)
            return results
        else:  # SKIP
            # Skip conflicts
            results["skipped_records"] = results.get("updated", 0)
            results["updated"] = 0
            return results
    
    async def _queue_manual_conflicts(self, results: Dict[str, Any]):
        """Queue conflicts for manual review."""
        # This would create conflict records for manual review
        pass
    
    def _is_duplicate(self, job_id: str, entity_type: str, entity_id: str) -> bool:
        """Check if entity is a duplicate within this sync job."""
        key = f"{entity_type}:{entity_id}"
        if key in self._deduplication_cache[job_id]:
            return True
        self._deduplication_cache[job_id].add(key)
        return False
    
    async def _update_job_status(self, job_id: str, status: SyncStatus, **kwargs):
        """Update sync job status."""
        collection = await get_collection("sync_jobs")
        
        update_data = {"status": status.value}
        update_data.update(kwargs)
        
        await collection.update_one(
            {"_id": job_id},
            {"$set": update_data}
        )
    
    async def _log_sync_error(self, job_id: str, integration_id: str, error_message: str):
        """Log sync error."""
        log = SyncLog(
            id=str(uuid.uuid4()),
            sync_job_id=job_id,
            integration_id=integration_id,
            timestamp=datetime.utcnow(),
            level="ERROR",
            operation="sync_job",
            entity_type="job",
            message=error_message,
            error={"message": error_message}
        )
        
        collection = await get_collection("sync_logs")
        await collection.insert_one(log.dict(by_alias=True))
    
    async def get_sync_job(self, job_id: str) -> Optional[SyncJob]:
        """Get sync job by ID."""
        collection = await get_collection("sync_jobs")
        doc = await collection.find_one({"_id": job_id})
        return SyncJob(**doc) if doc else None
    
    async def get_sync_jobs(
        self,
        integration_id: Optional[str] = None,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        status: Optional[SyncStatus] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[SyncJob]:
        """Get sync jobs with filters."""
        collection = await get_collection("sync_jobs")
        
        filters = {}
        if integration_id:
            filters["integration_id"] = integration_id
        if user_id:
            filters["user_id"] = user_id
        if organization_id:
            filters["organization_id"] = organization_id
        if status:
            filters["status"] = status.value
        
        cursor = collection.find(filters).sort("created_at", -1).skip(skip).limit(limit)
        
        jobs = []
        async for doc in cursor:
            jobs.append(SyncJob(**doc))
        
        return jobs
    
    async def cancel_sync_job(self, job_id: str) -> bool:
        """Cancel a sync job."""
        # Check if job is running
        if job_id in self.running_jobs:
            task = self.running_jobs[job_id]
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled running job {job_id}")
        
        # Update status
        await self._update_job_status(job_id, SyncStatus.CANCELLED)
        return True
    
    async def get_sync_logs(
        self,
        job_id: Optional[str] = None,
        integration_id: Optional[str] = None,
        level: Optional[str] = None,
        entity_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
        skip: int = 0
    ) -> List[SyncLog]:
        """Get sync logs with filters."""
        collection = await get_collection("sync_logs")
        
        filters = {}
        if job_id:
            filters["sync_job_id"] = job_id
        if integration_id:
            filters["integration_id"] = integration_id
        if level:
            filters["level"] = level
        if entity_type:
            filters["entity_type"] = entity_type
        if start_time or end_time:
            timestamp_filter = {}
            if start_time:
                timestamp_filter["$gte"] = start_time
            if end_time:
                timestamp_filter["$lte"] = end_time
            filters["timestamp"] = timestamp_filter
        
        cursor = collection.find(filters).sort("timestamp", -1).skip(skip).limit(limit)
        
        logs = []
        async for doc in cursor:
            logs.append(SyncLog(**doc))
        
        return logs
    
    async def get_sync_statistics(
        self,
        integration_id: Optional[str] = None,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get sync statistics."""
        collection = await get_collection("sync_jobs")
        
        # Build match stage
        match_stage = {
            "created_at": {
                "$gte": datetime.utcnow() - timedelta(days=days)
            }
        }
        if integration_id:
            match_stage["integration_id"] = integration_id
        if user_id:
            match_stage["user_id"] = user_id
        if organization_id:
            match_stage["organization_id"] = organization_id
        
        # Aggregate statistics
        pipeline = [
            {"$match": match_stage},
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                    "total_records": {"$sum": "$total_records"},
                    "processed_records": {"$sum": "$processed_records"},
                    "created_records": {"$sum": "$created_records"},
                    "updated_records": {"$sum": "$updated_records"},
                    "error_records": {"$sum": "$error_records"}
                }
            }
        ]
        
        cursor = collection.aggregate(pipeline)
        
        stats = {
            "period_days": days,
            "total_jobs": 0,
            "by_status": {},
            "totals": {
                "records_processed": 0,
                "records_created": 0,
                "records_updated": 0,
                "records_errored": 0
            }
        }
        
        async for doc in cursor:
            status = doc["_id"]
            stats["by_status"][status] = doc["count"]
            stats["total_jobs"] += doc["count"]
            stats["totals"]["records_processed"] += doc["processed_records"]
            stats["totals"]["records_created"] += doc["created_records"]
            stats["totals"]["records_updated"] += doc["updated_records"]
            stats["totals"]["records_errored"] += doc["error_records"]
        
        return stats


# Singleton instance
sync_service = SyncService()