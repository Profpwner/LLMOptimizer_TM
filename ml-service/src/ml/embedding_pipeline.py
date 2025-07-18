"""
Semantic Embedding Pipeline
Handles text processing and embedding generation with multi-language support
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import torch
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from datetime import datetime
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
import spacy
from langchain.text_splitter import RecursiveCharacterTextSplitter
import tiktoken

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingConfig:
    """Configuration for embedding generation"""
    model_type: str = "default"  # default or multilingual
    chunk_size: int = 512
    chunk_overlap: int = 50
    batch_size: int = 32
    normalize: bool = True
    cache_embeddings: bool = True


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata"""
    text: str
    start_index: int
    end_index: int
    chunk_index: int
    metadata: Dict[str, Any]
    embedding: Optional[np.ndarray] = None


class EmbeddingPipeline:
    """Pipeline for generating semantic embeddings"""
    
    def __init__(self, model_manager, redis_client=None):
        self.model_manager = model_manager
        self.redis_client = redis_client
        self.spacy_models = {}
        self._initialize_nlp_resources()
        
        # Text splitter for chunking
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=512,
            chunk_overlap=50,
            length_function=self._tiktoken_len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        # Cache for embeddings
        self._embedding_cache = {}
        
    def _initialize_nlp_resources(self):
        """Initialize NLP resources"""
        # Download NLTK data if not present
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')
        
        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('stopwords')
        
        # Load spaCy models
        try:
            self.spacy_models["en"] = spacy.load("en_core_web_sm")
        except:
            logger.warning("English spaCy model not found. Install with: python -m spacy download en_core_web_sm")
            
        try:
            self.spacy_models["multi"] = spacy.load("xx_ent_wiki_sm")
        except:
            logger.warning("Multilingual spaCy model not found. Install with: python -m spacy download xx_ent_wiki_sm")
    
    def _tiktoken_len(self, text: str) -> int:
        """Calculate token length using tiktoken"""
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except:
            # Fallback to simple word count
            return len(text.split())
    
    def _get_cache_key(self, text: str, config: EmbeddingConfig) -> str:
        """Generate cache key for text embedding"""
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        config_str = f"{config.model_type}_{config.normalize}"
        return f"embedding:{text_hash}:{config_str}"
    
    async def _get_cached_embedding(self, cache_key: str) -> Optional[np.ndarray]:
        """Get embedding from cache"""
        if self.redis_client:
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    return np.frombuffer(cached, dtype=np.float32)
            except Exception as e:
                logger.warning(f"Cache retrieval failed: {e}")
        
        return self._embedding_cache.get(cache_key)
    
    async def _cache_embedding(self, cache_key: str, embedding: np.ndarray):
        """Cache embedding"""
        self._embedding_cache[cache_key] = embedding
        
        if self.redis_client:
            try:
                await self.redis_client.setex(
                    cache_key,
                    3600 * 24,  # 24 hour cache
                    embedding.tobytes()
                )
            except Exception as e:
                logger.warning(f"Cache storage failed: {e}")
    
    def preprocess_text(self, text: str, language: str = "en") -> str:
        """Preprocess text for embedding generation"""
        # Basic cleaning
        text = text.strip()
        text = " ".join(text.split())  # Normalize whitespace
        
        # Use spaCy for advanced preprocessing if available
        if language in self.spacy_models:
            doc = self.spacy_models[language](text)
            # Remove stop words and punctuation for embedding
            tokens = [token.text.lower() for token in doc 
                     if not token.is_stop and not token.is_punct and token.text.strip()]
            return " ".join(tokens)
        
        return text
    
    def chunk_text(self, text: str, config: EmbeddingConfig) -> List[TextChunk]:
        """Split text into chunks for embedding"""
        # Update text splitter config
        self.text_splitter.chunk_size = config.chunk_size
        self.text_splitter.chunk_overlap = config.chunk_overlap
        
        # Split text
        chunks = self.text_splitter.split_text(text)
        
        # Create TextChunk objects
        text_chunks = []
        current_index = 0
        
        for i, chunk in enumerate(chunks):
            start_index = text.find(chunk, current_index)
            end_index = start_index + len(chunk)
            
            text_chunk = TextChunk(
                text=chunk,
                start_index=start_index,
                end_index=end_index,
                chunk_index=i,
                metadata={
                    "chunk_size": len(chunk),
                    "token_count": self._tiktoken_len(chunk)
                }
            )
            
            text_chunks.append(text_chunk)
            current_index = end_index
        
        return text_chunks
    
    async def generate_embeddings(
        self,
        texts: List[str],
        config: Optional[EmbeddingConfig] = None
    ) -> List[np.ndarray]:
        """Generate embeddings for multiple texts"""
        if config is None:
            config = EmbeddingConfig()
        
        embeddings = []
        uncached_texts = []
        uncached_indices = []
        
        # Check cache first
        for i, text in enumerate(texts):
            if config.cache_embeddings:
                cache_key = self._get_cache_key(text, config)
                cached_embedding = await self._get_cached_embedding(cache_key)
                
                if cached_embedding is not None:
                    embeddings.append(cached_embedding)
                else:
                    embeddings.append(None)
                    uncached_texts.append(text)
                    uncached_indices.append(i)
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)
                embeddings.append(None)
        
        # Generate embeddings for uncached texts
        if uncached_texts:
            # Preprocess texts
            processed_texts = [self.preprocess_text(text) for text in uncached_texts]
            
            # Generate embeddings in batches
            batch_embeddings = await self.model_manager.get_embeddings_batch(
                processed_texts,
                model_type=config.model_type,
                batch_size=config.batch_size
            )
            
            # Convert to numpy and normalize if needed
            batch_embeddings = batch_embeddings.cpu().numpy()
            
            if config.normalize:
                # L2 normalization
                norms = np.linalg.norm(batch_embeddings, axis=1, keepdims=True)
                batch_embeddings = batch_embeddings / (norms + 1e-8)
            
            # Cache and update results
            for idx, (orig_idx, text) in enumerate(zip(uncached_indices, uncached_texts)):
                embedding = batch_embeddings[idx]
                embeddings[orig_idx] = embedding
                
                if config.cache_embeddings:
                    cache_key = self._get_cache_key(text, config)
                    await self._cache_embedding(cache_key, embedding)
        
        return embeddings
    
    async def generate_document_embedding(
        self,
        text: str,
        config: Optional[EmbeddingConfig] = None
    ) -> Tuple[np.ndarray, List[TextChunk]]:
        """Generate embedding for a document with chunking"""
        if config is None:
            config = EmbeddingConfig()
        
        # Chunk the text
        chunks = self.chunk_text(text, config)
        
        # Generate embeddings for chunks
        chunk_texts = [chunk.text for chunk in chunks]
        chunk_embeddings = await self.generate_embeddings(chunk_texts, config)
        
        # Store embeddings in chunks
        for chunk, embedding in zip(chunks, chunk_embeddings):
            chunk.embedding = embedding
        
        # Compute document-level embedding (weighted average)
        weights = np.array([len(chunk.text) for chunk in chunks])
        weights = weights / weights.sum()
        
        document_embedding = np.average(
            chunk_embeddings,
            axis=0,
            weights=weights
        )
        
        if config.normalize:
            document_embedding = document_embedding / (np.linalg.norm(document_embedding) + 1e-8)
        
        return document_embedding, chunks
    
    async def generate_multilingual_embeddings(
        self,
        texts: Dict[str, str],
        config: Optional[EmbeddingConfig] = None
    ) -> Dict[str, np.ndarray]:
        """Generate embeddings for texts in multiple languages"""
        if config is None:
            config = EmbeddingConfig(model_type="multilingual")
        
        results = {}
        
        # Process each language
        for language, text in texts.items():
            embedding = await self.generate_embeddings([text], config)
            results[language] = embedding[0]
        
        return results
    
    def compute_semantic_density(self, chunks: List[TextChunk]) -> float:
        """Compute semantic density of text chunks"""
        if len(chunks) < 2:
            return 1.0
        
        embeddings = [chunk.embedding for chunk in chunks if chunk.embedding is not None]
        if len(embeddings) < 2:
            return 1.0
        
        # Compute pairwise similarities
        similarities = []
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                sim = np.dot(embeddings[i], embeddings[j])
                similarities.append(sim)
        
        # Return average similarity as density measure
        return np.mean(similarities)
    
    def identify_semantic_clusters(
        self,
        embeddings: List[np.ndarray],
        n_clusters: Optional[int] = None
    ) -> Tuple[List[int], List[np.ndarray]]:
        """Identify semantic clusters in embeddings"""
        from sklearn.cluster import KMeans, DBSCAN
        
        embeddings_array = np.array(embeddings)
        
        if n_clusters is None:
            # Use DBSCAN for automatic cluster detection
            clustering = DBSCAN(eps=0.3, min_samples=2, metric='cosine')
            labels = clustering.fit_predict(embeddings_array)
            
            # Get cluster centers
            unique_labels = set(labels) - {-1}  # Remove noise label
            centers = []
            for label in unique_labels:
                mask = labels == label
                center = embeddings_array[mask].mean(axis=0)
                centers.append(center)
        else:
            # Use KMeans with specified clusters
            kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            labels = kmeans.fit_predict(embeddings_array)
            centers = kmeans.cluster_centers_
        
        return labels.tolist(), centers
    
    async def analyze_semantic_coverage(
        self,
        text: str,
        reference_topics: List[str],
        config: Optional[EmbeddingConfig] = None
    ) -> Dict[str, float]:
        """Analyze how well text covers reference topics"""
        if config is None:
            config = EmbeddingConfig()
        
        # Generate embeddings
        text_embedding = (await self.generate_embeddings([text], config))[0]
        topic_embeddings = await self.generate_embeddings(reference_topics, config)
        
        # Calculate coverage scores
        coverage_scores = {}
        for topic, topic_embedding in zip(reference_topics, topic_embeddings):
            similarity = np.dot(text_embedding, topic_embedding)
            coverage_scores[topic] = float(similarity)
        
        return coverage_scores
    
    def export_embeddings(self, chunks: List[TextChunk], format: str = "json") -> str:
        """Export embeddings in various formats"""
        if format == "json":
            data = []
            for chunk in chunks:
                chunk_data = {
                    "text": chunk.text,
                    "start_index": chunk.start_index,
                    "end_index": chunk.end_index,
                    "chunk_index": chunk.chunk_index,
                    "metadata": chunk.metadata,
                    "embedding": chunk.embedding.tolist() if chunk.embedding is not None else None
                }
                data.append(chunk_data)
            
            return json.dumps(data, indent=2)
        
        elif format == "numpy":
            embeddings = [chunk.embedding for chunk in chunks if chunk.embedding is not None]
            return np.array(embeddings)
        
        else:
            raise ValueError(f"Unsupported export format: {format}")