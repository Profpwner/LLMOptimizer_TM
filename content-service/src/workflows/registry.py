"""
Workflow registry for managing workflow definitions and templates.
"""

import logging
from typing import Dict, List, Optional, Type
from datetime import datetime
import json
import os

from motor.motor_asyncio import AsyncIOMotorDatabase

from .definitions import WorkflowDefinition, WorkflowStep, StepType


logger = logging.getLogger(__name__)


class WorkflowRegistry:
    """
    Central registry for workflow definitions and templates.
    Supports versioning, categories, and dynamic loading.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self._definitions: Dict[str, WorkflowDefinition] = {}
        self._templates: Dict[str, dict] = {}
        self._loaded = False
    
    async def initialize(self):
        """Initialize registry and load built-in workflows."""
        if self._loaded:
            return
        
        # Create indexes
        await self.db.workflow_definitions.create_index([("name", 1)])
        await self.db.workflow_definitions.create_index([("category", 1)])
        await self.db.workflow_definitions.create_index([("is_active", 1)])
        await self.db.workflow_definitions.create_index([("created_at", -1)])
        
        # Load built-in workflows
        await self._load_builtin_workflows()
        
        # Load from database
        await self._load_from_database()
        
        self._loaded = True
        logger.info(f"Workflow registry initialized with {len(self._definitions)} workflows")
    
    async def register(
        self,
        workflow_def: WorkflowDefinition,
        overwrite: bool = False
    ) -> bool:
        """Register a workflow definition."""
        existing = await self.get(workflow_def.name)
        
        if existing and not overwrite:
            logger.warning(f"Workflow {workflow_def.name} already exists")
            return False
        
        # Save to database
        await self.db.workflow_definitions.replace_one(
            {"name": workflow_def.name},
            workflow_def.dict(exclude_none=True),
            upsert=True
        )
        
        # Update cache
        self._definitions[workflow_def.name] = workflow_def
        
        logger.info(f"Registered workflow: {workflow_def.name} (v{workflow_def.version})")
        return True
    
    async def get(
        self,
        name: str,
        version: Optional[str] = None
    ) -> Optional[WorkflowDefinition]:
        """Get workflow definition by name and optional version."""
        # Check cache first
        if not version and name in self._definitions:
            return self._definitions[name]
        
        # Query database
        query = {"name": name, "is_active": True}
        if version:
            query["version"] = version
        
        doc = await self.db.workflow_definitions.find_one(
            query,
            sort=[("created_at", -1)]  # Latest first if no version specified
        )
        
        if doc:
            workflow_def = WorkflowDefinition(**doc)
            # Update cache
            if not version:
                self._definitions[name] = workflow_def
            return workflow_def
        
        return None
    
    async def get_by_id(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """Get workflow definition by ID."""
        doc = await self.db.workflow_definitions.find_one({"id": workflow_id})
        return WorkflowDefinition(**doc) if doc else None
    
    async def list_workflows(
        self,
        category: Optional[str] = None,
        active_only: bool = True
    ) -> List[WorkflowDefinition]:
        """List available workflows."""
        query = {}
        if category:
            query["category"] = category
        if active_only:
            query["is_active"] = True
        
        cursor = self.db.workflow_definitions.find(query).sort("name", 1)
        workflows = []
        
        async for doc in cursor:
            workflows.append(WorkflowDefinition(**doc))
        
        return workflows
    
    async def get_categories(self) -> List[str]:
        """Get list of workflow categories."""
        categories = await self.db.workflow_definitions.distinct("category")
        return sorted(categories)
    
    async def update_workflow(
        self,
        name: str,
        updates: dict
    ) -> bool:
        """Update workflow definition."""
        # Don't allow updating critical fields
        protected_fields = ["id", "name", "created_at", "created_by"]
        for field in protected_fields:
            updates.pop(field, None)
        
        updates["updated_at"] = datetime.utcnow()
        
        result = await self.db.workflow_definitions.update_one(
            {"name": name},
            {"$set": updates}
        )
        
        if result.modified_count > 0:
            # Invalidate cache
            self._definitions.pop(name, None)
            logger.info(f"Updated workflow: {name}")
            return True
        
        return False
    
    async def deactivate_workflow(self, name: str) -> bool:
        """Deactivate a workflow (soft delete)."""
        return await self.update_workflow(name, {"is_active": False})
    
    async def create_from_template(
        self,
        template_name: str,
        workflow_name: str,
        customizations: dict
    ) -> Optional[WorkflowDefinition]:
        """Create a new workflow from a template."""
        template = self._templates.get(template_name)
        if not template:
            logger.error(f"Template {template_name} not found")
            return None
        
        # Apply customizations to template
        workflow_data = {**template, **customizations}
        workflow_data["name"] = workflow_name
        workflow_data["created_at"] = datetime.utcnow()
        workflow_data["updated_at"] = datetime.utcnow()
        
        # Create workflow definition
        workflow_def = WorkflowDefinition(**workflow_data)
        
        # Register it
        success = await self.register(workflow_def)
        if success:
            return workflow_def
        
        return None
    
    async def _load_builtin_workflows(self):
        """Load built-in workflow definitions."""
        # SEO Content Optimization Workflow
        seo_workflow = WorkflowDefinition(
            name="seo_content_optimization",
            description="Optimize content for search engines",
            category="seo",
            tags=["seo", "optimization", "content"],
            steps=[
                WorkflowStep(
                    name="Analyze Content",
                    type=StepType.ANALYSIS,
                    task_name="content_optimization.tasks.analyze_content",
                    task_args={"analysis_type": "seo"}
                ),
                WorkflowStep(
                    name="Extract Keywords",
                    type=StepType.ANALYSIS,
                    task_name="content_optimization.tasks.extract_keywords",
                    depends_on=["analyze_content_id"]
                ),
                WorkflowStep(
                    name="Generate SEO Suggestions",
                    type=StepType.OPTIMIZATION,
                    task_name="content_optimization.tasks.generate_seo_suggestions",
                    depends_on=["extract_keywords_id"]
                ),
                WorkflowStep(
                    name="Apply Optimizations",
                    type=StepType.TRANSFORMATION,
                    task_name="content_optimization.tasks.apply_seo_optimizations",
                    depends_on=["generate_seo_suggestions_id"],
                    requires_approval=True
                )
            ]
        )
        
        # A/B Testing Workflow
        ab_test_workflow = WorkflowDefinition(
            name="ab_testing_workflow",
            description="Create and manage A/B tests for content",
            category="ab_test",
            tags=["testing", "optimization", "experimentation"],
            steps=[
                WorkflowStep(
                    name="Create Test Variants",
                    type=StepType.TRANSFORMATION,
                    task_name="content_optimization.tasks.create_test_variants",
                    task_args={"num_variants": 2}
                ),
                WorkflowStep(
                    name="Setup Traffic Split",
                    type=StepType.CUSTOM,
                    task_name="content_optimization.tasks.setup_traffic_split",
                    depends_on=["create_test_variants_id"]
                ),
                WorkflowStep(
                    name="Monitor Performance",
                    type=StepType.ANALYSIS,
                    task_name="content_optimization.tasks.monitor_test_performance",
                    depends_on=["setup_traffic_split_id"],
                    task_args={"check_interval": 3600}  # 1 hour
                ),
                WorkflowStep(
                    name="Calculate Winner",
                    type=StepType.ANALYSIS,
                    task_name="content_optimization.tasks.calculate_test_winner",
                    depends_on=["monitor_performance_id"]
                )
            ]
        )
        
        # Content Quality Workflow
        quality_workflow = WorkflowDefinition(
            name="content_quality_check",
            description="Comprehensive content quality analysis",
            category="quality",
            tags=["quality", "analysis", "validation"],
            steps=[
                WorkflowStep(
                    name="Grammar Check",
                    type=StepType.VALIDATION,
                    task_name="content_optimization.tasks.check_grammar"
                ),
                WorkflowStep(
                    name="Readability Analysis",
                    type=StepType.ANALYSIS,
                    task_name="content_optimization.tasks.analyze_readability"
                ),
                WorkflowStep(
                    name="Fact Checking",
                    type=StepType.VALIDATION,
                    task_name="content_optimization.tasks.fact_check"
                ),
                WorkflowStep(
                    name="Plagiarism Check",
                    type=StepType.VALIDATION,
                    task_name="content_optimization.tasks.check_plagiarism"
                ),
                WorkflowStep(
                    name="Generate Quality Report",
                    type=StepType.ANALYSIS,
                    task_name="content_optimization.tasks.generate_quality_report",
                    depends_on=[
                        "grammar_check_id",
                        "readability_analysis_id",
                        "fact_checking_id",
                        "plagiarism_check_id"
                    ]
                )
            ]
        )
        
        # Register built-in workflows
        for workflow in [seo_workflow, ab_test_workflow, quality_workflow]:
            await self.register(workflow, overwrite=True)
        
        # Store as templates
        self._templates["seo_optimization"] = seo_workflow.dict()
        self._templates["ab_testing"] = ab_test_workflow.dict()
        self._templates["quality_check"] = quality_workflow.dict()
    
    async def _load_from_database(self):
        """Load active workflows from database into cache."""
        cursor = self.db.workflow_definitions.find({"is_active": True})
        
        async for doc in cursor:
            workflow_def = WorkflowDefinition(**doc)
            self._definitions[workflow_def.name] = workflow_def
    
    def get_workflow_templates(self) -> Dict[str, dict]:
        """Get available workflow templates."""
        return self._templates.copy()
    
    async def export_workflow(
        self,
        name: str,
        format: str = "json"
    ) -> Optional[str]:
        """Export workflow definition."""
        workflow = await self.get(name)
        if not workflow:
            return None
        
        if format == "json":
            return json.dumps(workflow.dict(), indent=2, default=str)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    async def import_workflow(
        self,
        data: str,
        format: str = "json",
        overwrite: bool = False
    ) -> Optional[WorkflowDefinition]:
        """Import workflow definition."""
        if format == "json":
            workflow_data = json.loads(data)
            workflow_def = WorkflowDefinition(**workflow_data)
            
            success = await self.register(workflow_def, overwrite=overwrite)
            if success:
                return workflow_def
        else:
            raise ValueError(f"Unsupported import format: {format}")
        
        return None