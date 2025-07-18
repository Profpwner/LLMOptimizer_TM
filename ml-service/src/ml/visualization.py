"""
Visualization Components
Generates 3D semantic networks and interactive visualizations
"""

import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import networkx as nx
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import colorsys

logger = logging.getLogger(__name__)


@dataclass
class VisualizationConfig:
    """Configuration for visualizations"""
    layout_algorithm: str = "force"  # force, spring, kamada_kawai
    node_size_metric: str = "pagerank"  # pagerank, degree, fixed
    edge_width_metric: str = "weight"  # weight, fixed
    color_by: str = "community"  # community, type, score
    show_labels: bool = True
    dimensions: int = 3  # 2D or 3D
    export_format: str = "html"  # html, json, png


class VisualizationEngine:
    """Engine for creating semantic network visualizations"""
    
    def __init__(self):
        self.color_palettes = {
            "default": px.colors.qualitative.Plotly,
            "semantic": px.colors.sequential.Viridis,
            "diverging": px.colors.diverging.RdBu
        }
    
    def generate_3d_network(
        self,
        content_mesh,
        config: Optional[VisualizationConfig] = None
    ) -> Dict[str, Any]:
        """Generate 3D network visualization data"""
        if config is None:
            config = VisualizationConfig()
        
        # Get graph from content mesh
        graph = content_mesh.graph
        
        # Calculate layout
        pos = self._calculate_layout(graph, config)
        
        # Prepare node data
        node_data = self._prepare_node_data(graph, pos, content_mesh, config)
        
        # Prepare edge data
        edge_data = self._prepare_edge_data(graph, pos, config)
        
        # Create plotly figure
        fig = self._create_3d_figure(node_data, edge_data, config)
        
        # Also prepare Three.js compatible data
        threejs_data = self._prepare_threejs_data(node_data, edge_data, graph)
        
        return {
            "plotly_figure": fig,
            "threejs_data": threejs_data,
            "layout_positions": pos
        }
    
    def _calculate_layout(
        self,
        graph: nx.Graph,
        config: VisualizationConfig
    ) -> Dict[str, np.ndarray]:
        """Calculate graph layout positions"""
        if config.layout_algorithm == "force":
            if config.dimensions == 3:
                # Use spring layout and add third dimension
                pos_2d = nx.spring_layout(graph, k=1, iterations=50, weight='weight')
                pos = {}
                for node, (x, y) in pos_2d.items():
                    z = np.random.uniform(-0.5, 0.5)
                    pos[node] = np.array([x, y, z])
            else:
                pos = nx.spring_layout(graph, k=1, iterations=50, weight='weight')
                pos = {node: np.array([x, y]) for node, (x, y) in pos.items()}
        
        elif config.layout_algorithm == "kamada_kawai":
            pos = nx.kamada_kawai_layout(graph, weight='weight')
            if config.dimensions == 3:
                pos = {node: np.array([x, y, np.random.uniform(-0.5, 0.5)]) 
                      for node, (x, y) in pos.items()}
            else:
                pos = {node: np.array([x, y]) for node, (x, y) in pos.items()}
        
        else:  # spring
            pos = nx.spring_layout(graph, weight='weight')
            if config.dimensions == 3:
                pos = {node: np.array([x, y, np.random.uniform(-0.5, 0.5)]) 
                      for node, (x, y) in pos.items()}
            else:
                pos = {node: np.array([x, y]) for node, (x, y) in pos.items()}
        
        return pos
    
    def _prepare_node_data(
        self,
        graph: nx.Graph,
        pos: Dict[str, np.ndarray],
        content_mesh,
        config: VisualizationConfig
    ) -> Dict[str, Any]:
        """Prepare node data for visualization"""
        nodes = list(graph.nodes())
        
        # Extract positions
        if config.dimensions == 3:
            x = [pos[node][0] for node in nodes]
            y = [pos[node][1] for node in nodes]
            z = [pos[node][2] for node in nodes]
        else:
            x = [pos[node][0] for node in nodes]
            y = [pos[node][1] for node in nodes]
            z = None
        
        # Calculate node sizes
        if config.node_size_metric == "pagerank":
            pagerank = nx.pagerank(graph, weight='weight')
            sizes = [pagerank.get(node, 0.1) * 100 for node in nodes]
        elif config.node_size_metric == "degree":
            degrees = dict(graph.degree())
            max_degree = max(degrees.values()) if degrees else 1
            sizes = [degrees[node] / max_degree * 50 + 10 for node in nodes]
        else:
            sizes = [20] * len(nodes)
        
        # Determine node colors
        if config.color_by == "community":
            communities = {}
            for node in nodes:
                communities[node] = graph.nodes[node].get('community', 0)
            unique_communities = list(set(communities.values()))
            color_map = {comm: i for i, comm in enumerate(unique_communities)}
            colors = [color_map[communities[node]] for node in nodes]
        elif config.color_by == "type":
            node_types = {}
            for node in nodes:
                node_types[node] = graph.nodes[node].get('node_type', 'default')
            unique_types = list(set(node_types.values()))
            color_map = {t: i for i, t in enumerate(unique_types)}
            colors = [color_map[node_types[node]] for node in nodes]
        else:
            colors = list(range(len(nodes)))
        
        # Prepare hover text
        hover_texts = []
        for node in nodes:
            attrs = graph.nodes[node]
            text = f"<b>{attrs.get('title', node)}</b><br>"
            text += f"Type: {attrs.get('node_type', 'content')}<br>"
            text += f"Community: {attrs.get('community', 'N/A')}<br>"
            text += f"PageRank: {attrs.get('pagerank', 0):.3f}<br>"
            text += f"Degree: {graph.degree(node)}"
            hover_texts.append(text)
        
        return {
            "nodes": nodes,
            "x": x,
            "y": y,
            "z": z,
            "sizes": sizes,
            "colors": colors,
            "hover_texts": hover_texts
        }
    
    def _prepare_edge_data(
        self,
        graph: nx.Graph,
        pos: Dict[str, np.ndarray],
        config: VisualizationConfig
    ) -> Dict[str, Any]:
        """Prepare edge data for visualization"""
        edge_x = []
        edge_y = []
        edge_z = [] if config.dimensions == 3 else None
        edge_weights = []
        
        for edge in graph.edges():
            x0, y0 = pos[edge[0]][0], pos[edge[0]][1]
            x1, y1 = pos[edge[1]][0], pos[edge[1]][1]
            
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
            
            if config.dimensions == 3:
                z0, z1 = pos[edge[0]][2], pos[edge[1]][2]
                edge_z.extend([z0, z1, None])
            
            weight = graph[edge[0]][edge[1]].get('weight', 1.0)
            edge_weights.append(weight)
        
        return {
            "x": edge_x,
            "y": edge_y,
            "z": edge_z,
            "weights": edge_weights
        }
    
    def _create_3d_figure(
        self,
        node_data: Dict[str, Any],
        edge_data: Dict[str, Any],
        config: VisualizationConfig
    ) -> go.Figure:
        """Create Plotly 3D figure"""
        fig = go.Figure()
        
        # Add edges
        if config.dimensions == 3:
            edge_trace = go.Scatter3d(
                x=edge_data["x"],
                y=edge_data["y"],
                z=edge_data["z"],
                mode='lines',
                line=dict(width=0.5, color='#888'),
                hoverinfo='none'
            )
        else:
            edge_trace = go.Scatter(
                x=edge_data["x"],
                y=edge_data["y"],
                mode='lines',
                line=dict(width=0.5, color='#888'),
                hoverinfo='none'
            )
        
        fig.add_trace(edge_trace)
        
        # Add nodes
        if config.dimensions == 3:
            node_trace = go.Scatter3d(
                x=node_data["x"],
                y=node_data["y"],
                z=node_data["z"],
                mode='markers+text' if config.show_labels else 'markers',
                marker=dict(
                    size=node_data["sizes"],
                    color=node_data["colors"],
                    colorscale='Viridis',
                    showscale=True,
                    colorbar=dict(
                        thickness=15,
                        title=config.color_by.capitalize(),
                        xanchor='left',
                        titleside='right'
                    ),
                    line=dict(width=2, color='white')
                ),
                text=node_data["nodes"] if config.show_labels else None,
                textposition="top center",
                hovertext=node_data["hover_texts"],
                hoverinfo='text'
            )
        else:
            node_trace = go.Scatter(
                x=node_data["x"],
                y=node_data["y"],
                mode='markers+text' if config.show_labels else 'markers',
                marker=dict(
                    size=node_data["sizes"],
                    color=node_data["colors"],
                    colorscale='Viridis',
                    showscale=True,
                    colorbar=dict(
                        thickness=15,
                        title=config.color_by.capitalize(),
                        xanchor='left',
                        titleside='right'
                    ),
                    line=dict(width=2, color='white')
                ),
                text=node_data["nodes"] if config.show_labels else None,
                textposition="top center",
                hovertext=node_data["hover_texts"],
                hoverinfo='text'
            )
        
        fig.add_trace(node_trace)
        
        # Update layout
        if config.dimensions == 3:
            fig.update_layout(
                title="3D Semantic Content Network",
                showlegend=False,
                hovermode='closest',
                margin=dict(b=20, l=5, r=5, t=40),
                scene=dict(
                    xaxis=dict(showgrid=False, showticklabels=False, title=''),
                    yaxis=dict(showgrid=False, showticklabels=False, title=''),
                    zaxis=dict(showgrid=False, showticklabels=False, title=''),
                    camera=dict(
                        eye=dict(x=1.5, y=1.5, z=1.5)
                    )
                ),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
        else:
            fig.update_layout(
                title="Semantic Content Network",
                showlegend=False,
                hovermode='closest',
                margin=dict(b=20, l=5, r=5, t=40),
                xaxis=dict(showgrid=False, showticklabels=False),
                yaxis=dict(showgrid=False, showticklabels=False),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
        
        return fig
    
    def _prepare_threejs_data(
        self,
        node_data: Dict[str, Any],
        edge_data: Dict[str, Any],
        graph: nx.Graph
    ) -> Dict[str, Any]:
        """Prepare data for Three.js visualization"""
        # Prepare nodes for Three.js
        nodes = []
        for i, node_id in enumerate(node_data["nodes"]):
            node = {
                "id": node_id,
                "x": float(node_data["x"][i]),
                "y": float(node_data["y"][i]),
                "z": float(node_data["z"][i]) if node_data["z"] else 0,
                "size": float(node_data["sizes"][i]),
                "color": int(node_data["colors"][i]),
                "label": graph.nodes[node_id].get('title', node_id),
                "metadata": dict(graph.nodes[node_id])
            }
            nodes.append(node)
        
        # Prepare edges for Three.js
        edges = []
        for edge in graph.edges():
            edge_data_dict = {
                "source": edge[0],
                "target": edge[1],
                "weight": float(graph[edge[0]][edge[1]].get('weight', 1.0)),
                "type": graph[edge[0]][edge[1]].get('edge_type', 'semantic')
            }
            edges.append(edge_data_dict)
        
        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "communities": len(set(node_data["colors"]))
            }
        }
    
    def generate_gap_visualization(
        self,
        gaps: List[Any],
        config: Optional[VisualizationConfig] = None
    ) -> go.Figure:
        """Generate visualization of semantic gaps"""
        if config is None:
            config = VisualizationConfig()
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Gap Severity Distribution', 'Gaps by Type',
                          'Priority Matrix', 'Coverage Heatmap'),
            specs=[[{'type': 'bar'}, {'type': 'pie'}],
                   [{'type': 'scatter'}, {'type': 'heatmap'}]]
        )
        
        # Gap severity distribution
        severities = [gap.severity for gap in gaps]
        fig.add_trace(
            go.Histogram(x=severities, nbinsx=20, name='Severity'),
            row=1, col=1
        )
        
        # Gaps by type
        gap_types = {}
        for gap in gaps:
            gap_types[gap.gap_type] = gap_types.get(gap.gap_type, 0) + 1
        
        fig.add_trace(
            go.Pie(labels=list(gap_types.keys()), values=list(gap_types.values())),
            row=1, col=2
        )
        
        # Priority matrix
        x = [gap.severity for gap in gaps]
        y = [len(gap.affected_topics) for gap in gaps]
        colors = ['red' if gap.severity > 0.8 else 'yellow' if gap.severity > 0.5 else 'green' 
                 for gap in gaps]
        
        fig.add_trace(
            go.Scatter(
                x=x, y=y,
                mode='markers',
                marker=dict(size=10, color=colors),
                text=[gap.description[:50] + '...' for gap in gaps],
                hovertemplate='<b>%{text}</b><br>Severity: %{x}<br>Affected Topics: %{y}'
            ),
            row=2, col=1
        )
        
        # Coverage heatmap (simplified)
        # Create a matrix of gap impacts
        gap_impact_matrix = np.zeros((min(10, len(gaps)), 5))
        for i, gap in enumerate(gaps[:10]):
            gap_impact_matrix[i, 0] = gap.severity
            gap_impact_matrix[i, 1] = len(gap.affected_topics)
            gap_impact_matrix[i, 2] = len(gap.recommendations)
            gap_impact_matrix[i, 3] = 1 if gap.gap_type == "missing_topic" else 0
            gap_impact_matrix[i, 4] = 1 if gap.gap_type == "competitor_advantage" else 0
        
        fig.add_trace(
            go.Heatmap(
                z=gap_impact_matrix,
                x=['Severity', 'Topics', 'Recommendations', 'Missing', 'Competitive'],
                y=[f'Gap {i+1}' for i in range(gap_impact_matrix.shape[0])],
                colorscale='RdBu'
            ),
            row=2, col=2
        )
        
        # Update layout
        fig.update_layout(
            title_text="Semantic Gap Analysis Dashboard",
            showlegend=False,
            height=800
        )
        
        return fig
    
    def generate_embedding_visualization(
        self,
        embeddings: np.ndarray,
        labels: Optional[List[str]] = None,
        clusters: Optional[np.ndarray] = None,
        method: str = "pca"
    ) -> go.Figure:
        """Visualize embeddings in 2D or 3D space"""
        # Reduce dimensions if needed
        if embeddings.shape[1] > 3:
            from sklearn.decomposition import PCA
            from sklearn.manifold import TSNE
            
            if method == "pca":
                reducer = PCA(n_components=3)
                reduced = reducer.fit_transform(embeddings)
            elif method == "tsne":
                reducer = TSNE(n_components=3, random_state=42)
                reduced = reducer.fit_transform(embeddings)
            else:
                reduced = embeddings[:, :3]
        else:
            reduced = embeddings
        
        # Create figure
        fig = go.Figure()
        
        # Add points
        if clusters is not None:
            # Color by cluster
            unique_clusters = np.unique(clusters)
            for cluster in unique_clusters:
                mask = clusters == cluster
                cluster_points = reduced[mask]
                
                trace = go.Scatter3d(
                    x=cluster_points[:, 0],
                    y=cluster_points[:, 1],
                    z=cluster_points[:, 2] if reduced.shape[1] > 2 else np.zeros(len(cluster_points)),
                    mode='markers',
                    name=f'Cluster {cluster}',
                    marker=dict(size=5),
                    text=labels[mask] if labels is not None else None,
                    hovertemplate='<b>%{text}</b><br>X: %{x}<br>Y: %{y}<br>Z: %{z}'
                )
                fig.add_trace(trace)
        else:
            # Single color
            trace = go.Scatter3d(
                x=reduced[:, 0],
                y=reduced[:, 1],
                z=reduced[:, 2] if reduced.shape[1] > 2 else np.zeros(len(reduced)),
                mode='markers',
                marker=dict(size=5, color='blue'),
                text=labels if labels is not None else None,
                hovertemplate='<b>%{text}</b><br>X: %{x}<br>Y: %{y}<br>Z: %{z}'
            )
            fig.add_trace(trace)
        
        # Update layout
        fig.update_layout(
            title=f"Embedding Visualization ({method.upper()})",
            scene=dict(
                xaxis_title="Component 1",
                yaxis_title="Component 2",
                zaxis_title="Component 3"
            ),
            height=600
        )
        
        return fig
    
    def export_visualization(
        self,
        figure: go.Figure,
        filename: str,
        format: str = "html"
    ) -> str:
        """Export visualization to file"""
        if format == "html":
            figure.write_html(filename)
        elif format == "png":
            figure.write_image(filename)
        elif format == "json":
            figure.write_json(filename)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        return filename