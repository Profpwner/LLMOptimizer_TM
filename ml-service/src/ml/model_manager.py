"""
Model Manager for ML Service
Handles loading, caching, and management of ML models
"""

import os
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
import torch
import tensorflow as tf
from sentence_transformers import SentenceTransformer
from transformers import (
    AutoTokenizer,
    AutoModel,
    pipeline,
    BertForSequenceClassification,
    GPT2LMHeadModel
)
import joblib
from functools import lru_cache
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class ModelManager:
    """Manages ML models for the optimization engine"""
    
    def __init__(self, model_cache_dir: str = "/app/models"):
        self.model_cache_dir = Path(model_cache_dir)
        self.model_cache_dir.mkdir(parents=True, exist_ok=True)
        self.models: Dict[str, Any] = {}
        self.tokenizers: Dict[str, Any] = {}
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.executor = ThreadPoolExecutor(max_workers=4)
        logger.info(f"Model Manager initialized with device: {self.device}")
        
        # Configure GPU memory if available
        if self.device == "cuda":
            torch.cuda.empty_cache()
            # Limit GPU memory growth for TensorFlow
            gpus = tf.config.experimental.list_physical_devices('GPU')
            if gpus:
                for gpu in gpus:
                    tf.config.experimental.set_memory_growth(gpu, True)
    
    async def initialize_models(self):
        """Initialize all required models"""
        logger.info("Initializing ML models...")
        
        # Load models asynchronously
        tasks = [
            self._load_embedding_model(),
            self._load_nlp_models(),
            self._load_classification_models(),
            self._load_generation_models()
        ]
        
        await asyncio.gather(*tasks)
        logger.info(f"Successfully loaded {len(self.models)} models")
    
    async def _load_embedding_model(self):
        """Load sentence transformer for embeddings"""
        try:
            loop = asyncio.get_event_loop()
            
            # Load multilingual model for better language support
            model_name = "sentence-transformers/all-MiniLM-L6-v2"
            
            def load_model():
                return SentenceTransformer(
                    model_name,
                    device=self.device,
                    cache_folder=str(self.model_cache_dir)
                )
            
            self.models["embeddings"] = await loop.run_in_executor(
                self.executor, load_model
            )
            
            # Also load a multilingual model
            multilingual_model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            
            def load_multilingual():
                return SentenceTransformer(
                    multilingual_model,
                    device=self.device,
                    cache_folder=str(self.model_cache_dir)
                )
            
            self.models["embeddings_multilingual"] = await loop.run_in_executor(
                self.executor, load_multilingual
            )
            
            logger.info("Embedding models loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding models: {e}")
            raise
    
    async def _load_nlp_models(self):
        """Load NLP models for text analysis"""
        try:
            loop = asyncio.get_event_loop()
            
            # Load BERT for text analysis
            bert_model = "bert-base-uncased"
            
            def load_bert():
                tokenizer = AutoTokenizer.from_pretrained(
                    bert_model,
                    cache_dir=str(self.model_cache_dir)
                )
                model = AutoModel.from_pretrained(
                    bert_model,
                    cache_dir=str(self.model_cache_dir)
                ).to(self.device)
                return tokenizer, model
            
            tokenizer, model = await loop.run_in_executor(
                self.executor, load_bert
            )
            
            self.tokenizers["bert"] = tokenizer
            self.models["bert"] = model
            
            # Load sentiment analysis pipeline
            def load_sentiment():
                return pipeline(
                    "sentiment-analysis",
                    model="nlptown/bert-base-multilingual-uncased-sentiment",
                    device=0 if self.device == "cuda" else -1
                )
            
            self.models["sentiment"] = await loop.run_in_executor(
                self.executor, load_sentiment
            )
            
            logger.info("NLP models loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load NLP models: {e}")
            raise
    
    async def _load_classification_models(self):
        """Load classification models"""
        try:
            loop = asyncio.get_event_loop()
            
            # Load readability classifier
            def load_readability():
                return pipeline(
                    "text-classification",
                    model="facebook/bart-large-mnli",
                    device=0 if self.device == "cuda" else -1
                )
            
            self.models["readability_classifier"] = await loop.run_in_executor(
                self.executor, load_readability
            )
            
            # Load topic classifier
            def load_topic():
                return pipeline(
                    "zero-shot-classification",
                    model="facebook/bart-large-mnli",
                    device=0 if self.device == "cuda" else -1
                )
            
            self.models["topic_classifier"] = await loop.run_in_executor(
                self.executor, load_topic
            )
            
            logger.info("Classification models loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load classification models: {e}")
            raise
    
    async def _load_generation_models(self):
        """Load text generation models"""
        try:
            loop = asyncio.get_event_loop()
            
            # Load small GPT-2 for text generation suggestions
            def load_gpt2():
                return pipeline(
                    "text-generation",
                    model="gpt2",
                    device=0 if self.device == "cuda" else -1,
                    max_length=150
                )
            
            self.models["text_generator"] = await loop.run_in_executor(
                self.executor, load_gpt2
            )
            
            # Load summarization model
            def load_summarizer():
                return pipeline(
                    "summarization",
                    model="facebook/bart-large-cnn",
                    device=0 if self.device == "cuda" else -1
                )
            
            self.models["summarizer"] = await loop.run_in_executor(
                self.executor, load_summarizer
            )
            
            logger.info("Generation models loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load generation models: {e}")
            raise
    
    @lru_cache(maxsize=1000)
    def get_embeddings(self, text: str, model_type: str = "default") -> torch.Tensor:
        """Get embeddings for text with caching"""
        model_key = "embeddings" if model_type == "default" else "embeddings_multilingual"
        model = self.models.get(model_key)
        
        if not model:
            raise ValueError(f"Model {model_key} not loaded")
        
        # Generate embeddings
        with torch.no_grad():
            embeddings = model.encode(text, convert_to_tensor=True)
        
        return embeddings
    
    async def get_embeddings_batch(
        self, 
        texts: List[str], 
        model_type: str = "default",
        batch_size: int = 32
    ) -> torch.Tensor:
        """Get embeddings for batch of texts"""
        model_key = "embeddings" if model_type == "default" else "embeddings_multilingual"
        model = self.models.get(model_key)
        
        if not model:
            raise ValueError(f"Model {model_key} not loaded")
        
        loop = asyncio.get_event_loop()
        
        def encode_batch():
            with torch.no_grad():
                return model.encode(
                    texts,
                    convert_to_tensor=True,
                    batch_size=batch_size,
                    show_progress_bar=len(texts) > 100
                )
        
        embeddings = await loop.run_in_executor(self.executor, encode_batch)
        return embeddings
    
    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """Analyze sentiment of text"""
        sentiment_model = self.models.get("sentiment")
        if not sentiment_model:
            raise ValueError("Sentiment model not loaded")
        
        results = sentiment_model(text[:512])  # Limit text length
        
        # Convert to standardized format
        sentiment_map = {
            "1 star": "very_negative",
            "2 stars": "negative",
            "3 stars": "neutral",
            "4 stars": "positive",
            "5 stars": "very_positive"
        }
        
        sentiment_scores = {}
        for result in results:
            label = sentiment_map.get(result["label"], result["label"])
            sentiment_scores[label] = result["score"]
        
        return sentiment_scores
    
    def classify_topics(self, text: str, candidate_labels: List[str]) -> Dict[str, float]:
        """Classify text into topics"""
        classifier = self.models.get("topic_classifier")
        if not classifier:
            raise ValueError("Topic classifier not loaded")
        
        results = classifier(text, candidate_labels)
        
        # Return as dictionary
        topic_scores = {}
        for label, score in zip(results["labels"], results["scores"]):
            topic_scores[label] = score
        
        return topic_scores
    
    def generate_suggestions(self, prompt: str, max_length: int = 100) -> List[str]:
        """Generate text suggestions"""
        generator = self.models.get("text_generator")
        if not generator:
            raise ValueError("Text generator not loaded")
        
        results = generator(
            prompt,
            max_length=max_length,
            num_return_sequences=3,
            temperature=0.8,
            do_sample=True
        )
        
        suggestions = [result["generated_text"] for result in results]
        return suggestions
    
    def summarize_text(self, text: str, max_length: int = 150) -> str:
        """Summarize long text"""
        summarizer = self.models.get("summarizer")
        if not summarizer:
            raise ValueError("Summarizer not loaded")
        
        # Handle long texts by chunking
        max_chunk_length = 1024
        if len(text) > max_chunk_length:
            # Simple chunking - in production, use better sentence boundary detection
            chunks = [text[i:i+max_chunk_length] for i in range(0, len(text), max_chunk_length)]
            summaries = []
            
            for chunk in chunks:
                result = summarizer(chunk, max_length=max_length // len(chunks), min_length=30)
                summaries.append(result[0]["summary_text"])
            
            return " ".join(summaries)
        else:
            result = summarizer(text, max_length=max_length, min_length=30)
            return result[0]["summary_text"]
    
    def cleanup(self):
        """Cleanup models and free memory"""
        logger.info("Cleaning up models...")
        
        # Clear models
        self.models.clear()
        self.tokenizers.clear()
        
        # Clear GPU cache if available
        if self.device == "cuda":
            torch.cuda.empty_cache()
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        logger.info("Model cleanup completed")


# Singleton instance
_model_manager: Optional[ModelManager] = None


async def get_model_manager() -> ModelManager:
    """Get or create model manager instance"""
    global _model_manager
    
    if _model_manager is None:
        _model_manager = ModelManager()
        await _model_manager.initialize_models()
    
    return _model_manager