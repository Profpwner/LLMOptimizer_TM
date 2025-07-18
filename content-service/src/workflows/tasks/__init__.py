"""
Celery tasks for content optimization workflows.
"""

from .content_tasks import *
from .seo_tasks import *
from .optimization_tasks import *
from .ab_testing_tasks import *
from .transformation_tasks import *

__all__ = [
    # Content tasks
    'analyze_content',
    'extract_keywords',
    'check_grammar',
    'analyze_readability',
    
    # SEO tasks
    'generate_seo_suggestions',
    'apply_seo_optimizations',
    'generate_meta_description',
    'optimize_title',
    
    # Optimization tasks
    'generate_content_suggestions',
    'optimize_content_with_ai',
    'improve_readability',
    'enhance_engagement',
    
    # A/B testing tasks
    'create_test_variants',
    'setup_traffic_split',
    'monitor_test_performance',
    'calculate_test_winner',
    
    # Transformation tasks
    'convert_content_format',
    'optimize_images',
    'transcode_video',
    'generate_schema_markup'
]