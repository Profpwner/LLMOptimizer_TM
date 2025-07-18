"""Integration implementations."""

from .base import BaseIntegration, IntegrationError, RateLimitError, AuthenticationError
from .registry import IntegrationRegistry
from .hubspot import HubSpotIntegration
from .salesforce import SalesforceIntegration
from .wordpress import WordPressIntegration
from .github import GitHubIntegration

__all__ = [
    "BaseIntegration",
    "IntegrationError",
    "RateLimitError",
    "AuthenticationError",
    "IntegrationRegistry",
    "HubSpotIntegration",
    "SalesforceIntegration",
    "WordPressIntegration",
    "GitHubIntegration",
]