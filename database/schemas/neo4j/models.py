"""Neo4j models for knowledge graph relationships."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from py2neo import Node, Relationship, Graph
from py2neo.ogm import Model, Property, RelatedTo, RelatedFrom


class EntityType(str, Enum):
    """Types of entities in the knowledge graph."""
    TOPIC = "Topic"
    KEYWORD = "Keyword"
    CONCEPT = "Concept"
    INDUSTRY = "Industry"
    PRODUCT = "Product"
    FEATURE = "Feature"
    COMPETITOR = "Competitor"
    AUDIENCE = "Audience"
    INTENT = "Intent"


class RelationshipType(str, Enum):
    """Types of relationships between entities."""
    RELATES_TO = "RELATES_TO"
    CONTAINS = "CONTAINS"
    TARGETS = "TARGETS"
    COMPETES_WITH = "COMPETES_WITH"
    REQUIRES = "REQUIRES"
    INFLUENCES = "INFLUENCES"
    SIMILAR_TO = "SIMILAR_TO"
    OPPOSITE_OF = "OPPOSITE_OF"
    PARENT_OF = "PARENT_OF"
    USED_IN = "USED_IN"


@dataclass
class TenantContext:
    """Context for multi-tenant operations."""
    org_id: str
    label_prefix: str = ""
    
    def get_label(self, base_label: str) -> str:
        """Get tenant-specific label."""
        if self.label_prefix:
            return f"{self.label_prefix}{base_label}"
        return base_label
    
    def get_property_filter(self) -> Dict[str, str]:
        """Get property filter for tenant isolation."""
        return {"org_id": self.org_id}


class BaseNode(Model):
    """Base class for all Neo4j nodes."""
    
    __primarykey__ = "uid"
    
    # Unique identifier
    uid = Property()
    
    # Multi-tenancy
    org_id = Property()
    
    # Common properties
    name = Property()
    description = Property()
    created_at = Property(default=lambda: datetime.utcnow().isoformat())
    updated_at = Property(default=lambda: datetime.utcnow().isoformat())
    
    # Metadata
    metadata = Property(default={})
    tags = Property(default=[])
    
    # Scoring and importance
    importance_score = Property(default=0.0)
    confidence_score = Property(default=1.0)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary."""
        return {
            "uid": self.uid,
            "org_id": self.org_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
            "tags": self.tags,
            "importance_score": self.importance_score,
            "confidence_score": self.confidence_score,
        }


class ContentNode(BaseNode):
    """Node representing content in the knowledge graph."""
    
    __primarylabel__ = "Content"
    
    # Content identifiers
    content_id = Property()  # PostgreSQL/MongoDB reference
    title = Property()
    slug = Property()
    content_type = Property()
    
    # Content properties
    summary = Property()
    main_topic = Property()
    language = Property(default="en")
    
    # Performance metrics
    optimization_score = Property(default=0.0)
    engagement_score = Property(default=0.0)
    conversion_rate = Property(default=0.0)
    
    # Relationships
    topics = RelatedTo("TopicNode", "HAS_TOPIC")
    keywords = RelatedTo("KeywordNode", "CONTAINS_KEYWORD")
    concepts = RelatedTo("ConceptNode", "EXPRESSES_CONCEPT")
    audience = RelatedTo("AudienceNode", "TARGETS_AUDIENCE")
    similar_content = RelatedTo("ContentNode", "SIMILAR_TO")


class TopicNode(BaseNode):
    """Node representing a topic or subject area."""
    
    __primarylabel__ = "Topic"
    
    # Topic properties
    category = Property()
    subcategory = Property()
    
    # Hierarchy
    parent_topic_id = Property()
    level = Property(default=0)
    
    # Analytics
    search_volume = Property(default=0)
    trend_score = Property(default=0.0)
    competition_level = Property(default="medium")
    
    # Relationships
    parent = RelatedTo("TopicNode", "PARENT_OF")
    children = RelatedFrom("TopicNode", "PARENT_OF")
    related_topics = RelatedTo("TopicNode", "RELATES_TO")
    content_items = RelatedFrom("ContentNode", "HAS_TOPIC")
    keywords = RelatedTo("KeywordNode", "CONTAINS_KEYWORD")


