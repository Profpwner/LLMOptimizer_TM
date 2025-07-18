"""
Celery application configuration for content optimization workflows.
"""

import os
from celery import Celery
from kombu import Exchange, Queue


# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create Celery app
app = Celery(
    'content_optimization',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        'src.workflows.tasks.content_tasks',
        'src.workflows.tasks.seo_tasks',
        'src.workflows.tasks.optimization_tasks',
        'src.workflows.tasks.ab_testing_tasks',
        'src.workflows.tasks.transformation_tasks'
    ]
)

# Celery configuration
app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Result backend settings
    result_expires=86400,  # 24 hours
    result_persistent=True,
    
    # Worker settings
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=100,
    worker_disable_rate_limits=False,
    
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_ignore_result=False,
    
    # Time limits
    task_soft_time_limit=3600,  # 1 hour soft limit
    task_time_limit=3900,       # 65 minutes hard limit
    
    # Retry settings
    task_autoretry_for=(Exception,),
    task_retry_kwargs={'max_retries': 3, 'countdown': 60},
    
    # Routing
    task_default_queue='default',
    task_queues=(
        Queue('default', Exchange('default'), routing_key='default'),
        Queue('content_optimization', Exchange('content'), routing_key='content.#'),
        Queue('ml_processing', Exchange('ml'), routing_key='ml.#'),
        Queue('notifications', Exchange('notifications'), routing_key='notifications.#'),
    ),
    task_routes={
        'src.workflows.tasks.content_tasks.*': {'queue': 'content_optimization'},
        'src.workflows.tasks.seo_tasks.*': {'queue': 'content_optimization'},
        'src.workflows.tasks.optimization_tasks.*': {'queue': 'ml_processing'},
        'src.workflows.tasks.ab_testing_tasks.*': {'queue': 'content_optimization'},
        'src.workflows.tasks.transformation_tasks.*': {'queue': 'content_optimization'},
        'src.workflows.tasks.notification_tasks.*': {'queue': 'notifications'},
    },
    
    # Beat schedule (for periodic tasks)
    beat_schedule={
        'cleanup-expired-workflows': {
            'task': 'src.workflows.tasks.maintenance.cleanup_expired_workflows',
            'schedule': 3600.0,  # Every hour
        },
        'process-pending-approvals': {
            'task': 'src.workflows.tasks.maintenance.process_pending_approvals',
            'schedule': 300.0,  # Every 5 minutes
        },
        'update-workflow-metrics': {
            'task': 'src.workflows.tasks.maintenance.update_workflow_metrics',
            'schedule': 600.0,  # Every 10 minutes
        },
    },
)

# Configure task error handling
app.conf.task_annotations = {
    '*': {
        'rate_limit': '100/m',  # 100 tasks per minute default
        'time_limit': 3600,     # 1 hour default
        'soft_time_limit': 3300 # 55 minutes soft limit
    },
    'src.workflows.tasks.optimization_tasks.*': {
        'rate_limit': '20/m',   # ML tasks are more resource intensive
        'time_limit': 7200,     # 2 hours for ML tasks
        'soft_time_limit': 6900 # 115 minutes soft limit
    }
}

if __name__ == '__main__':
    app.start()