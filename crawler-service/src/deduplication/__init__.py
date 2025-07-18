"""Content deduplication module for identifying duplicate and near-duplicate content."""

from .deduplicator import ContentDeduplicator
from .hashing import HashingStrategies
from .similarity import SimilarityCalculator

__all__ = [
    "ContentDeduplicator",
    "HashingStrategies",
    "SimilarityCalculator"
]