class KeywordNode(BaseNode):
    """Node representing a keyword or key phrase."""
    
    __primarylabel__ = "Keyword"
    
    # Keyword properties
    keyword = Property()
    keyword_type = Property()  # primary, secondary, long-tail
    
    # SEO metrics
    search_volume = Property(default=0)
    difficulty_score = Property(default=0.0)
    cpc = Property(default=0.0)
    
    # Performance
    click_through_rate = Property(default=0.0)
    conversion_rate = Property(default=0.0)
    
    # Relationships
    topics = RelatedFrom("TopicNode", "CONTAINS_KEYWORD")
    content_items = RelatedFrom("ContentNode", "CONTAINS_KEYWORD")
    related_keywords = RelatedTo("KeywordNode", "RELATES_TO")
    concepts = RelatedTo("ConceptNode", "REPRESENTS_CONCEPT")


class ConceptNode(BaseNode):
    """Node representing an abstract concept or idea."""
    
    __primarylabel__ = "Concept"
    
    # Concept properties
    concept_type = Property()  # technical, business, marketing, etc.
    complexity_level = Property(default="medium")
    
    # Semantic properties
    definition = Property()
    synonyms = Property(default=[])
    antonyms = Property(default=[])
    
    # Relationships
    related_concepts = RelatedTo("ConceptNode", "RELATES_TO")
    opposite_concepts = RelatedTo("ConceptNode", "OPPOSITE_OF")
    content_items = RelatedFrom("ContentNode", "EXPRESSES_CONCEPT")
    keywords = RelatedFrom("KeywordNode", "REPRESENTS_CONCEPT")


class AudienceNode(BaseNode):
    """Node representing a target audience segment."""
    
    __primarylabel__ = "Audience"
    
    # Audience properties
    segment_name = Property()
    demographics = Property(default={})
    psychographics = Property(default={})
    
    # Behavior
    interests = Property(default=[])
    pain_points = Property(default=[])
    goals = Property(default=[])
    
    # Value metrics
    lifetime_value = Property(default=0.0)
    engagement_level = Property(default="medium")
    
    # Relationships
    content_preferences = RelatedTo("ContentNode", "PREFERS_CONTENT")
    topics_of_interest = RelatedTo("TopicNode", "INTERESTED_IN")
    related_audiences = RelatedTo("AudienceNode", "SIMILAR_TO")


class CompetitorNode(BaseNode):
    """Node representing a competitor or competitive content."""
    
    __primarylabel__ = "Competitor"
    
    # Competitor properties
    competitor_name = Property()
    domain = Property()
    competitor_type = Property()  # direct, indirect, substitute
    
    # Competitive metrics
    market_share = Property(default=0.0)
    strength_score = Property(default=0.0)
    
    # Content strategy
    content_frequency = Property(default=0)
    avg_content_length = Property(default=0)
    main_topics = Property(default=[])
    
    # Relationships
    competes_for_keywords = RelatedTo("KeywordNode", "COMPETES_FOR")
    competes_in_topics = RelatedTo("TopicNode", "COMPETES_IN")
    similar_content = RelatedTo("ContentNode", "HAS_SIMILAR_CONTENT")


class IntentNode(BaseNode):
    """Node representing user search or action intent."""
    
    __primarylabel__ = "Intent"
    
    # Intent properties
    intent_type = Property()  # informational, navigational, transactional, commercial
    intent_stage = Property()  # awareness, consideration, decision, retention
    
    # Behavior signals
    typical_queries = Property(default=[])
    action_keywords = Property(default=[])
    
    # Conversion metrics
    conversion_probability = Property(default=0.0)
    average_value = Property(default=0.0)
    
    # Relationships
    keywords = RelatedTo("KeywordNode", "EXPRESSED_BY")
    content_matches = RelatedTo("ContentNode", "SATISFIED_BY")
    audience_segments = RelatedFrom("AudienceNode", "HAS_INTENT")


class IndustryNode(BaseNode):
    """Node representing an industry or market sector."""
    
    __primarylabel__ = "Industry"
    
    # Industry properties
    industry_code = Property()  # NAICS, SIC, etc.
    sector = Property()
    subsector = Property()
    
    # Market data
    market_size = Property(default=0.0)
    growth_rate = Property(default=0.0)
    
    # Trends
    trending_topics = Property(default=[])
    emerging_keywords = Property(default=[])
    
    # Relationships
    topics = RelatedTo("TopicNode", "CONTAINS_TOPIC")
    competitors = RelatedTo("CompetitorNode", "HAS_COMPETITOR")
    audiences = RelatedTo("AudienceNode", "SERVES_AUDIENCE")


