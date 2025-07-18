"""
Core workflow execution engine with state management.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from enum import Enum
import json
from collections import defaultdict

from motor.motor_asyncio import AsyncIOMotorDatabase
import redis.asyncio as redis
from celery import Celery
from pydantic import BaseModel

from .definitions import (
    WorkflowDefinition, WorkflowInstance, WorkflowStatus,
    WorkflowStep, StepType
)
from .state import WorkflowStateManager


logger = logging.getLogger(__name__)


class WorkflowEvent(str, Enum):
    """Workflow lifecycle events."""
    STARTED = "workflow.started"
    STEP_STARTED = "step.started"
    STEP_COMPLETED = "step.completed"
    STEP_FAILED = "step.failed"
    STEP_RETRYING = "step.retrying"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    WORKFLOW_CANCELLED = "workflow.cancelled"
    WORKFLOW_PAUSED = "workflow.paused"
    WORKFLOW_RESUMED = "workflow.resumed"


class WorkflowState(BaseModel):
    """Current state of a workflow execution."""
    instance_id: str
    workflow_id: str
    status: WorkflowStatus
    current_step: Optional[str] = None
    progress: float = 0.0
    message: Optional[str] = None
    metadata: Dict[str, Any] = {}


class WorkflowEngine:
    """
    Core workflow execution engine.
    Manages workflow lifecycle, state transitions, and step execution.
    """
    
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        redis_client: redis.Redis,
        celery_app: Celery
    ):
        self.db = db
        self.redis = redis_client
        self.celery = celery_app
        self.state_manager = WorkflowStateManager(db, redis_client)
        
        # Event handlers
        self._event_handlers: Dict[WorkflowEvent, List[callable]] = defaultdict(list)
        
        # Active workflows tracking
        self._active_workflows: Set[str] = set()
        
    async def start_workflow(
        self,
        workflow_def: WorkflowDefinition,
        input_data: Dict[str, Any],
        triggered_by: Optional[str] = None,
        parent_instance_id: Optional[str] = None
    ) -> WorkflowInstance:
        """
        Start a new workflow instance.
        """
        # Create workflow instance
        instance = WorkflowInstance(
            workflow_id=workflow_def.id,
            workflow_version=workflow_def.version,
            input_data=input_data,
            triggered_by=triggered_by,
            parent_instance_id=parent_instance_id,
            started_at=datetime.utcnow(),
            context={
                "workflow_name": workflow_def.name,
                "category": workflow_def.category,
                "tags": workflow_def.tags
            }
        )
        
        # Save instance to database
        await self._save_instance(instance)
        
        # Initialize state
        await self.state_manager.initialize_state(instance.id, workflow_def)
        
        # Track active workflow
        self._active_workflows.add(instance.id)
        
        # Emit start event
        await self._emit_event(
            WorkflowEvent.STARTED,
            instance_id=instance.id,
            workflow_id=workflow_def.id,
            input_data=input_data
        )
        
        # Start execution
        asyncio.create_task(self._execute_workflow(instance, workflow_def))
        
        return instance
    
    async def _execute_workflow(
        self,
        instance: WorkflowInstance,
        workflow_def: WorkflowDefinition
    ):
        """
        Main workflow execution loop.
        """
        try:
            # Update status to running
            instance.status = WorkflowStatus.RUNNING
            await self._update_instance(instance)
            
            # Create step lookup
            steps_by_id = {step.id: step for step in workflow_def.steps}
            
            # Get execution order
            execution_order = self._get_execution_order(workflow_def)
            
            # Execute steps
            for step_id in execution_order:
                if instance.status not in [WorkflowStatus.RUNNING, WorkflowStatus.RETRY]:
                    break
                
                step = steps_by_id[step_id]
                
                # Check if step should be executed
                if not await self._should_execute_step(step, instance):
                    logger.info(f"Skipping step {step.id} due to condition")
                    continue
                
                # Wait for dependencies
                await self._wait_for_dependencies(step, instance)
                
                # Execute step
                success = await self._execute_step(step, instance, workflow_def)
                
                if not success and not step.allow_failure:
                    # Workflow failed
                    instance.status = WorkflowStatus.FAILED
                    instance.error_message = f"Step {step.name} failed"
                    await self._update_instance(instance)
                    await self._emit_event(
                        WorkflowEvent.WORKFLOW_FAILED,
                        instance_id=instance.id,
                        step_id=step.id
                    )
                    return
            
            # Workflow completed successfully
            instance.status = WorkflowStatus.COMPLETED
            instance.completed_at = datetime.utcnow()
            await self._update_instance(instance)
            
            await self._emit_event(
                WorkflowEvent.WORKFLOW_COMPLETED,
                instance_id=instance.id,
                output_data=instance.output_data
            )
            
        except Exception as e:
            logger.error(f"Workflow execution error: {e}")
            instance.status = WorkflowStatus.FAILED
            instance.error_message = str(e)
            await self._update_instance(instance)
            
            await self._emit_event(
                WorkflowEvent.WORKFLOW_FAILED,
                instance_id=instance.id,
                error=str(e)
            )
        
        finally:
            # Remove from active workflows
            self._active_workflows.discard(instance.id)
    
    async def _execute_step(
        self,
        step: WorkflowStep,
        instance: WorkflowInstance,
        workflow_def: WorkflowDefinition
    ) -> bool:
        """
        Execute a single workflow step.
        Returns True if successful, False otherwise.
        """
        retry_count = 0
        max_retries = step.retry_policy.max_attempts if step.retry_policy else 1
        
        while retry_count < max_retries:
            try:
                # Update current step
                instance.current_step_id = step.id
                await self._update_instance(instance)
                
                # Emit step started event
                await self._emit_event(
                    WorkflowEvent.STEP_STARTED,
                    instance_id=instance.id,
                    step_id=step.id,
                    step_name=step.name
                )
                
                # Prepare task arguments
                task_args = self._prepare_task_args(step, instance)
                
                # Execute task
                if step.type == StepType.PARALLEL:
                    # Handle parallel execution
                    result = await self._execute_parallel_tasks(step, task_args)
                else:
                    # Execute single task
                    task = self.celery.send_task(
                        step.task_name,
                        args=[task_args],
                        queue='content_optimization',
                        time_limit=step.timeout_seconds
                    )
                    
                    # Wait for result
                    result = await self._wait_for_task_result(
                        task,
                        timeout=step.timeout_seconds
                    )
                
                # Store result
                instance.add_step_result(step.id, result)
                
                # Update context with step output
                if isinstance(result, dict):
                    instance.context.update(result.get('context', {}))
                    instance.output_data.update(result.get('output', {}))
                
                await self._update_instance(instance)
                
                # Emit step completed event
                await self._emit_event(
                    WorkflowEvent.STEP_COMPLETED,
                    instance_id=instance.id,
                    step_id=step.id,
                    result=result
                )
                
                return True
                
            except Exception as e:
                retry_count += 1
                logger.error(f"Step {step.id} failed (attempt {retry_count}/{max_retries}): {e}")
                
                if retry_count < max_retries:
                    # Calculate retry delay
                    delay = step.retry_policy.delay_seconds * (
                        step.retry_policy.backoff_multiplier ** (retry_count - 1)
                    )
                    delay = min(delay, step.retry_policy.max_delay_seconds)
                    
                    await self._emit_event(
                        WorkflowEvent.STEP_RETRYING,
                        instance_id=instance.id,
                        step_id=step.id,
                        retry_count=retry_count,
                        delay=delay
                    )
                    
                    await asyncio.sleep(delay)
                else:
                    # Step failed
                    instance.mark_step_failed(step.id, str(e))
                    await self._update_instance(instance)
                    
                    await self._emit_event(
                        WorkflowEvent.STEP_FAILED,
                        instance_id=instance.id,
                        step_id=step.id,
                        error=str(e)
                    )
                    
                    return False
    
    async def pause_workflow(self, instance_id: str) -> bool:
        """Pause a running workflow."""
        instance = await self._get_instance(instance_id)
        if not instance or instance.status != WorkflowStatus.RUNNING:
            return False
        
        instance.status = WorkflowStatus.PAUSED
        instance.paused_at = datetime.utcnow()
        await self._update_instance(instance)
        
        await self._emit_event(
            WorkflowEvent.WORKFLOW_PAUSED,
            instance_id=instance_id
        )
        
        return True
    
    async def resume_workflow(self, instance_id: str) -> bool:
        """Resume a paused workflow."""
        instance = await self._get_instance(instance_id)
        if not instance or instance.status != WorkflowStatus.PAUSED:
            return False
        
        workflow_def = await self._get_workflow_definition(instance.workflow_id)
        if not workflow_def:
            return False
        
        instance.status = WorkflowStatus.RUNNING
        instance.paused_at = None
        await self._update_instance(instance)
        
        await self._emit_event(
            WorkflowEvent.WORKFLOW_RESUMED,
            instance_id=instance_id
        )
        
        # Resume execution
        asyncio.create_task(self._execute_workflow(instance, workflow_def))
        
        return True
    
    async def cancel_workflow(self, instance_id: str) -> bool:
        """Cancel a workflow execution."""
        instance = await self._get_instance(instance_id)
        if not instance or instance.status in [
            WorkflowStatus.COMPLETED,
            WorkflowStatus.CANCELLED
        ]:
            return False
        
        instance.status = WorkflowStatus.CANCELLED
        instance.completed_at = datetime.utcnow()
        await self._update_instance(instance)
        
        # Cancel any pending tasks
        # TODO: Implement task cancellation
        
        await self._emit_event(
            WorkflowEvent.WORKFLOW_CANCELLED,
            instance_id=instance_id
        )
        
        return True
    
    async def get_workflow_state(self, instance_id: str) -> Optional[WorkflowState]:
        """Get current workflow state."""
        instance = await self._get_instance(instance_id)
        if not instance:
            return None
        
        # Calculate progress
        workflow_def = await self._get_workflow_definition(instance.workflow_id)
        total_steps = len(workflow_def.steps) if workflow_def else 0
        completed_steps = len(instance.completed_steps)
        progress = (completed_steps / total_steps * 100) if total_steps > 0 else 0
        
        return WorkflowState(
            instance_id=instance.id,
            workflow_id=instance.workflow_id,
            status=instance.status,
            current_step=instance.current_step_id,
            progress=progress,
            message=instance.error_message,
            metadata={
                "completed_steps": instance.completed_steps,
                "failed_steps": instance.failed_steps,
                "started_at": instance.started_at.isoformat() if instance.started_at else None,
                "completed_at": instance.completed_at.isoformat() if instance.completed_at else None
            }
        )
    
    def register_event_handler(self, event: WorkflowEvent, handler: callable):
        """Register an event handler."""
        self._event_handlers[event].append(handler)
    
    # Helper methods
    
    def _get_execution_order(self, workflow_def: WorkflowDefinition) -> List[str]:
        """
        Determine step execution order using topological sort.
        """
        # Build dependency graph
        graph = defaultdict(list)
        in_degree = defaultdict(int)
        
        for step in workflow_def.steps:
            in_degree[step.id] = len(step.depends_on)
            for dep in step.depends_on:
                graph[dep].append(step.id)
        
        # Topological sort
        queue = [step.id for step in workflow_def.steps if not step.depends_on]
        order = []
        
        while queue:
            current = queue.pop(0)
            order.append(current)
            
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return order
    
    async def _should_execute_step(
        self,
        step: WorkflowStep,
        instance: WorkflowInstance
    ) -> bool:
        """
        Check if a step should be executed based on conditions.
        """
        if not step.condition:
            return True
        
        # TODO: Implement Jinja2 condition evaluation
        # For now, always return True
        return True
    
    async def _wait_for_dependencies(
        self,
        step: WorkflowStep,
        instance: WorkflowInstance
    ):
        """
        Wait for step dependencies to complete.
        """
        while True:
            pending_deps = [
                dep for dep in step.depends_on
                if dep not in instance.completed_steps and dep not in instance.failed_steps
            ]
            
            if not pending_deps:
                break
            
            await asyncio.sleep(1)
            # Refresh instance
            instance = await self._get_instance(instance.id)
    
    def _prepare_task_args(
        self,
        step: WorkflowStep,
        instance: WorkflowInstance
    ) -> Dict[str, Any]:
        """
        Prepare arguments for task execution.
        """
        return {
            "workflow_instance_id": instance.id,
            "step_id": step.id,
            "input_data": instance.input_data,
            "context": instance.context,
            "step_results": instance.step_results,
            **step.task_args
        }
    
    async def _wait_for_task_result(self, task, timeout: int):
        """
        Wait for Celery task result with timeout.
        """
        # TODO: Implement proper async Celery result handling
        # For now, use sync get with timeout
        return task.get(timeout=timeout)
    
    async def _execute_parallel_tasks(
        self,
        step: WorkflowStep,
        task_args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute multiple tasks in parallel.
        """
        # TODO: Implement parallel task execution
        return {"status": "completed", "results": []}
    
    async def _save_instance(self, instance: WorkflowInstance):
        """Save workflow instance to database."""
        await self.db.workflow_instances.insert_one(
            instance.dict(exclude_none=True)
        )
    
    async def _update_instance(self, instance: WorkflowInstance):
        """Update workflow instance in database."""
        await self.db.workflow_instances.update_one(
            {"id": instance.id},
            {"$set": instance.dict(exclude_none=True)}
        )
    
    async def _get_instance(self, instance_id: str) -> Optional[WorkflowInstance]:
        """Get workflow instance from database."""
        doc = await self.db.workflow_instances.find_one({"id": instance_id})
        return WorkflowInstance(**doc) if doc else None
    
    async def _get_workflow_definition(
        self,
        workflow_id: str
    ) -> Optional[WorkflowDefinition]:
        """Get workflow definition from database."""
        doc = await self.db.workflow_definitions.find_one({"id": workflow_id})
        return WorkflowDefinition(**doc) if doc else None
    
    async def _emit_event(self, event: WorkflowEvent, **kwargs):
        """Emit workflow event to handlers."""
        for handler in self._event_handlers[event]:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event, **kwargs)
                else:
                    handler(event, **kwargs)
            except Exception as e:
                logger.error(f"Event handler error: {e}")