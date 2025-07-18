"""Integration registry for managing integration types."""

from typing import Dict, Type, Optional
from app.integrations.base import BaseIntegration
from app.models import IntegrationType


class IntegrationRegistry:
    """Registry for integration implementations."""
    
    _integrations: Dict[IntegrationType, Type[BaseIntegration]] = {}
    
    @classmethod
    def register(cls, integration_type: IntegrationType):
        """Decorator to register an integration class."""
        def decorator(integration_class: Type[BaseIntegration]):
            cls._integrations[integration_type] = integration_class
            return integration_class
        return decorator
    
    @classmethod
    def get(cls, integration_type: IntegrationType) -> Optional[Type[BaseIntegration]]:
        """Get integration class by type."""
        return cls._integrations.get(integration_type)
    
    @classmethod
    def list_types(cls) -> list[IntegrationType]:
        """List all registered integration types."""
        return list(cls._integrations.keys())