# Relationship classes with properties
class ContentRelationship:
    """Factory for creating content relationships with properties."""
    
    @staticmethod
    def similar_to(content1: ContentNode, content2: ContentNode, 
                   similarity_score: float, similarity_type: str) -> Relationship:
        """Create SIMILAR_TO relationship between content nodes."""
        return Relationship(
            content1.__node__,
            "SIMILAR_TO",
            content2.__node__,
            similarity_score=similarity_score,
            similarity_type=similarity_type,
            created_at=datetime.utcnow().isoformat()
        )
    
    @staticmethod
    def has_topic(content: ContentNode, topic: TopicNode,
                  relevance_score: float, is_primary: bool = False) -> Relationship:
        """Create HAS_TOPIC relationship."""
        return Relationship(
            content.__node__,
            "HAS_TOPIC",
            topic.__node__,
            relevance_score=relevance_score,
            is_primary=is_primary,
            created_at=datetime.utcnow().isoformat()
        )
    
    @staticmethod
    def targets_audience(content: ContentNode, audience: AudienceNode,
                        targeting_score: float, targeting_strategy: str) -> Relationship:
        """Create TARGETS_AUDIENCE relationship."""
        return Relationship(
            content.__node__,
            "TARGETS_AUDIENCE",
            audience.__node__,
            targeting_score=targeting_score,
            targeting_strategy=targeting_strategy,
            created_at=datetime.utcnow().isoformat()
        )


class KnowledgeGraphQueries:
    """Common queries for the knowledge graph."""
    
    @staticmethod
    def find_related_content(graph: Graph, content_id: str, org_id: str, 
                           limit: int = 10) -> List[Dict[str, Any]]:
        """Find content related to a given content item."""
        query = """
        MATCH (c:Content {content_id: $content_id, org_id: $org_id})
        MATCH (c)-[:HAS_TOPIC|:CONTAINS_KEYWORD|:EXPRESSES_CONCEPT]->()<-[:HAS_TOPIC|:CONTAINS_KEYWORD|:EXPRESSES_CONCEPT]-(related:Content)
        WHERE related.content_id <> c.content_id
        WITH related, COUNT(*) as common_connections
        ORDER BY common_connections DESC
        LIMIT $limit
        RETURN related, common_connections
        """
        return graph.run(query, content_id=content_id, org_id=org_id, limit=limit).data()
    
    @staticmethod
    def get_content_knowledge_map(graph: Graph, content_id: str, org_id: str) -> Dict[str, Any]:
        """Get the full knowledge map for a content item."""
        query = """
        MATCH (c:Content {content_id: $content_id, org_id: $org_id})
        OPTIONAL MATCH (c)-[:HAS_TOPIC]->(t:Topic)
        OPTIONAL MATCH (c)-[:CONTAINS_KEYWORD]->(k:Keyword)
        OPTIONAL MATCH (c)-[:EXPRESSES_CONCEPT]->(con:Concept)
        OPTIONAL MATCH (c)-[:TARGETS_AUDIENCE]->(a:Audience)
        RETURN c,
               COLLECT(DISTINCT t) as topics,
               COLLECT(DISTINCT k) as keywords,
               COLLECT(DISTINCT con) as concepts,
               COLLECT(DISTINCT a) as audiences
        """
        return graph.run(query, content_id=content_id, org_id=org_id).data()
    
    @staticmethod
    def find_content_gaps(graph: Graph, org_id: str, competitor_id: str) -> List[Dict[str, Any]]:
        """Find content gaps by comparing with competitors."""
        query = """
        MATCH (comp:Competitor {uid: $competitor_id, org_id: $org_id})
        MATCH (comp)-[:COMPETES_FOR]->(k:Keyword)
        WHERE NOT EXISTS {
            MATCH (c:Content {org_id: $org_id})-[:CONTAINS_KEYWORD]->(k)
        }
        RETURN k as keyword, k.search_volume as search_volume, k.difficulty_score as difficulty
        ORDER BY k.search_volume DESC
        """
        return graph.run(query, org_id=org_id, competitor_id=competitor_id).data()
    
    @staticmethod
    def get_topic_hierarchy(graph: Graph, org_id: str, root_topic_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get topic hierarchy tree."""
        if root_topic_id:
            query = """
            MATCH path = (root:Topic {uid: $root_topic_id, org_id: $org_id})-[:PARENT_OF*]->(child:Topic)
            RETURN root, COLLECT(child) as children, LENGTH(path) as depth
            ORDER BY depth
            """
            return graph.run(query, root_topic_id=root_topic_id, org_id=org_id).data()
        else:
            query = """
            MATCH (t:Topic {org_id: $org_id})
            WHERE NOT EXISTS ((t)<-[:PARENT_OF]-(:Topic))
            OPTIONAL MATCH (t)-[:PARENT_OF*]->(child:Topic)
            RETURN t as root, COLLECT(child) as children
            """
            return graph.run(query, org_id=org_id).data()