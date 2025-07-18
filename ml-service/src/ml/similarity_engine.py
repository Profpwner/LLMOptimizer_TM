"""
Similarity Computation Engine
Handles efficient similarity search and clustering using FAISS and other algorithms
"""

import numpy as np
import faiss
import logging
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
from sklearn.decomposition import PCA
import torch
from annoy import AnnoyIndex
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


@dataclass
class SimilarityConfig:
    """Configuration for similarity computation"""
    metric: str = "cosine"  # cosine, euclidean, dot
    threshold: float = 0.7
    use_gpu: bool = False
    index_type: str = "faiss"  # faiss, annoy
    n_neighbors: int = 10
    clustering_algorithm: str = "kmeans"  # kmeans, dbscan, hierarchical


@dataclass
class SearchResult:
    """Result from similarity search"""
    index: int
    score: float
    metadata: Dict[str, Any]


class SimilarityEngine:
    """Engine for computing similarities and performing efficient search"""
    
    def __init__(self):
        self.indices = {}
        self.metadata_store = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Similarity Engine initialized with device: {self.device}")
    
    def _normalize_vectors(self, vectors: np.ndarray) -> np.ndarray:
        """Normalize vectors for cosine similarity"""
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / (norms + 1e-8)
    
    def create_faiss_index(
        self,
        dimension: int,
        config: SimilarityConfig
    ) -> faiss.Index:
        """Create FAISS index based on configuration"""
        if config.metric == "cosine":
            # Use Inner Product for normalized vectors (equivalent to cosine)
            if config.use_gpu and faiss.get_num_gpus() > 0:
                # GPU index
                flat_config = faiss.GpuIndexFlatConfig()
                flat_config.device = 0
                index = faiss.GpuIndexFlatIP(
                    faiss.StandardGpuResources(),
                    dimension,
                    flat_config
                )
            else:
                # CPU index
                index = faiss.IndexFlatIP(dimension)
        
        elif config.metric == "euclidean":
            if config.use_gpu and faiss.get_num_gpus() > 0:
                flat_config = faiss.GpuIndexFlatConfig()
                flat_config.device = 0
                index = faiss.GpuIndexFlatL2(
                    faiss.StandardGpuResources(),
                    dimension,
                    flat_config
                )
            else:
                index = faiss.IndexFlatL2(dimension)
        
        else:  # dot product
            if config.use_gpu and faiss.get_num_gpus() > 0:
                flat_config = faiss.GpuIndexFlatConfig()
                flat_config.device = 0
                index = faiss.GpuIndexFlatIP(
                    faiss.StandardGpuResources(),
                    dimension,
                    flat_config
                )
            else:
                index = faiss.IndexFlatIP(dimension)
        
        return index
    
    def create_annoy_index(
        self,
        dimension: int,
        config: SimilarityConfig
    ) -> AnnoyIndex:
        """Create Annoy index for approximate search"""
        metric = "angular" if config.metric == "cosine" else "euclidean"
        index = AnnoyIndex(dimension, metric)
        return index
    
    async def build_index(
        self,
        embeddings: np.ndarray,
        index_name: str,
        config: Optional[SimilarityConfig] = None,
        metadata: Optional[List[Dict[str, Any]]] = None
    ):
        """Build similarity index from embeddings"""
        if config is None:
            config = SimilarityConfig()
        
        loop = asyncio.get_event_loop()
        
        # Normalize if using cosine similarity
        if config.metric == "cosine":
            embeddings = self._normalize_vectors(embeddings)
        
        dimension = embeddings.shape[1]
        
        if config.index_type == "faiss":
            # Build FAISS index
            def build_faiss():
                index = self.create_faiss_index(dimension, config)
                index.add(embeddings.astype(np.float32))
                return index
            
            index = await loop.run_in_executor(self.executor, build_faiss)
        
        else:  # annoy
            # Build Annoy index
            def build_annoy():
                index = self.create_annoy_index(dimension, config)
                for i, embedding in enumerate(embeddings):
                    index.add_item(i, embedding)
                index.build(50)  # 50 trees
                return index
            
            index = await loop.run_in_executor(self.executor, build_annoy)
        
        # Store index and metadata
        self.indices[index_name] = {
            "index": index,
            "config": config,
            "dimension": dimension,
            "size": len(embeddings)
        }
        
        if metadata:
            self.metadata_store[index_name] = metadata
        
        logger.info(f"Built {config.index_type} index '{index_name}' with {len(embeddings)} vectors")
    
    async def search(
        self,
        query_embedding: np.ndarray,
        index_name: str,
        k: Optional[int] = None
    ) -> List[SearchResult]:
        """Search for similar items in index"""
        if index_name not in self.indices:
            raise ValueError(f"Index '{index_name}' not found")
        
        index_info = self.indices[index_name]
        index = index_info["index"]
        config = index_info["config"]
        
        if k is None:
            k = config.n_neighbors
        
        # Ensure k doesn't exceed index size
        k = min(k, index_info["size"])
        
        # Normalize query if needed
        if config.metric == "cosine":
            query_embedding = self._normalize_vectors(query_embedding.reshape(1, -1))[0]
        
        loop = asyncio.get_event_loop()
        
        if config.index_type == "faiss":
            # FAISS search
            def faiss_search():
                distances, indices = index.search(
                    query_embedding.reshape(1, -1).astype(np.float32),
                    k
                )
                return distances[0], indices[0]
            
            distances, indices = await loop.run_in_executor(
                self.executor, faiss_search
            )
        
        else:  # annoy
            # Annoy search
            def annoy_search():
                indices, distances = index.get_nns_by_vector(
                    query_embedding,
                    k,
                    include_distances=True
                )
                return np.array(distances), np.array(indices)
            
            distances, indices = await loop.run_in_executor(
                self.executor, annoy_search
            )
        
        # Create search results
        results = []
        metadata = self.metadata_store.get(index_name, [])
        
        for i, (idx, dist) in enumerate(zip(indices, distances)):
            if idx >= 0:  # Valid index
                # Convert distance to similarity score
                if config.metric == "cosine":
                    score = float(dist)  # FAISS IP gives similarity directly
                elif config.metric == "euclidean":
                    score = 1.0 / (1.0 + float(dist))  # Convert distance to similarity
                else:
                    score = float(dist)
                
                result = SearchResult(
                    index=int(idx),
                    score=score,
                    metadata=metadata[idx] if idx < len(metadata) else {}
                )
                results.append(result)
        
        return results
    
    async def batch_search(
        self,
        query_embeddings: np.ndarray,
        index_name: str,
        k: Optional[int] = None
    ) -> List[List[SearchResult]]:
        """Batch search for multiple queries"""
        tasks = []
        for query in query_embeddings:
            task = self.search(query, index_name, k)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        return results
    
    def compute_pairwise_similarities(
        self,
        embeddings: np.ndarray,
        config: Optional[SimilarityConfig] = None
    ) -> np.ndarray:
        """Compute pairwise similarities between embeddings"""
        if config is None:
            config = SimilarityConfig()
        
        if config.metric == "cosine":
            embeddings = self._normalize_vectors(embeddings)
            similarities = np.dot(embeddings, embeddings.T)
        elif config.metric == "euclidean":
            # Convert euclidean distance to similarity
            distances = np.linalg.norm(
                embeddings[:, np.newaxis] - embeddings[np.newaxis, :],
                axis=2
            )
            similarities = 1.0 / (1.0 + distances)
        else:  # dot product
            similarities = np.dot(embeddings, embeddings.T)
        
        return similarities
    
    async def cluster_embeddings(
        self,
        embeddings: np.ndarray,
        n_clusters: Optional[int] = None,
        config: Optional[SimilarityConfig] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Cluster embeddings using specified algorithm"""
        if config is None:
            config = SimilarityConfig()
        
        loop = asyncio.get_event_loop()
        
        def perform_clustering():
            if config.clustering_algorithm == "kmeans":
                if n_clusters is None:
                    # Estimate optimal clusters using elbow method
                    n_clusters = self._estimate_optimal_clusters(embeddings)
                
                clusterer = KMeans(
                    n_clusters=n_clusters,
                    random_state=42,
                    n_init=10
                )
                labels = clusterer.fit_predict(embeddings)
                
                cluster_info = {
                    "n_clusters": n_clusters,
                    "centers": clusterer.cluster_centers_,
                    "inertia": clusterer.inertia_
                }
            
            elif config.clustering_algorithm == "dbscan":
                clusterer = DBSCAN(
                    eps=1 - config.threshold,  # Convert similarity to distance
                    min_samples=2,
                    metric="cosine" if config.metric == "cosine" else "euclidean"
                )
                labels = clusterer.fit_predict(embeddings)
                
                unique_labels = set(labels) - {-1}
                n_clusters = len(unique_labels)
                
                # Calculate cluster centers
                centers = []
                for label in unique_labels:
                    mask = labels == label
                    center = embeddings[mask].mean(axis=0)
                    centers.append(center)
                
                cluster_info = {
                    "n_clusters": n_clusters,
                    "centers": np.array(centers) if centers else np.array([]),
                    "n_noise": np.sum(labels == -1)
                }
            
            else:  # hierarchical
                if n_clusters is None:
                    n_clusters = self._estimate_optimal_clusters(embeddings)
                
                clusterer = AgglomerativeClustering(
                    n_clusters=n_clusters,
                    linkage="average",
                    metric="cosine" if config.metric == "cosine" else "euclidean"
                )
                labels = clusterer.fit_predict(embeddings)
                
                # Calculate cluster centers
                centers = []
                for i in range(n_clusters):
                    mask = labels == i
                    center = embeddings[mask].mean(axis=0)
                    centers.append(center)
                
                cluster_info = {
                    "n_clusters": n_clusters,
                    "centers": np.array(centers)
                }
            
            return labels, cluster_info
        
        labels, cluster_info = await loop.run_in_executor(
            self.executor, perform_clustering
        )
        
        return labels, cluster_info
    
    def _estimate_optimal_clusters(
        self,
        embeddings: np.ndarray,
        max_clusters: int = 10
    ) -> int:
        """Estimate optimal number of clusters using elbow method"""
        if len(embeddings) < 3:
            return 1
        
        max_clusters = min(max_clusters, len(embeddings) - 1)
        inertias = []
        
        for k in range(1, max_clusters + 1):
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            kmeans.fit(embeddings)
            inertias.append(kmeans.inertia_)
        
        # Find elbow point
        if len(inertias) > 2:
            # Calculate rate of change
            deltas = np.diff(inertias)
            delta_deltas = np.diff(deltas)
            
            # Find the point where rate of change decreases most
            elbow = np.argmax(delta_deltas) + 2
            return min(elbow, max_clusters)
        
        return 2
    
    def find_outliers(
        self,
        embeddings: np.ndarray,
        contamination: float = 0.1
    ) -> np.ndarray:
        """Find outlier embeddings"""
        from sklearn.ensemble import IsolationForest
        
        detector = IsolationForest(
            contamination=contamination,
            random_state=42
        )
        
        outliers = detector.fit_predict(embeddings)
        return outliers == -1  # True for outliers
    
    def reduce_dimensions(
        self,
        embeddings: np.ndarray,
        n_components: int = 3,
        method: str = "pca"
    ) -> np.ndarray:
        """Reduce embedding dimensions for visualization"""
        if method == "pca":
            reducer = PCA(n_components=n_components)
            reduced = reducer.fit_transform(embeddings)
        elif method == "tsne":
            from sklearn.manifold import TSNE
            reducer = TSNE(n_components=n_components, random_state=42)
            reduced = reducer.fit_transform(embeddings)
        elif method == "umap":
            try:
                import umap
                reducer = umap.UMAP(n_components=n_components, random_state=42)
                reduced = reducer.fit_transform(embeddings)
            except ImportError:
                logger.warning("UMAP not installed, falling back to PCA")
                reducer = PCA(n_components=n_components)
                reduced = reducer.fit_transform(embeddings)
        else:
            raise ValueError(f"Unknown reduction method: {method}")
        
        return reduced
    
    def cleanup(self):
        """Clean up resources"""
        self.indices.clear()
        self.metadata_store.clear()
        self.executor.shutdown(wait=True)
        logger.info("Similarity engine cleaned up")