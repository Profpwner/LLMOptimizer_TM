"""
Content Mesh Algorithm
Builds and optimizes semantic content graphs using NetworkX
"""

import networkx as nx
import numpy as np
import logging
from typing import List, Dict, Any, Tuple, Optional, Set
from dataclasses import dataclass
import community as community_louvain
from collections import defaultdict
import json
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


@dataclass
class ContentNode:
    """Represents a content node in the mesh"""
    id: str
    title: str
    content: str
    embedding: np.ndarray
    metadata: Dict[str, Any]
    node_type: str = "content"  # content, topic, keyword


@dataclass
class ContentEdge:
    """Represents an edge between content nodes"""
    source: str
    target: str
    weight: float
    edge_type: str = "semantic"  # semantic, reference, topic


@dataclass
class MeshConfig:
    """Configuration for content mesh generation"""
    similarity_threshold: float = 0.7
    max_edges_per_node: int = 10
    min_community_size: int = 3
    use_pagerank: bool = True
    use_community_detection: bool = True
    edge_types: List[str] = None
    
    def __post_init__(self):
        if self.edge_types is None:
            self.edge_types = ["semantic", "reference", "topic"]


class ContentMesh:
    """Manages semantic content mesh/graph"""
    
    def __init__(self, similarity_engine):
        self.similarity_engine = similarity_engine
        self.graph = nx.Graph()
        self.nodes = {}
        self.embeddings = {}
        self.communities = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
        
    def add_node(self, node: ContentNode):
        """Add a node to the content mesh"""
        self.nodes[node.id] = node
        self.embeddings[node.id] = node.embedding
        
        # Add to graph with attributes
        self.graph.add_node(
            node.id,
            title=node.title,
            node_type=node.node_type,
            metadata=node.metadata
        )
    
    def add_edge(self, edge: ContentEdge):
        """Add an edge to the content mesh"""
        if edge.source in self.nodes and edge.target in self.nodes:
            self.graph.add_edge(
                edge.source,
                edge.target,
                weight=edge.weight,
                edge_type=edge.edge_type
            )
    
    async def build_mesh(
        self,
        nodes: List[ContentNode],
        config: Optional[MeshConfig] = None
    ):
        """Build content mesh from nodes"""
        if config is None:
            config = MeshConfig()
        
        logger.info(f"Building content mesh with {len(nodes)} nodes")
        
        # Add all nodes
        for node in nodes:
            self.add_node(node)
        
        # Build similarity index
        embeddings = np.array([node.embedding for node in nodes])
        await self.similarity_engine.build_index(
            embeddings,
            "content_mesh",
            metadata=[{"id": node.id} for node in nodes]
        )
        
        # Create edges based on similarity
        await self._create_similarity_edges(nodes, config)
        
        # Detect communities if enabled
        if config.use_community_detection:
            await self._detect_communities(config)
        
        # Calculate PageRank if enabled
        if config.use_pagerank:
            await self._calculate_pagerank()
        
        logger.info(f"Content mesh built with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges")
    
    async def _create_similarity_edges(
        self,
        nodes: List[ContentNode],
        config: MeshConfig
    ):
        """Create edges based on content similarity"""
        loop = asyncio.get_event_loop()
        
        def create_edges():
            edges = []
            
            # For each node, find similar nodes
            for i, node in enumerate(nodes):
                # Search for similar content
                similarities = self.similarity_engine.compute_pairwise_similarities(
                    np.array([node.embedding, *[n.embedding for n in nodes if n.id != node.id]])
                )[0, 1:]  # Get similarities to other nodes
                
                # Get top k similar nodes above threshold
                similar_indices = np.where(similarities >= config.similarity_threshold)[0]
                similar_scores = similarities[similar_indices]
                
                # Sort by similarity and limit edges
                if len(similar_indices) > 0:
                    sorted_indices = np.argsort(similar_scores)[::-1][:config.max_edges_per_node]
                    
                    for idx in sorted_indices:
                        # Adjust index to account for skipped self
                        actual_idx = similar_indices[idx]
                        if actual_idx >= i:
                            actual_idx += 1
                        
                        target_node = nodes[actual_idx]
                        edge = ContentEdge(
                            source=node.id,
                            target=target_node.id,
                            weight=float(similar_scores[idx]),
                            edge_type="semantic"
                        )
                        edges.append(edge)
            
            return edges
        
        edges = await loop.run_in_executor(self.executor, create_edges)
        
        # Add edges to graph
        for edge in edges:
            self.add_edge(edge)
    
    async def _detect_communities(self, config: MeshConfig):
        """Detect communities in the content mesh"""
        loop = asyncio.get_event_loop()
        
        def detect():
            # Use Louvain method for community detection
            partition = community_louvain.best_partition(
                self.graph,
                weight='weight'
            )
            
            # Group nodes by community
            communities = defaultdict(list)
            for node_id, community_id in partition.items():
                communities[community_id].append(node_id)
            
            # Filter out small communities
            filtered_communities = {}
            community_idx = 0
            for comm_id, members in communities.items():
                if len(members) >= config.min_community_size:
                    filtered_communities[community_idx] = members
                    community_idx += 1
            
            # Calculate modularity
            modularity = community_louvain.modularity(partition, self.graph)
            
            return filtered_communities, modularity
        
        self.communities, modularity = await loop.run_in_executor(
            self.executor, detect
        )
        
        # Add community info to nodes
        for comm_id, members in self.communities.items():
            for node_id in members:
                self.graph.nodes[node_id]['community'] = comm_id
        
        logger.info(f"Detected {len(self.communities)} communities with modularity {modularity:.3f}")
    
    async def _calculate_pagerank(self):
        """Calculate PageRank scores for nodes"""
        loop = asyncio.get_event_loop()
        
        def calculate():
            return nx.pagerank(self.graph, weight='weight')
        
        pagerank_scores = await loop.run_in_executor(self.executor, calculate)
        
        # Add PageRank scores to nodes
        for node_id, score in pagerank_scores.items():
            self.graph.nodes[node_id]['pagerank'] = score
    
    def find_content_gaps(self, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Identify gaps in the content mesh"""
        gaps = []
        
        # Find disconnected components
        components = list(nx.connected_components(self.graph))
        if len(components) > 1:
            # Multiple disconnected components indicate content gaps
            for i, comp1 in enumerate(components):
                for j, comp2 in enumerate(components[i+1:], i+1):
                    # Calculate average embedding for each component
                    emb1 = np.mean([self.embeddings[n] for n in comp1], axis=0)
                    emb2 = np.mean([self.embeddings[n] for n in comp2], axis=0)
                    
                    # Calculate similarity
                    similarity = np.dot(emb1, emb2)
                    
                    if similarity > threshold:
                        gaps.append({
                            "type": "disconnected_components",
                            "component1": list(comp1),
                            "component2": list(comp2),
                            "similarity": float(similarity),
                            "suggestion": "These components are semantically related but not connected"
                        })
        
        # Find nodes with low connectivity
        for node in self.graph.nodes():
            degree = self.graph.degree(node)
            if degree < 2:  # Poorly connected
                gaps.append({
                    "type": "low_connectivity",
                    "node": node,
                    "degree": degree,
                    "suggestion": f"Node '{node}' has low connectivity and may need more related content"
                })
        
        # Find communities with weak inter-connections
        if self.communities:
            for comm_id, members in self.communities.items():
                # Calculate internal density
                subgraph = self.graph.subgraph(members)
                density = nx.density(subgraph)
                
                if density < 0.3:  # Low internal density
                    gaps.append({
                        "type": "weak_community",
                        "community_id": comm_id,
                        "members": members,
                        "density": density,
                        "suggestion": f"Community {comm_id} has weak internal connections"
                    })
        
        return gaps
    
    def optimize_mesh(self, config: Optional[MeshConfig] = None) -> Dict[str, Any]:
        """Optimize the content mesh structure"""
        if config is None:
            config = MeshConfig()
        
        optimizations = {
            "edges_added": 0,
            "edges_removed": 0,
            "nodes_repositioned": 0
        }
        
        # Remove weak edges
        edges_to_remove = []
        for u, v, data in self.graph.edges(data=True):
            if data.get('weight', 1.0) < config.similarity_threshold * 0.5:
                edges_to_remove.append((u, v))
        
        for edge in edges_to_remove:
            self.graph.remove_edge(*edge)
            optimizations["edges_removed"] += 1
        
        # Add edges to connect related but disconnected nodes
        for node in self.graph.nodes():
            if self.graph.degree(node) < 2:
                # Find most similar unconnected nodes
                node_embedding = self.embeddings[node]
                similarities = {}
                
                for other_node in self.graph.nodes():
                    if other_node != node and not self.graph.has_edge(node, other_node):
                        other_embedding = self.embeddings[other_node]
                        similarity = np.dot(node_embedding, other_embedding)
                        if similarity >= config.similarity_threshold:
                            similarities[other_node] = similarity
                
                # Add edges to top similar nodes
                for other_node, similarity in sorted(
                    similarities.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:3]:
                    self.add_edge(ContentEdge(
                        source=node,
                        target=other_node,
                        weight=similarity,
                        edge_type="semantic"
                    ))
                    optimizations["edges_added"] += 1
        
        return optimizations
    
    def get_node_recommendations(
        self,
        node_id: str,
        n_recommendations: int = 5
    ) -> List[Tuple[str, float]]:
        """Get content recommendations based on mesh structure"""
        if node_id not in self.graph:
            return []
        
        # Use personalized PageRank for recommendations
        try:
            ppr = nx.pagerank(
                self.graph,
                personalization={node_id: 1.0},
                weight='weight'
            )
            
            # Remove the source node and sort by score
            ppr.pop(node_id, None)
            recommendations = sorted(
                ppr.items(),
                key=lambda x: x[1],
                reverse=True
            )[:n_recommendations]
            
            return recommendations
        except:
            # Fallback to neighbor-based recommendations
            neighbors = []
            for neighbor in self.graph.neighbors(node_id):
                weight = self.graph[node_id][neighbor].get('weight', 1.0)
                neighbors.append((neighbor, weight))
            
            return sorted(neighbors, key=lambda x: x[1], reverse=True)[:n_recommendations]
    
    def get_shortest_path(
        self,
        source: str,
        target: str
    ) -> Optional[List[str]]:
        """Find shortest path between two nodes"""
        try:
            return nx.shortest_path(
                self.graph,
                source=source,
                target=target,
                weight=lambda u, v, d: 1.0 / (d.get('weight', 1.0) + 0.1)
            )
        except nx.NetworkXNoPath:
            return None
    
    def export_mesh(self, format: str = "json") -> Any:
        """Export content mesh in various formats"""
        if format == "json":
            # Convert to node-link format
            data = nx.node_link_data(self.graph)
            
            # Add additional information
            data["communities"] = {
                str(k): v for k, v in self.communities.items()
            }
            data["metadata"] = {
                "created_at": datetime.utcnow().isoformat(),
                "num_nodes": self.graph.number_of_nodes(),
                "num_edges": self.graph.number_of_edges(),
                "num_communities": len(self.communities)
            }
            
            return json.dumps(data, indent=2)
        
        elif format == "gexf":
            # Export as GEXF for Gephi
            return nx.generate_gexf(self.graph)
        
        elif format == "graphml":
            # Export as GraphML
            return nx.generate_graphml(self.graph)
        
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def get_mesh_statistics(self) -> Dict[str, Any]:
        """Get statistics about the content mesh"""
        stats = {
            "num_nodes": self.graph.number_of_nodes(),
            "num_edges": self.graph.number_of_edges(),
            "density": nx.density(self.graph),
            "num_communities": len(self.communities),
            "avg_degree": sum(dict(self.graph.degree()).values()) / self.graph.number_of_nodes() if self.graph.number_of_nodes() > 0 else 0,
            "connected_components": nx.number_connected_components(self.graph)
        }
        
        # Add community statistics
        if self.communities:
            community_sizes = [len(members) for members in self.communities.values()]
            stats["avg_community_size"] = np.mean(community_sizes)
            stats["max_community_size"] = max(community_sizes)
            stats["min_community_size"] = min(community_sizes)
        
        # Add centrality measures
        if self.graph.number_of_nodes() > 0:
            degree_centrality = nx.degree_centrality(self.graph)
            stats["avg_degree_centrality"] = np.mean(list(degree_centrality.values()))
            
            if nx.is_connected(self.graph):
                stats["diameter"] = nx.diameter(self.graph)
                stats["radius"] = nx.radius(self.graph)
        
        return stats