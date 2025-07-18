"""
Workflow executor for managing Celery task execution.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

from celery import Celery, Task, group, chain, chord
from celery.result import AsyncResult, GroupResult
from celery.exceptions import TimeoutError as CeleryTimeoutError

from .definitions import WorkflowStep, StepType
from .state import WorkflowStateManager


logger = logging.getLogger(__name__)


class WorkflowTask(Task):
    """Base class for workflow tasks with automatic state tracking."""
    
    def __init__(self):
        super().__init__()
        self.state_manager: Optional[WorkflowStateManager] = None
    
    def before_start(self, task_id, args, kwargs):
        """Called before task execution starts."""
        if 'workflow_instance_id' in kwargs and 'step_id' in kwargs:
            # Update step state to running
            asyncio.create_task(
                self.state_manager.update_step_state(
                    kwargs['workflow_instance_id'],
                    kwargs['step_id'],
                    'running'
                )
            )
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called on successful task completion."""
        if 'workflow_instance_id' in kwargs and 'step_id' in kwargs:
            # Update step state to completed
            asyncio.create_task(
                self.state_manager.update_step_state(
                    kwargs['workflow_instance_id'],
                    kwargs['step_id'],
                    'completed',
                    result=retval
                )
            )
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called on task failure."""
        if 'workflow_instance_id' in kwargs and 'step_id' in kwargs:
            # Update step state to failed
            asyncio.create_task(
                self.state_manager.update_step_state(
                    kwargs['workflow_instance_id'],
                    kwargs['step_id'],
                    'failed',
                    error=str(exc)
                )
            )


class WorkflowExecutor:
    """
    Manages Celery task execution for workflows.
    Handles task scheduling, monitoring, and result collection.
    """
    
    def __init__(
        self,
        celery_app: Celery,
        state_manager: WorkflowStateManager,
        max_workers: int = 10
    ):
        self.celery = celery_app
        self.state_manager = state_manager
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Configure task base class
        self.celery.Task = WorkflowTask
        WorkflowTask.state_manager = state_manager
        
        # Task registry
        self._task_registry: Dict[str, Task] = {}
        
        # Active task tracking
        self._active_tasks: Dict[str, AsyncResult] = {}
    
    def register_task(self, name: str, task_func: callable):
        """Register a workflow task."""
        task = self.celery.task(
            name=name,
            base=WorkflowTask,
            bind=True
        )(task_func)
        
        self._task_registry[name] = task
        return task
    
    async def execute_step(
        self,
        step: WorkflowStep,
        context: Dict[str, Any],
        timeout: Optional[int] = None
    ) -> Any:
        """Execute a workflow step."""
        timeout = timeout or step.timeout_seconds
        
        try:
            # Acquire step lock
            lock_acquired = await self.state_manager.acquire_step_lock(
                context['workflow_instance_id'],
                step.id,
                ttl=timeout
            )
            
            if not lock_acquired:
                logger.warning(f"Failed to acquire lock for step {step.id}")
                return None
            
            # Update state to running
            await self.state_manager.update_step_state(
                context['workflow_instance_id'],
                step.id,
                'running'
            )
            
            # Execute based on step type
            if step.type == StepType.PARALLEL:
                result = await self._execute_parallel_step(step, context, timeout)
            elif step.type == StepType.BRANCHING:
                result = await self._execute_branching_step(step, context, timeout)
            else:
                result = await self._execute_single_task(step, context, timeout)
            
            # Update state to completed
            await self.state_manager.update_step_state(
                context['workflow_instance_id'],
                step.id,
                'completed',
                result=result
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Step execution failed: {e}")
            
            # Update state to failed
            await self.state_manager.update_step_state(
                context['workflow_instance_id'],
                step.id,
                'failed',
                error=str(e)
            )
            
            raise
        
        finally:
            # Release step lock
            await self.state_manager.release_step_lock(
                context['workflow_instance_id'],
                step.id
            )
    
    async def _execute_single_task(
        self,
        step: WorkflowStep,
        context: Dict[str, Any],
        timeout: int
    ) -> Any:
        """Execute a single Celery task."""
        # Prepare task arguments
        task_args = {
            **context,
            **step.task_args,
            'step_id': step.id,
            'step_name': step.name
        }
        
        # Send task to Celery
        task = self.celery.send_task(
            step.task_name,
            kwargs=task_args,
            queue='content_optimization',
            time_limit=timeout,
            soft_time_limit=int(timeout * 0.9)  # Soft limit at 90%
        )
        
        # Track active task
        self._active_tasks[f"{context['workflow_instance_id']}:{step.id}"] = task
        
        # Wait for result
        try:
            result = await self._wait_for_result(task, timeout)
            return result
        finally:
            # Remove from active tasks
            self._active_tasks.pop(f"{context['workflow_instance_id']}:{step.id}", None)
    
    async def _execute_parallel_step(
        self,
        step: WorkflowStep,
        context: Dict[str, Any],
        timeout: int
    ) -> Dict[str, Any]:
        """Execute multiple tasks in parallel."""
        parallel_tasks = step.task_args.get('tasks', [])
        if not parallel_tasks:
            return {"error": "No tasks defined for parallel execution"}
        
        # Create task group
        task_group = group(
            self.celery.signature(
                task_config['name'],
                kwargs={
                    **context,
                    **task_config.get('args', {}),
                    'step_id': f"{step.id}:{i}",
                    'step_name': f"{step.name}:{task_config['name']}"
                },
                queue='content_optimization',
                time_limit=timeout
            )
            for i, task_config in enumerate(parallel_tasks)
        )
        
        # Execute group
        group_result = task_group.apply_async()
        
        # Wait for all results
        results = await self._wait_for_group_result(group_result, timeout)
        
        return {
            "status": "completed",
            "results": results,
            "completed_at": datetime.utcnow().isoformat()
        }
    
    async def _execute_branching_step(
        self,
        step: WorkflowStep,
        context: Dict[str, Any],
        timeout: int
    ) -> Any:
        """Execute branching logic to determine next steps."""
        # Execute condition evaluation task
        condition_task = step.task_args.get('condition_task', step.task_name)
        
        result = await self._execute_single_task(
            WorkflowStep(
                id=f"{step.id}_condition",
                name=f"{step.name}_condition",
                type=StepType.CUSTOM,
                task_name=condition_task,
                task_args=step.task_args,
                timeout_seconds=timeout
            ),
            context,
            timeout
        )
        
        # Result should indicate which branch to take
        return {
            "branch": result.get('branch', 'default'),
            "condition_result": result,
            "evaluated_at": datetime.utcnow().isoformat()
        }
    
    async def _wait_for_result(
        self,
        task: AsyncResult,
        timeout: int
    ) -> Any:
        """Wait for Celery task result with async support."""
        loop = asyncio.get_event_loop()
        
        # Use thread pool for blocking operation
        future = loop.run_in_executor(
            self.executor,
            task.get,
            timeout
        )
        
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            # Try to revoke the task
            task.revoke(terminate=True)
            raise TimeoutError(f"Task {task.id} timed out after {timeout} seconds")
        except CeleryTimeoutError:
            raise TimeoutError(f"Task {task.id} timed out after {timeout} seconds")
    
    async def _wait_for_group_result(
        self,
        group_result: GroupResult,
        timeout: int
    ) -> List[Any]:
        """Wait for all tasks in a group to complete."""
        loop = asyncio.get_event_loop()
        
        # Use thread pool for blocking operation
        future = loop.run_in_executor(
            self.executor,
            group_result.get,
            timeout
        )
        
        try:
            results = await asyncio.wait_for(future, timeout=timeout)
            return results
        except asyncio.TimeoutError:
            # Try to revoke all tasks
            for task in group_result.children:
                task.revoke(terminate=True)
            raise TimeoutError(f"Task group timed out after {timeout} seconds")
    
    async def cancel_task(self, task_id: str, terminate: bool = False):
        """Cancel a running task."""
        task = self._active_tasks.get(task_id)
        if task:
            task.revoke(terminate=terminate)
            self._active_tasks.pop(task_id, None)
            logger.info(f"Cancelled task {task_id}")
    
    async def get_task_status(self, task_id: str) -> Optional[str]:
        """Get status of a task."""
        task = AsyncResult(task_id, app=self.celery)
        return task.state
    
    async def cleanup_completed_tasks(self):
        """Clean up completed tasks from tracking."""
        completed = []
        
        for key, task in self._active_tasks.items():
            if task.ready():
                completed.append(key)
        
        for key in completed:
            self._active_tasks.pop(key, None)
        
        logger.info(f"Cleaned up {len(completed)} completed tasks")
    
    def create_workflow_chain(
        self,
        steps: List[WorkflowStep],
        context: Dict[str, Any]
    ) -> chain:
        """Create a Celery chain from workflow steps."""
        signatures = []
        
        for step in steps:
            sig = self.celery.signature(
                step.task_name,
                kwargs={
                    **context,
                    **step.task_args,
                    'step_id': step.id,
                    'step_name': step.name
                },
                queue='content_optimization'
            )
            signatures.append(sig)
        
        return chain(*signatures)
    
    def create_workflow_chord(
        self,
        parallel_steps: List[WorkflowStep],
        callback_step: WorkflowStep,
        context: Dict[str, Any]
    ) -> chord:
        """Create a Celery chord for parallel execution with callback."""
        # Create parallel tasks
        header = group(
            self.celery.signature(
                step.task_name,
                kwargs={
                    **context,
                    **step.task_args,
                    'step_id': step.id,
                    'step_name': step.name
                },
                queue='content_optimization'
            )
            for step in parallel_steps
        )
        
        # Create callback
        callback = self.celery.signature(
            callback_step.task_name,
            kwargs={
                **context,
                **callback_step.task_args,
                'step_id': callback_step.id,
                'step_name': callback_step.name
            },
            queue='content_optimization'
        )
        
        return chord(header)(callback)