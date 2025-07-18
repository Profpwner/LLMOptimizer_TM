"""
Workflow definition models and schemas.
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
import uuid


class WorkflowStatus(str, Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRY = "retry"


class StepType(str, Enum):
    """Types of workflow steps."""
    ANALYSIS = "analysis"
    TRANSFORMATION = "transformation"
    OPTIMIZATION = "optimization"
    VALIDATION = "validation"
    APPROVAL = "approval"
    NOTIFICATION = "notification"
    BRANCHING = "branching"
    PARALLEL = "parallel"
    CUSTOM = "custom"


class RetryPolicy(BaseModel):
    """Retry configuration for workflow steps."""
    max_attempts: int = Field(default=3, ge=1, le=10)
    delay_seconds: int = Field(default=60, ge=1)
    backoff_multiplier: float = Field(default=2.0, ge=1.0)
    max_delay_seconds: int = Field(default=3600, ge=60)


class WorkflowStep(BaseModel):
    """Individual workflow step definition."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., min_length=1, max_length=100)
    type: StepType
    description: Optional[str] = None
    
    # Execution configuration
    task_name: str = Field(..., description="Celery task name")
    task_args: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: Optional[int] = Field(default=3600, ge=1)
    
    # Dependencies and flow control
    depends_on: List[str] = Field(default_factory=list, description="Step IDs this step depends on")
    condition: Optional[str] = Field(None, description="Jinja2 expression for conditional execution")
    on_success: Optional[List[str]] = Field(default_factory=list, description="Steps to execute on success")
    on_failure: Optional[List[str]] = Field(default_factory=list, description="Steps to execute on failure")
    
    # Retry and error handling
    retry_policy: Optional[RetryPolicy] = Field(default_factory=RetryPolicy)
    allow_failure: bool = Field(default=False, description="Whether workflow can continue if this step fails")
    
    # Resource requirements
    requires_approval: bool = Field(default=False)
    approvers: Optional[List[str]] = Field(default_factory=list, description="User IDs who can approve")
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Analyze Content",
                "type": "analysis",
                "task_name": "workflows.tasks.analyze_content",
                "task_args": {"depth": "detailed"},
                "depends_on": [],
                "retry_policy": {"max_attempts": 3}
            }
        }


class WorkflowTrigger(BaseModel):
    """Workflow trigger configuration."""
    type: str = Field(..., description="Trigger type: manual, schedule, event, webhook")
    config: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = Field(default=True)
    
    @validator('type')
    def validate_trigger_type(cls, v):
        valid_types = ['manual', 'schedule', 'event', 'webhook', 'api']
        if v not in valid_types:
            raise ValueError(f"Invalid trigger type. Must be one of: {valid_types}")
        return v


class WorkflowDefinition(BaseModel):
    """Complete workflow definition."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    version: str = Field(default="1.0.0")
    
    # Workflow configuration
    category: str = Field(..., description="Workflow category: content, seo, ab_test, etc.")
    tags: List[str] = Field(default_factory=list)
    
    # Steps and execution
    steps: List[WorkflowStep] = Field(..., min_items=1)
    entry_point: Optional[str] = Field(None, description="ID of the first step")
    
    # Triggers and scheduling
    triggers: List[WorkflowTrigger] = Field(default_factory=list)
    
    # Global configuration
    timeout_seconds: Optional[int] = Field(default=7200, ge=60)
    max_parallel_steps: int = Field(default=5, ge=1, le=20)
    
    # Metadata
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
    
    @validator('entry_point', always=True)
    def validate_entry_point(cls, v, values):
        if 'steps' in values and values['steps']:
            if v is None:
                # Use first step as entry point if not specified
                return values['steps'][0].id
            # Validate that entry point exists
            step_ids = [step.id for step in values['steps']]
            if v not in step_ids:
                raise ValueError(f"Entry point {v} not found in workflow steps")
        return v
    
    @validator('steps')
    def validate_step_dependencies(cls, v):
        step_ids = [step.id for step in v]
        for step in v:
            for dep_id in step.depends_on:
                if dep_id not in step_ids:
                    raise ValueError(f"Step {step.id} depends on non-existent step {dep_id}")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "name": "SEO Content Optimization",
                "description": "Optimize content for search engines",
                "category": "seo",
                "steps": [
                    {
                        "name": "Analyze Content",
                        "type": "analysis",
                        "task_name": "workflows.tasks.analyze_content"
                    },
                    {
                        "name": "Generate Suggestions",
                        "type": "optimization",
                        "task_name": "workflows.tasks.generate_seo_suggestions",
                        "depends_on": ["step-1-id"]
                    }
                ]
            }
        }


class WorkflowInstance(BaseModel):
    """Running instance of a workflow."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str
    workflow_version: str
    
    # Execution state
    status: WorkflowStatus = Field(default=WorkflowStatus.PENDING)
    current_step_id: Optional[str] = None
    completed_steps: List[str] = Field(default_factory=list)
    failed_steps: List[str] = Field(default_factory=list)
    
    # Execution context
    context: Dict[str, Any] = Field(default_factory=dict, description="Workflow execution context")
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    
    # Step results
    step_results: Dict[str, Any] = Field(default_factory=dict, description="Results from each step")
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    
    # Error tracking
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    retry_count: int = Field(default=0)
    
    # Metadata
    triggered_by: Optional[str] = None
    parent_instance_id: Optional[str] = None
    
    def add_step_result(self, step_id: str, result: Any):
        """Add result from a completed step."""
        self.step_results[step_id] = result
        if step_id not in self.completed_steps:
            self.completed_steps.append(step_id)
    
    def mark_step_failed(self, step_id: str, error: str):
        """Mark a step as failed."""
        self.failed_steps.append(step_id)
        self.step_results[step_id] = {"error": error, "status": "failed"}
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }