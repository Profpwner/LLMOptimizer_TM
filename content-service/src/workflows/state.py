"""
Workflow state management with Redis for distributed coordination.
"""

import json
import logging
from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timedelta
import asyncio

import redis.asyncio as redis
from motor.motor_asyncio import AsyncIOMotorDatabase

from .definitions import WorkflowDefinition, WorkflowInstance, WorkflowStatus


logger = logging.getLogger(__name__)


class WorkflowStateManager:
    """
    Manages workflow state in Redis for distributed execution.
    Provides atomic operations and distributed locking.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase, redis_client: redis.Redis):
        self.db = db
        self.redis = redis_client
        self.key_prefix = "workflow:state:"
        self.lock_prefix = "workflow:lock:"
        self.ttl = 86400  # 24 hours default TTL
    
    async def initialize_state(
        self,
        instance_id: str,
        workflow_def: WorkflowDefinition
    ):
        """Initialize workflow state in Redis."""
        key = self._get_state_key(instance_id)
        
        state = {
            "instance_id": instance_id,
            "workflow_id": workflow_def.id,
            "status": WorkflowStatus.PENDING,
            "created_at": datetime.utcnow().isoformat(),
            "total_steps": len(workflow_def.steps),
            "completed_steps": [],
            "failed_steps": [],
            "current_step": None,
            "step_states": {
                step.id: {
                    "status": "pending",
                    "attempts": 0,
                    "last_attempt": None,
                    "result": None
                }
                for step in workflow_def.steps
            }
        }
        
        await self.redis.setex(
            key,
            self.ttl,
            json.dumps(state)
        )
    
    async def get_state(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow state from Redis."""
        key = self._get_state_key(instance_id)
        data = await self.redis.get(key)
        
        if data:
            return json.loads(data)
        
        # Fallback to database
        instance = await self.db.workflow_instances.find_one({"id": instance_id})
        if instance:
            # Restore to Redis
            state = self._instance_to_state(instance)
            await self.redis.setex(key, self.ttl, json.dumps(state))
            return state
        
        return None
    
    async def update_status(
        self,
        instance_id: str,
        status: WorkflowStatus,
        error: Optional[str] = None
    ):
        """Update workflow status atomically."""
        key = self._get_state_key(instance_id)
        
        async with self._get_lock(instance_id):
            state = await self.get_state(instance_id)
            if not state:
                return
            
            state["status"] = status
            state["updated_at"] = datetime.utcnow().isoformat()
            
            if error:
                state["error"] = error
            
            if status == WorkflowStatus.COMPLETED:
                state["completed_at"] = datetime.utcnow().isoformat()
            
            await self.redis.setex(key, self.ttl, json.dumps(state))
    
    async def update_step_state(
        self,
        instance_id: str,
        step_id: str,
        status: str,
        result: Optional[Any] = None,
        error: Optional[str] = None
    ):
        """Update individual step state."""
        key = self._get_state_key(instance_id)
        
        async with self._get_lock(instance_id):
            state = await self.get_state(instance_id)
            if not state:
                return
            
            step_state = state["step_states"].get(step_id, {})
            step_state["status"] = status
            step_state["last_attempt"] = datetime.utcnow().isoformat()
            step_state["attempts"] = step_state.get("attempts", 0) + 1
            
            if result is not None:
                step_state["result"] = result
            
            if error:
                step_state["error"] = error
            
            state["step_states"][step_id] = step_state
            
            # Update completed/failed lists
            if status == "completed" and step_id not in state["completed_steps"]:
                state["completed_steps"].append(step_id)
            elif status == "failed" and step_id not in state["failed_steps"]:
                state["failed_steps"].append(step_id)
            
            # Update current step
            if status == "running":
                state["current_step"] = step_id
            elif state.get("current_step") == step_id:
                state["current_step"] = None
            
            await self.redis.setex(key, self.ttl, json.dumps(state))
    
    async def get_ready_steps(
        self,
        instance_id: str,
        workflow_def: WorkflowDefinition
    ) -> List[str]:
        """Get steps that are ready to execute."""
        state = await self.get_state(instance_id)
        if not state:
            return []
        
        ready_steps = []
        step_lookup = {step.id: step for step in workflow_def.steps}
        
        for step_id, step_state in state["step_states"].items():
            if step_state["status"] != "pending":
                continue
            
            step = step_lookup.get(step_id)
            if not step:
                continue
            
            # Check if all dependencies are completed
            deps_completed = all(
                dep in state["completed_steps"]
                for dep in step.depends_on
            )
            
            if deps_completed:
                ready_steps.append(step_id)
        
        return ready_steps
    
    async def acquire_step_lock(
        self,
        instance_id: str,
        step_id: str,
        ttl: int = 300
    ) -> bool:
        """
        Acquire a lock for step execution.
        Prevents duplicate execution in distributed environment.
        """
        lock_key = f"{self.lock_prefix}step:{instance_id}:{step_id}"
        
        # Try to acquire lock with TTL
        acquired = await self.redis.set(
            lock_key,
            "1",
            nx=True,
            ex=ttl
        )
        
        return bool(acquired)
    
    async def release_step_lock(self, instance_id: str, step_id: str):
        """Release step execution lock."""
        lock_key = f"{self.lock_prefix}step:{instance_id}:{step_id}"
        await self.redis.delete(lock_key)
    
    async def extend_step_lock(
        self,
        instance_id: str,
        step_id: str,
        ttl: int = 300
    ):
        """Extend step lock TTL."""
        lock_key = f"{self.lock_prefix}step:{instance_id}:{step_id}"
        await self.redis.expire(lock_key, ttl)
    
    async def get_active_workflows(self) -> List[str]:
        """Get list of active workflow instance IDs."""
        pattern = f"{self.key_prefix}*"
        cursor = 0
        active_instances = []
        
        while True:
            cursor, keys = await self.redis.scan(
                cursor,
                match=pattern,
                count=100
            )
            
            for key in keys:
                instance_id = key.decode().replace(self.key_prefix, "")
                state = await self.get_state(instance_id)
                
                if state and state["status"] in [
                    WorkflowStatus.PENDING,
                    WorkflowStatus.RUNNING,
                    WorkflowStatus.RETRY
                ]:
                    active_instances.append(instance_id)
            
            if cursor == 0:
                break
        
        return active_instances
    
    async def cleanup_expired_states(self):
        """Clean up expired workflow states."""
        # Redis handles expiration automatically with TTL
        # This method can be used for additional cleanup if needed
        pass
    
    async def get_workflow_metrics(self) -> Dict[str, Any]:
        """Get workflow execution metrics."""
        pattern = f"{self.key_prefix}*"
        cursor = 0
        
        metrics = {
            "total": 0,
            "by_status": {},
            "average_duration": 0,
            "failed_steps": 0,
            "completed_today": 0
        }
        
        durations = []
        today = datetime.utcnow().date()
        
        while True:
            cursor, keys = await self.redis.scan(
                cursor,
                match=pattern,
                count=100
            )
            
            for key in keys:
                instance_id = key.decode().replace(self.key_prefix, "")
                state = await self.get_state(instance_id)
                
                if not state:
                    continue
                
                metrics["total"] += 1
                
                # Count by status
                status = state.get("status", "unknown")
                metrics["by_status"][status] = metrics["by_status"].get(status, 0) + 1
                
                # Calculate duration for completed workflows
                if status == WorkflowStatus.COMPLETED:
                    if "created_at" in state and "completed_at" in state:
                        created = datetime.fromisoformat(state["created_at"])
                        completed = datetime.fromisoformat(state["completed_at"])
                        duration = (completed - created).total_seconds()
                        durations.append(duration)
                        
                        if completed.date() == today:
                            metrics["completed_today"] += 1
                
                # Count failed steps
                metrics["failed_steps"] += len(state.get("failed_steps", []))
            
            if cursor == 0:
                break
        
        # Calculate average duration
        if durations:
            metrics["average_duration"] = sum(durations) / len(durations)
        
        return metrics
    
    # Helper methods
    
    def _get_state_key(self, instance_id: str) -> str:
        """Get Redis key for workflow state."""
        return f"{self.key_prefix}{instance_id}"
    
    def _get_lock_key(self, instance_id: str) -> str:
        """Get Redis key for workflow lock."""
        return f"{self.lock_prefix}{instance_id}"
    
    async def _get_lock(self, instance_id: str, timeout: int = 10):
        """Get distributed lock for workflow operations."""
        lock_key = self._get_lock_key(instance_id)
        
        # Simple lock implementation
        # In production, use redis-py's Lock or redlock
        acquired = False
        start_time = asyncio.get_event_loop().time()
        
        while not acquired:
            acquired = await self.redis.set(
                lock_key,
                "1",
                nx=True,
                ex=timeout
            )
            
            if acquired:
                break
            
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError(f"Failed to acquire lock for {instance_id}")
            
            await asyncio.sleep(0.1)
        
        try:
            yield
        finally:
            await self.redis.delete(lock_key)
    
    def _instance_to_state(self, instance: dict) -> dict:
        """Convert workflow instance to state format."""
        return {
            "instance_id": instance["id"],
            "workflow_id": instance["workflow_id"],
            "status": instance["status"],
            "created_at": instance["started_at"].isoformat() if instance.get("started_at") else None,
            "completed_at": instance["completed_at"].isoformat() if instance.get("completed_at") else None,
            "total_steps": len(instance.get("step_results", {})),
            "completed_steps": instance.get("completed_steps", []),
            "failed_steps": instance.get("failed_steps", []),
            "current_step": instance.get("current_step_id"),
            "step_states": {
                step_id: {
                    "status": "completed" if step_id in instance.get("completed_steps", [])
                    else "failed" if step_id in instance.get("failed_steps", [])
                    else "pending",
                    "result": instance.get("step_results", {}).get(step_id)
                }
                for step_id in instance.get("step_results", {}).keys()
            }
        }