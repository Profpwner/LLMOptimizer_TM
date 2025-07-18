"""Webhook service for handling incoming webhooks."""

import asyncio
import json
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid
import hmac
import hashlib
from collections import defaultdict

from app.models import Integration, IntegrationType
from app.integrations.registry import IntegrationRegistry
from app.core.database import get_collection
from app.core.config import get_settings
from app.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)
settings = get_settings()


class WebhookStatus(str, Enum):
    """Webhook processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookEvent:
    """Webhook event model."""
    
    def __init__(
        self,
        id: str,
        integration_id: str,
        integration_type: IntegrationType,
        event_type: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        signature: Optional[str] = None,
        source_ip: Optional[str] = None,
        received_at: Optional[datetime] = None,
        status: WebhookStatus = WebhookStatus.PENDING,
        attempts: int = 0,
        processed_at: Optional[datetime] = None,
        error_message: Optional[str] = None
    ):
        self.id = id
        self.integration_id = integration_id
        self.integration_type = integration_type
        self.event_type = event_type
        self.payload = payload
        self.headers = headers
        self.signature = signature
        self.source_ip = source_ip
        self.received_at = received_at or datetime.utcnow()
        self.status = status
        self.attempts = attempts
        self.processed_at = processed_at
        self.error_message = error_message
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "_id": self.id,
            "integration_id": self.integration_id,
            "integration_type": self.integration_type.value,
            "event_type": self.event_type,
            "payload": self.payload,
            "headers": self.headers,
            "signature": self.signature,
            "source_ip": self.source_ip,
            "received_at": self.received_at,
            "status": self.status.value,
            "attempts": self.attempts,
            "processed_at": self.processed_at,
            "error_message": self.error_message
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WebhookEvent":
        """Create from dictionary."""
        return cls(
            id=data["_id"],
            integration_id=data["integration_id"],
            integration_type=IntegrationType(data["integration_type"]),
            event_type=data["event_type"],
            payload=data["payload"],
            headers=data["headers"],
            signature=data.get("signature"),
            source_ip=data.get("source_ip"),
            received_at=data.get("received_at"),
            status=WebhookStatus(data["status"]),
            attempts=data.get("attempts", 0),
            processed_at=data.get("processed_at"),
            error_message=data.get("error_message")
        )


class WebhookService:
    """Service for managing webhooks."""
    
    def __init__(self):
        self.event_queue = asyncio.Queue()
        self.retry_queue = asyncio.Queue()
        self.dead_letter_queue = asyncio.Queue()
        self.rate_limiter = RateLimiter(
            redis_url=settings.redis_url,
            prefix="webhook_service"
        )
        self._shutdown = False
        self._event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._workers: List[asyncio.Task] = []
        
        # Retry configuration
        self.max_retries = 3
        self.retry_delays = [60, 300, 900]  # 1 min, 5 min, 15 min
        
    async def start_processing(self):
        """Start webhook processing."""
        logger.info("Starting webhook service...")
        
        # Start worker tasks
        num_workers = 4
        for i in range(num_workers):
            worker = asyncio.create_task(self._process_events(f"worker_{i}"))
            self._workers.append(worker)
        
        # Start retry processor
        retry_processor = asyncio.create_task(self._process_retries())
        self._workers.append(retry_processor)
        
        # Start dead letter processor
        dead_letter_processor = asyncio.create_task(self._process_dead_letters())
        self._workers.append(dead_letter_processor)
        
        # Wait for shutdown
        try:
            await asyncio.gather(*self._workers)
        except Exception as e:
            logger.error(f"Webhook service error: {e}")
            self._shutdown = True
    
    async def stop_processing(self):
        """Stop webhook processing."""
        logger.info("Stopping webhook service...")
        self._shutdown = True
        
        # Cancel workers
        for worker in self._workers:
            if not worker.done():
                worker.cancel()
        
        # Wait for workers to finish
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
    
    async def receive_webhook(
        self,
        integration_id: str,
        integration_type: IntegrationType,
        event_type: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        signature: Optional[str] = None,
        source_ip: Optional[str] = None
    ) -> str:
        """Receive and queue a webhook for processing."""
        # Create event
        event = WebhookEvent(
            id=str(uuid.uuid4()),
            integration_id=integration_id,
            integration_type=integration_type,
            event_type=event_type,
            payload=payload,
            headers=headers,
            signature=signature,
            source_ip=source_ip
        )
        
        # Save to database
        collection = await get_collection("webhook_events")
        await collection.insert_one(event.to_dict())
        
        # Queue for processing
        await self.event_queue.put(event)
        
        logger.info(f"Received webhook {event.id} for integration {integration_id}")
        return event.id
    
    async def _process_events(self, worker_name: str):
        """Process webhook events."""
        logger.info(f"Webhook worker {worker_name} started")
        
        while not self._shutdown:
            try:
                # Get event from queue
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                
                # Process event
                await self._process_single_event(event)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"Webhook worker {worker_name} stopped")
    
    async def _process_single_event(self, event: WebhookEvent):
        """Process a single webhook event."""
        try:
            # Update status
            await self._update_event_status(event.id, WebhookStatus.PROCESSING)
            
            # Rate limiting
            rate_limit_key = f"{event.integration_type}:{event.integration_id}"
            if not await self.rate_limiter.check_rate_limit(rate_limit_key):
                # Requeue for later
                await asyncio.sleep(1)
                await self.event_queue.put(event)
                return
            
            # Get integration
            integrations_collection = await get_collection("integrations")
            integration_doc = await integrations_collection.find_one({"_id": event.integration_id})
            if not integration_doc:
                raise ValueError(f"Integration {event.integration_id} not found")
            
            integration = Integration(**integration_doc)
            
            # Verify webhook signature
            handler_class = IntegrationRegistry.get(integration.integration_type)
            if not handler_class:
                raise ValueError(f"No handler for integration type {integration.integration_type}")
            
            async with handler_class(integration) as handler:
                # Verify signature if provided
                if event.signature:
                    payload_bytes = json.dumps(event.payload, separators=(',', ':')).encode()
                    if not handler.verify_webhook_signature(event.signature, payload_bytes):
                        raise ValueError("Invalid webhook signature")
                
                # Handle webhook
                await handler.handle_webhook(event.event_type, event.payload)
                
                # Call custom handlers
                await self._call_custom_handlers(event)
            
            # Update status
            await self._update_event_status(
                event.id,
                WebhookStatus.COMPLETED,
                processed_at=datetime.utcnow()
            )
            
            logger.info(f"Successfully processed webhook {event.id}")
            
        except Exception as e:
            logger.error(f"Failed to process webhook {event.id}: {e}")
            
            # Update attempt count
            event.attempts += 1
            
            # Check if should retry
            if event.attempts < self.max_retries:
                # Queue for retry
                await self._update_event_status(
                    event.id,
                    WebhookStatus.RETRYING,
                    attempts=event.attempts,
                    error_message=str(e)
                )
                await self.retry_queue.put((event, self.retry_delays[event.attempts - 1]))
            else:
                # Move to dead letter queue
                await self._update_event_status(
                    event.id,
                    WebhookStatus.FAILED,
                    attempts=event.attempts,
                    error_message=str(e)
                )
                await self.dead_letter_queue.put(event)
    
    async def _process_retries(self):
        """Process webhook retry queue."""
        logger.info("Webhook retry processor started")
        
        retry_tasks = []
        
        while not self._shutdown:
            try:
                # Get event from retry queue
                event, delay = await asyncio.wait_for(self.retry_queue.get(), timeout=1.0)
                
                # Schedule retry
                retry_task = asyncio.create_task(self._retry_event(event, delay))
                retry_tasks.append(retry_task)
                
                # Clean up completed tasks
                retry_tasks = [t for t in retry_tasks if not t.done()]
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Retry processor error: {e}")
                await asyncio.sleep(1)
        
        # Cancel pending retries
        for task in retry_tasks:
            if not task.done():
                task.cancel()
        
        if retry_tasks:
            await asyncio.gather(*retry_tasks, return_exceptions=True)
        
        logger.info("Webhook retry processor stopped")
    
    async def _retry_event(self, event: WebhookEvent, delay: int):
        """Retry a webhook event after delay."""
        logger.info(f"Scheduling retry for webhook {event.id} in {delay} seconds")
        await asyncio.sleep(delay)
        
        # Requeue for processing
        await self.event_queue.put(event)
    
    async def _process_dead_letters(self):
        """Process dead letter queue."""
        logger.info("Dead letter processor started")
        
        while not self._shutdown:
            try:
                # Get event from dead letter queue
                event = await asyncio.wait_for(self.dead_letter_queue.get(), timeout=1.0)
                
                # Log to dead letter collection
                await self._save_dead_letter(event)
                
                # Notify administrators
                await self._notify_dead_letter(event)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Dead letter processor error: {e}")
                await asyncio.sleep(1)
        
        logger.info("Dead letter processor stopped")
    
    async def _save_dead_letter(self, event: WebhookEvent):
        """Save event to dead letter collection."""
        collection = await get_collection("webhook_dead_letters")
        
        dead_letter = {
            "_id": str(uuid.uuid4()),
            "event_id": event.id,
            "integration_id": event.integration_id,
            "integration_type": event.integration_type.value,
            "event_type": event.event_type,
            "payload": event.payload,
            "headers": event.headers,
            "error_message": event.error_message,
            "attempts": event.attempts,
            "received_at": event.received_at,
            "failed_at": datetime.utcnow()
        }
        
        await collection.insert_one(dead_letter)
        logger.warning(f"Webhook {event.id} moved to dead letter queue")
    
    async def _notify_dead_letter(self, event: WebhookEvent):
        """Notify administrators about dead letter event."""
        # This would send notifications via email, Slack, etc.
        pass
    
    async def _call_custom_handlers(self, event: WebhookEvent):
        """Call custom event handlers."""
        handlers = self._event_handlers.get(f"{event.integration_type}:{event.event_type}", [])
        
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Custom handler error: {e}")
    
    def register_handler(self, integration_type: IntegrationType, event_type: str, handler: Callable):
        """Register a custom webhook handler."""
        key = f"{integration_type}:{event_type}"
        self._event_handlers[key].append(handler)
        logger.info(f"Registered handler for {key}")
    
    async def _update_event_status(self, event_id: str, status: WebhookStatus, **kwargs):
        """Update webhook event status."""
        collection = await get_collection("webhook_events")
        
        update_data = {"status": status.value}
        update_data.update(kwargs)
        
        await collection.update_one(
            {"_id": event_id},
            {"$set": update_data}
        )
    
    async def get_webhook_event(self, event_id: str) -> Optional[WebhookEvent]:
        """Get webhook event by ID."""
        collection = await get_collection("webhook_events")
        doc = await collection.find_one({"_id": event_id})
        return WebhookEvent.from_dict(doc) if doc else None
    
    async def get_webhook_events(
        self,
        integration_id: Optional[str] = None,
        integration_type: Optional[IntegrationType] = None,
        event_type: Optional[str] = None,
        status: Optional[WebhookStatus] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[WebhookEvent]:
        """Get webhook events with filters."""
        collection = await get_collection("webhook_events")
        
        filters = {}
        if integration_id:
            filters["integration_id"] = integration_id
        if integration_type:
            filters["integration_type"] = integration_type.value
        if event_type:
            filters["event_type"] = event_type
        if status:
            filters["status"] = status.value
        if start_time or end_time:
            received_filter = {}
            if start_time:
                received_filter["$gte"] = start_time
            if end_time:
                received_filter["$lte"] = end_time
            filters["received_at"] = received_filter
        
        cursor = collection.find(filters).sort("received_at", -1).skip(skip).limit(limit)
        
        events = []
        async for doc in cursor:
            events.append(WebhookEvent.from_dict(doc))
        
        return events
    
    async def reprocess_webhook(self, event_id: str) -> bool:
        """Reprocess a webhook event."""
        event = await self.get_webhook_event(event_id)
        if not event:
            return False
        
        # Reset status and attempts
        event.status = WebhookStatus.PENDING
        event.attempts = 0
        event.error_message = None
        
        # Update in database
        await self._update_event_status(
            event_id,
            WebhookStatus.PENDING,
            attempts=0,
            error_message=None
        )
        
        # Queue for processing
        await self.event_queue.put(event)
        
        logger.info(f"Requeued webhook {event_id} for processing")
        return True
    
    async def get_webhook_statistics(
        self,
        integration_id: Optional[str] = None,
        integration_type: Optional[IntegrationType] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get webhook statistics."""
        collection = await get_collection("webhook_events")
        
        # Build match stage
        match_stage = {
            "received_at": {
                "$gte": datetime.utcnow() - timedelta(days=days)
            }
        }
        if integration_id:
            match_stage["integration_id"] = integration_id
        if integration_type:
            match_stage["integration_type"] = integration_type.value
        
        # Aggregate statistics
        pipeline = [
            {"$match": match_stage},
            {
                "$group": {
                    "_id": {
                        "status": "$status",
                        "event_type": "$event_type"
                    },
                    "count": {"$sum": 1},
                    "avg_attempts": {"$avg": "$attempts"}
                }
            }
        ]
        
        cursor = collection.aggregate(pipeline)
        
        stats = {
            "period_days": days,
            "total_events": 0,
            "by_status": defaultdict(int),
            "by_event_type": defaultdict(int),
            "by_status_and_type": defaultdict(lambda: defaultdict(int)),
            "average_attempts": 0
        }
        
        total_attempts = 0
        async for doc in cursor:
            status = doc["_id"]["status"]
            event_type = doc["_id"]["event_type"]
            count = doc["count"]
            avg_attempts = doc["avg_attempts"]
            
            stats["total_events"] += count
            stats["by_status"][status] += count
            stats["by_event_type"][event_type] += count
            stats["by_status_and_type"][status][event_type] = count
            total_attempts += avg_attempts * count
        
        if stats["total_events"] > 0:
            stats["average_attempts"] = total_attempts / stats["total_events"]
        
        # Convert defaultdicts to regular dicts for JSON serialization
        stats["by_status"] = dict(stats["by_status"])
        stats["by_event_type"] = dict(stats["by_event_type"])
        stats["by_status_and_type"] = {
            status: dict(types)
            for status, types in stats["by_status_and_type"].items()
        }
        
        return stats
    
    def generate_webhook_secret(self) -> str:
        """Generate a secure webhook secret."""
        return hashlib.sha256(uuid.uuid4().bytes).hexdigest()


# Singleton instance
webhook_service = WebhookService()