"""Neo4j client with async support and multi-tenancy."""

import logging
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any, Type, TypeVar, Union, Tuple

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession, AsyncTransaction
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError
from py2neo import Graph, Node, Relationship
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import Neo4jConfig, db_config
from database.schemas.neo4j.models import (
    TenantContext, BaseNode, ContentNode, TopicNode,
    KeywordNode, ConceptNode, AudienceNode, CompetitorNode,
    IntentNode, IndustryNode, KnowledgeGraphQueries
)

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseNode)


class Neo4jClient:
    """Async Neo4j client with multi-tenancy support."""
    
    def __init__(self, config: Optional[Neo4jConfig] = None):
        """Initialize Neo4j client."""
        self.config = config or db_config.neo4j
        self._driver: Optional[AsyncDriver] = None
        self._sync_graph: Optional[Graph] = None
        
    async def initialize(self):
        """Initialize Neo4j connection."""
        # Create async driver
        self._driver = AsyncGraphDatabase.driver(
            self.config.bolt_url,
            auth=(self.config.username, self.config.password),
            max_connection_lifetime=self.config.max_connection_lifetime,
            max_connection_pool_size=self.config.max_connection_pool_size,
            connection_acquisition_timeout=30,
        )
        
        # Verify connectivity
        await self._driver.verify_connectivity()
        
        # Create sync graph for py2neo operations
        self._sync_graph = Graph(
            self.config.http_url,
            auth=(self.config.username, self.config.password)
        )
        
        # Create constraints and indexes
        await self._create_constraints_and_indexes()
        
        logger.info("Neo4j client initialized successfully")
    
    async def close(self):
        """Close Neo4j connection."""
        if self._driver:
            await self._driver.close()
        logger.info("Neo4j client closed")
    
    async def _create_constraints_and_indexes(self):
        """Create necessary constraints and indexes."""
        constraints = [
            # Unique constraints
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Content) REQUIRE (n.uid, n.org_id) IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Topic) REQUIRE (n.uid, n.org_id) IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Keyword) REQUIRE (n.uid, n.org_id) IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Concept) REQUIRE (n.uid, n.org_id) IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Audience) REQUIRE (n.uid, n.org_id) IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Competitor) REQUIRE (n.uid, n.org_id) IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Intent) REQUIRE (n.uid, n.org_id) IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Industry) REQUIRE (n.uid, n.org_id) IS UNIQUE",
        ]
        
        indexes = [
            # Performance indexes
            "CREATE INDEX IF NOT EXISTS FOR (n:Content) ON (n.org_id, n.content_id)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Content) ON (n.org_id, n.slug)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Topic) ON (n.org_id, n.category)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Keyword) ON (n.org_id, n.keyword)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Concept) ON (n.org_id, n.concept_type)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Audience) ON (n.org_id, n.segment_name)",
            
            # Full-text search indexes
            "CREATE FULLTEXT INDEX content_search IF NOT EXISTS FOR (n:Content) ON EACH [n.title, n.summary, n.main_topic]",
            "CREATE FULLTEXT INDEX topic_search IF NOT EXISTS FOR (n:Topic) ON EACH [n.name, n.description]",
            "CREATE FULLTEXT INDEX keyword_search IF NOT EXISTS FOR (n:Keyword) ON EACH [n.keyword]",
        ]
        
        async with self._driver.session() as session:
            # Create constraints
            for constraint in constraints:
                try:
                    await session.run(constraint)
                except Exception as e:
                    logger.warning(f"Constraint creation warning: {e}")
            
            # Create indexes
            for index in indexes:
                try:
                    await session.run(index)
                except Exception as e:
                    logger.warning(f"Index creation warning: {e}")
    
    def get_tenant_context(self, tenant_id: str) -> TenantContext:
        """Get tenant context for multi-tenant operations."""
        return TenantContext(
            org_id=tenant_id,
            label_prefix=f"Tenant_{tenant_id}_" if self.config.tenant_label_prefix else ""
        )
    
    @asynccontextmanager
    async def get_session(self) -> AsyncSession:
        """Get a Neo4j session."""
        async with self._driver.session() as session:
            yield session
    
    @asynccontextmanager
    async def transaction(self):
        """Create a transaction context."""
        async with self.get_session() as session:
            async with session.begin_transaction() as tx:
                yield tx
    
    # Node Operations
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def create_node(self, node_data: Dict[str, Any], labels: List[str],
                         tenant_id: str) -> Dict[str, Any]:
        """Create a new node."""
        # Add tenant context
        node_data["org_id"] = tenant_id
        
        # Build query
        label_str = ":".join(labels)
        props_str = ", ".join([f"{k}: ${k}" for k in node_data.keys()])
        
        query = f"""
        CREATE (n:{label_str} {{{props_str}}})
        RETURN n
        """
        
        async with self.get_session() as session:
            result = await session.run(query, **node_data)
            record = await result.single()
            return dict(record["n"])
    
    async def get_node(self, uid: str, label: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get a node by UID and label."""
        query = f"""
        MATCH (n:{label} {{uid: $uid, org_id: $org_id}})
        RETURN n
        """
        
        async with self.get_session() as session:
            result = await session.run(query, uid=uid, org_id=tenant_id)
            record = await result.single()
            return dict(record["n"]) if record else None
    
    async def update_node(self, uid: str, label: str, updates: Dict[str, Any],
                         tenant_id: str) -> Optional[Dict[str, Any]]:
        """Update a node."""
        # Build SET clause
        set_items = [f"n.{k} = ${k}" for k in updates.keys() if k not in ["uid", "org_id"]]
        set_clause = ", ".join(set_items)
        
        query = f"""
        MATCH (n:{label} {{uid: $uid, org_id: $org_id}})
        SET {set_clause}, n.updated_at = datetime()
        RETURN n
        """
        
        params = {"uid": uid, "org_id": tenant_id, **updates}
        
        async with self.get_session() as session:
            result = await session.run(query, **params)
            record = await result.single()
            return dict(record["n"]) if record else None
    
    async def delete_node(self, uid: str, label: str, tenant_id: str,
                         detach: bool = True) -> bool:
        """Delete a node."""
        delete_clause = "DETACH DELETE" if detach else "DELETE"
        
        query = f"""
        MATCH (n:{label} {{uid: $uid, org_id: $org_id}})
        {delete_clause} n
        RETURN COUNT(n) as deleted
        """
        
        async with self.get_session() as session:
            result = await session.run(query, uid=uid, org_id=tenant_id)
            record = await result.single()
            return record["deleted"] > 0
    
    # Relationship Operations
    async def create_relationship(self, from_uid: str, from_label: str,
                                to_uid: str, to_label: str,
                                rel_type: str, rel_props: Optional[Dict[str, Any]] = None,
                                tenant_id: str = None) -> bool:
        """Create a relationship between nodes."""
        props_str = ""
        if rel_props:
            props_items = [f"{k}: ${k}" for k in rel_props.keys()]
            props_str = f" {{{', '.join(props_items)}}}"
        
        query = f"""
        MATCH (a:{from_label} {{uid: $from_uid, org_id: $org_id}})
        MATCH (b:{to_label} {{uid: $to_uid, org_id: $org_id}})
        CREATE (a)-[r:{rel_type}{props_str}]->(b)
        RETURN r
        """
        
        params = {
            "from_uid": from_uid,
            "to_uid": to_uid,
            "org_id": tenant_id,
            **(rel_props or {})
        }
        
        async with self.get_session() as session:
            result = await session.run(query, **params)
            record = await result.single()
            return record is not None
    
    async def delete_relationship(self, from_uid: str, from_label: str,
                                to_uid: str, to_label: str,
                                rel_type: str, tenant_id: str) -> bool:
        """Delete a relationship between nodes."""
        query = f"""
        MATCH (a:{from_label} {{uid: $from_uid, org_id: $org_id}})
              -[r:{rel_type}]->
              (b:{to_label} {{uid: $to_uid, org_id: $org_id}})
        DELETE r
        RETURN COUNT(r) as deleted
        """
        
        async with self.get_session() as session:
            result = await session.run(
                query,
                from_uid=from_uid,
                to_uid=to_uid,
                org_id=tenant_id
            )
            record = await result.single()
            return record["deleted"] > 0
    
    # Query Operations
    async def find_nodes(self, label: str, filters: Dict[str, Any],
                        tenant_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Find nodes matching filters."""
        # Add tenant filter
        filters["org_id"] = tenant_id
        
        # Build WHERE clause
        where_items = [f"n.{k} = ${k}" for k in filters.keys()]
        where_clause = " AND ".join(where_items)
        
        query = f"""
        MATCH (n:{label})
        WHERE {where_clause}
        RETURN n
        ORDER BY n.created_at DESC
        LIMIT $limit
        """
        
        async with self.get_session() as session:
            result = await session.run(query, limit=limit, **filters)
            records = [dict(record["n"]) async for record in result]
            return records
    
    async def find_connected_nodes(self, uid: str, label: str,
                                 rel_type: Optional[str] = None,
                                 direction: str = "both",
                                 target_label: Optional[str] = None,
                                 tenant_id: str = None,
                                 limit: int = 50) -> List[Dict[str, Any]]:
        """Find nodes connected to a given node."""
        # Build relationship pattern
        if direction == "out":
            rel_pattern = f"-[r{':' + rel_type if rel_type else ''}]->"
        elif direction == "in":
            rel_pattern = f"<-[r{':' + rel_type if rel_type else ''}]-"
        else:
            rel_pattern = f"-[r{':' + rel_type if rel_type else ''}]-"
        
        target_pattern = f":{target_label}" if target_label else ""
        
        query = f"""
        MATCH (n:{label} {{uid: $uid, org_id: $org_id}})
              {rel_pattern}
              (connected{target_pattern} {{org_id: $org_id}})
        RETURN connected, r
        ORDER BY connected.importance_score DESC
        LIMIT $limit
        """
        
        async with self.get_session() as session:
            result = await session.run(
                query,
                uid=uid,
                org_id=tenant_id,
                limit=limit
            )
            
            records = []
            async for record in result:
                node_data = dict(record["connected"])
                node_data["_relationship"] = dict(record["r"]) if record["r"] else None
                records.append(node_data)
            
            return records
    
    # Full-text Search
    async def search_nodes(self, search_text: str, index_name: str,
                         tenant_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Perform full-text search on nodes."""
        query = f"""
        CALL db.index.fulltext.queryNodes($index_name, $search_text)
        YIELD node, score
        WHERE node.org_id = $org_id
        RETURN node, score
        ORDER BY score DESC
        LIMIT $limit
        """
        
        async with self.get_session() as session:
            result = await session.run(
                query,
                index_name=index_name,
                search_text=search_text,
                org_id=tenant_id,
                limit=limit
            )
            
            records = []
            async for record in result:
                node_data = dict(record["node"])
                node_data["_search_score"] = record["score"]
                records.append(node_data)
            
            return records
    
    # Graph Algorithms
    async def find_shortest_path(self, from_uid: str, to_uid: str,
                               max_length: int = 5, tenant_id: str = None) -> Optional[List[Dict[str, Any]]]:
        """Find shortest path between two nodes."""
        query = """
        MATCH (start {uid: $from_uid, org_id: $org_id}),
              (end {uid: $to_uid, org_id: $org_id})
        MATCH path = shortestPath((start)-[*..{max_length}]-(end))
        WHERE ALL(n IN nodes(path) WHERE n.org_id = $org_id)
        RETURN path
        """
        
        async with self.get_session() as session:
            result = await session.run(
                query,
                from_uid=from_uid,
                to_uid=to_uid,
                org_id=tenant_id,
                max_length=max_length
            )
            
            record = await result.single()
            if record:
                path = record["path"]
                return [dict(node) for node in path.nodes]
            
            return None
    
    async def calculate_centrality(self, label: str, tenant_id: str,
                                 algorithm: str = "pagerank") -> List[Dict[str, Any]]:
        """Calculate centrality scores for nodes."""
        if algorithm == "pagerank":
            query = f"""
            CALL gds.pageRank.stream({{
                nodeQuery: 'MATCH (n:{label} {{org_id: $org_id}}) RETURN id(n) as id',
                relationshipQuery: 'MATCH (a:{label} {{org_id: $org_id}})-[r]->(b:{label} {{org_id: $org_id}}) RETURN id(a) as source, id(b) as target'
            }})
            YIELD nodeId, score
            RETURN gds.util.asNode(nodeId) AS node, score
            ORDER BY score DESC
            LIMIT 100
            """
        elif algorithm == "betweenness":
            query = f"""
            CALL gds.betweenness.stream({{
                nodeQuery: 'MATCH (n:{label} {{org_id: $org_id}}) RETURN id(n) as id',
                relationshipQuery: 'MATCH (a:{label} {{org_id: $org_id}})-[r]->(b:{label} {{org_id: $org_id}}) RETURN id(a) as source, id(b) as target'
            }})
            YIELD nodeId, score
            RETURN gds.util.asNode(nodeId) AS node, score
            ORDER BY score DESC
            LIMIT 100
            """
        else:
            raise ValueError(f"Unknown centrality algorithm: {algorithm}")
        
        async with self.get_session() as session:
            result = await session.run(query, org_id=tenant_id)
            
            records = []
            async for record in result:
                node_data = dict(record["node"])
                node_data["_centrality_score"] = record["score"]
                records.append(node_data)
            
            return records
    
    # Content-specific Operations
    async def create_content_node(self, content_data: Dict[str, Any],
                                tenant_id: str) -> ContentNode:
        """Create a content node with all relationships."""
        # Create content node
        content_node = await self.create_node(
            content_data,
            ["Content"],
            tenant_id
        )
        
        return ContentNode(**content_node)
    
    async def link_content_to_topics(self, content_uid: str, topic_uids: List[str],
                                   relevance_scores: Optional[List[float]] = None,
                                   tenant_id: str = None) -> int:
        """Link content to multiple topics."""
        if not relevance_scores:
            relevance_scores = [1.0] * len(topic_uids)
        
        created = 0
        for topic_uid, score in zip(topic_uids, relevance_scores):
            success = await self.create_relationship(
                content_uid, "Content",
                topic_uid, "Topic",
                "HAS_TOPIC",
                {"relevance_score": score},
                tenant_id
            )
            if success:
                created += 1
        
        return created
    
    async def find_similar_content(self, content_uid: str, tenant_id: str,
                                 similarity_threshold: float = 0.7,
                                 limit: int = 10) -> List[Dict[str, Any]]:
        """Find content similar to given content based on shared connections."""
        query = """
        MATCH (c:Content {uid: $content_uid, org_id: $org_id})
        MATCH (c)-[:HAS_TOPIC|:CONTAINS_KEYWORD|:EXPRESSES_CONCEPT]->()<-[:HAS_TOPIC|:CONTAINS_KEYWORD|:EXPRESSES_CONCEPT]-(similar:Content)
        WHERE similar.uid <> c.uid
        WITH similar, COUNT(*) as shared_connections,
             COLLECT(DISTINCT labels(similar)) as node_labels
        WHERE shared_connections >= $min_connections
        RETURN similar, shared_connections,
               shared_connections * 1.0 / (SIZE((c)--()) + SIZE((similar)--()) - shared_connections) as jaccard_similarity
        ORDER BY jaccard_similarity DESC
        LIMIT $limit
        """
        
        min_connections = int(similarity_threshold * 3)  # Rough heuristic
        
        async with self.get_session() as session:
            result = await session.run(
                query,
                content_uid=content_uid,
                org_id=tenant_id,
                min_connections=min_connections,
                limit=limit
            )
            
            similar_content = []
            async for record in result:
                content_data = dict(record["similar"])
                content_data["_similarity_score"] = record["jaccard_similarity"]
                content_data["_shared_connections"] = record["shared_connections"]
                similar_content.append(content_data)
            
            return similar_content
    
    # Batch Operations
    async def batch_create_nodes(self, nodes_data: List[Dict[str, Any]],
                               label: str, tenant_id: str) -> int:
        """Create multiple nodes in a batch."""
        # Add tenant context to all nodes
        for node in nodes_data:
            node["org_id"] = tenant_id
        
        query = f"""
        UNWIND $nodes AS node
        CREATE (n:{label})
        SET n = node
        RETURN COUNT(n) as created
        """
        
        async with self.get_session() as session:
            result = await session.run(query, nodes=nodes_data)
            record = await result.single()
            return record["created"]
    
    async def batch_create_relationships(self, relationships: List[Dict[str, Any]],
                                       tenant_id: str) -> int:
        """Create multiple relationships in a batch."""
        query = """
        UNWIND $relationships AS rel
        MATCH (a {uid: rel.from_uid, org_id: $org_id})
        MATCH (b {uid: rel.to_uid, org_id: $org_id})
        CREATE (a)-[r:TEMP_REL]->(b)
        SET r = rel.properties, r.type = rel.type
        WITH r, rel.type as relType
        CALL apoc.refactor.setType(r, relType) YIELD output
        RETURN COUNT(output) as created
        """
        
        async with self.get_session() as session:
            result = await session.run(
                query,
                relationships=relationships,
                org_id=tenant_id
            )
            record = await result.single()
            return record["created"]
    
    # Maintenance Operations
    async def cleanup_orphaned_nodes(self, tenant_id: str) -> int:
        """Remove nodes with no relationships."""
        query = """
        MATCH (n {org_id: $org_id})
        WHERE NOT (n)--()
        DELETE n
        RETURN COUNT(n) as deleted
        """
        
        async with self.get_session() as session:
            result = await session.run(query, org_id=tenant_id)
            record = await result.single()
            return record["deleted"]
    
    async def get_graph_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get statistics about the graph for a tenant."""
        query = """
        MATCH (n {org_id: $org_id})
        WITH labels(n) as node_labels, COUNT(n) as count
        RETURN node_labels, count
        ORDER BY count DESC
        """
        
        relationship_query = """
        MATCH (a {org_id: $org_id})-[r]-(b {org_id: $org_id})
        RETURN type(r) as rel_type, COUNT(r) as count
        ORDER BY count DESC
        """
        
        async with self.get_session() as session:
            # Get node counts
            node_result = await session.run(query, org_id=tenant_id)
            node_stats = {}
            async for record in node_result:
                labels = record["node_labels"]
                if labels:
                    node_stats[labels[0]] = record["count"]
            
            # Get relationship counts
            rel_result = await session.run(relationship_query, org_id=tenant_id)
            rel_stats = {}
            async for record in rel_result:
                rel_stats[record["rel_type"]] = record["count"]
            
            return {
                "nodes": node_stats,
                "relationships": rel_stats,
                "total_nodes": sum(node_stats.values()),
                "total_relationships": sum(rel_stats.values())
            }


# Global client instance
neo4j_client = Neo4jClient()