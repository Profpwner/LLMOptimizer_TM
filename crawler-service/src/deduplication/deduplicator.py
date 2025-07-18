"""Main content deduplication service."""

import asyncio
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass
from datetime import datetime
import json
from urllib.parse import urlparse, urljoin

import structlog
from redis import asyncio as aioredis

from .hashing import HashingStrategies, MinHashLSHIndex
from .similarity import SimilarityCalculator

logger = structlog.get_logger(__name__)


@dataclass
class DuplicationPolicy:
    """Policy for handling duplicate content."""
    
    # Similarity thresholds
    exact_match_threshold: float = 0.95
    near_duplicate_threshold: float = 0.80
    similar_content_threshold: float = 0.60
    
    # Actions
    reject_exact_duplicates: bool = True
    reject_near_duplicates: bool = True
    merge_similar_content: bool = False
    
    # Canonical URL handling
    prefer_canonical: bool = True
    follow_canonical_redirects: bool = True
    
    # Content priority
    prefer_newer: bool = False
    prefer_longer: bool = True
    prefer_https: bool = True
    
    # Storage
    store_duplicates: bool = False
    store_relationships: bool = True


class ContentDeduplicator:
    """Handles content deduplication with multiple strategies."""
    
    def __init__(
        self,
        redis_client: Optional[aioredis.Redis] = None,
        policy: Optional[DuplicationPolicy] = None
    ):
        """
        Initialize content deduplicator.
        
        Args:
            redis_client: Redis client for caching
            policy: Deduplication policy
        """
        self.redis = redis_client
        self.policy = policy or DuplicationPolicy()
        
        self.hashing = HashingStrategies()
        self.similarity = SimilarityCalculator()
        self.lsh_index = MinHashLSHIndex(
            threshold=self.policy.near_duplicate_threshold
        )
        
        # Statistics
        self.stats = {
            'total_checked': 0,
            'exact_duplicates': 0,
            'near_duplicates': 0,
            'similar_content': 0,
            'unique_content': 0,
            'canonical_redirects': 0
        }
        
        # In-memory caches
        self.content_hashes: Dict[str, str] = {}
        self.url_canonical_map: Dict[str, str] = {}
        self.duplicate_relationships: Dict[str, List[str]] = {}
    
    async def check_duplicate(
        self,
        content: str,
        url: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Check if content is duplicate.
        
        Args:
            content: Content to check
            url: Content URL
            metadata: Additional metadata
            
        Returns:
            Duplication check results
        """
        self.stats['total_checked'] += 1
        
        # Generate content fingerprint
        fingerprint = self.hashing.content_fingerprint(content)
        
        # Check for exact duplicate
        exact_match = await self._check_exact_duplicate(fingerprint['sha256'])
        if exact_match:
            self.stats['exact_duplicates'] += 1
            return {
                'is_duplicate': True,
                'duplicate_type': 'exact',
                'original_url': exact_match['url'],
                'similarity_score': 1.0,
                'action': 'reject' if self.policy.reject_exact_duplicates else 'accept',
                'fingerprint': fingerprint
            }
        
        # Check for near-duplicates using LSH
        near_duplicates = await self._check_near_duplicates(content, url)
        if near_duplicates:
            best_match = near_duplicates[0]
            self.stats['near_duplicates'] += 1
            
            return {
                'is_duplicate': True,
                'duplicate_type': 'near_duplicate',
                'original_url': best_match['url'],
                'similarity_score': best_match['similarity'],
                'action': 'reject' if self.policy.reject_near_duplicates else 'accept',
                'fingerprint': fingerprint,
                'similar_urls': [match['url'] for match in near_duplicates]
            }
        
        # Check canonical URL
        canonical_result = await self._check_canonical_url(url, metadata)
        if canonical_result and canonical_result['is_canonical_duplicate']:
            self.stats['canonical_redirects'] += 1
            return canonical_result
        
        # Check for similar content
        similar_content = await self._find_similar_content(content, fingerprint)
        if similar_content:
            self.stats['similar_content'] += 1
            return {
                'is_duplicate': False,
                'duplicate_type': 'similar',
                'similar_content': similar_content,
                'action': 'merge' if self.policy.merge_similar_content else 'accept',
                'fingerprint': fingerprint
            }
        
        # Unique content
        self.stats['unique_content'] += 1
        
        # Store content for future comparisons
        await self._store_content(url, content, fingerprint)
        
        return {
            'is_duplicate': False,
            'duplicate_type': None,
            'action': 'accept',
            'fingerprint': fingerprint
        }
    
    async def _check_exact_duplicate(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """Check for exact content match."""
        # Check in-memory cache
        if content_hash in self.content_hashes:
            return {'url': self.content_hashes[content_hash]}
        
        # Check Redis if available
        if self.redis:
            try:
                cached = await self.redis.get(f"content_hash:{content_hash}")
                if cached:
                    data = json.loads(cached)
                    self.content_hashes[content_hash] = data['url']
                    return data
            except Exception as e:
                logger.error(f"Redis error checking exact duplicate: {e}")
        
        return None
    
    async def _check_near_duplicates(
        self,
        content: str,
        url: str
    ) -> List[Dict[str, Any]]:
        """Check for near-duplicate content using LSH."""
        # Query LSH index
        similar_keys = self.lsh_index.query(content)
        
        if not similar_keys:
            return []
        
        # Calculate detailed similarity for each match
        matches = []
        for key in similar_keys:
            # Get stored content info
            if self.redis:
                try:
                    stored_data = await self.redis.get(f"content_data:{key}")
                    if stored_data:
                        data = json.loads(stored_data)
                        similarity = self.similarity.content_similarity_score(
                            content,
                            data['content_sample']
                        )
                        
                        if similarity['weighted_score'] >= self.policy.near_duplicate_threshold:
                            matches.append({
                                'url': data['url'],
                                'similarity': similarity['weighted_score'],
                                'scores': similarity['scores']
                            })
                except Exception as e:
                    logger.error(f"Error retrieving near-duplicate data: {e}")
        
        # Sort by similarity score
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        
        return matches
    
    async def _check_canonical_url(
        self,
        url: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Check if URL has a canonical version."""
        if not self.policy.prefer_canonical:
            return None
        
        canonical_url = None
        
        # Check metadata for canonical URL
        if metadata and 'canonical_url' in metadata:
            canonical_url = metadata['canonical_url']
        
        # Check URL canonical map
        elif url in self.url_canonical_map:
            canonical_url = self.url_canonical_map[url]
        
        if canonical_url and canonical_url != url:
            # Check if we already have the canonical content
            if canonical_url in self.content_hashes.values():
                return {
                    'is_duplicate': True,
                    'duplicate_type': 'canonical',
                    'original_url': canonical_url,
                    'similarity_score': 1.0,
                    'action': 'redirect' if self.policy.follow_canonical_redirects else 'reject',
                    'is_canonical_duplicate': True
                }
        
        return None
    
    async def _find_similar_content(
        self,
        content: str,
        fingerprint: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Find similar but not duplicate content."""
        similar_content = []
        
        # Use SimHash for initial filtering
        simhash_value = fingerprint['simhash']
        
        if self.redis:
            try:
                # Get SimHashes within threshold
                simhash_key = f"simhash:{simhash_value >> 32}"  # Bucket by high bits
                similar_hashes = await self.redis.smembers(simhash_key)
                
                for hash_data in similar_hashes:
                    data = json.loads(hash_data)
                    stored_simhash = data['simhash']
                    
                    # Calculate SimHash similarity
                    sim_similarity = self.hashing.simhash_similarity(
                        simhash_value,
                        stored_simhash
                    )
                    
                    if sim_similarity >= self.policy.similar_content_threshold:
                        similar_content.append({
                            'url': data['url'],
                            'similarity': sim_similarity,
                            'type': 'simhash'
                        })
                
            except Exception as e:
                logger.error(f"Error finding similar content: {e}")
        
        return similar_content[:10]  # Limit results
    
    async def _store_content(
        self,
        url: str,
        content: str,
        fingerprint: Dict[str, Any]
    ):
        """Store content for future deduplication."""
        # Store in memory
        self.content_hashes[fingerprint['sha256']] = url
        
        # Store in LSH index
        self.lsh_index.insert(url, content)
        
        # Store in Redis if available
        if self.redis:
            try:
                # Store content hash
                await self.redis.setex(
                    f"content_hash:{fingerprint['sha256']}",
                    86400,  # 24 hours TTL
                    json.dumps({
                        'url': url,
                        'timestamp': datetime.utcnow().isoformat()
                    })
                )
                
                # Store content sample for similarity checking
                content_sample = content[:5000]  # Store first 5KB
                await self.redis.setex(
                    f"content_data:{url}",
                    86400,
                    json.dumps({
                        'url': url,
                        'content_sample': content_sample,
                        'fingerprint': fingerprint,
                        'timestamp': datetime.utcnow().isoformat()
                    })
                )
                
                # Store SimHash in bucket
                simhash_bucket = f"simhash:{fingerprint['simhash'] >> 32}"
                await self.redis.sadd(
                    simhash_bucket,
                    json.dumps({
                        'url': url,
                        'simhash': fingerprint['simhash']
                    })
                )
                
            except Exception as e:
                logger.error(f"Error storing content in Redis: {e}")
    
    def update_canonical_mapping(self, url: str, canonical_url: str):
        """Update canonical URL mapping."""
        self.url_canonical_map[url] = canonical_url
        
        if self.policy.store_relationships:
            if canonical_url not in self.duplicate_relationships:
                self.duplicate_relationships[canonical_url] = []
            self.duplicate_relationships[canonical_url].append(url)
    
    def get_duplicate_clusters(self) -> Dict[str, List[str]]:
        """Get clusters of duplicate content."""
        return self.duplicate_relationships.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get deduplication statistics."""
        total = max(self.stats['total_checked'], 1)
        
        return {
            **self.stats,
            'duplicate_rate': (self.stats['exact_duplicates'] + self.stats['near_duplicates']) / total,
            'unique_rate': self.stats['unique_content'] / total,
            'memory_usage': {
                'content_hashes': len(self.content_hashes),
                'canonical_mappings': len(self.url_canonical_map),
                'duplicate_clusters': len(self.duplicate_relationships)
            }
        }
    
    async def clear_cache(self):
        """Clear deduplication caches."""
        self.content_hashes.clear()
        self.url_canonical_map.clear()
        self.duplicate_relationships.clear()
        
        if self.redis:
            try:
                # Clear Redis keys (be careful in production)
                keys = await self.redis.keys("content_hash:*")
                if keys:
                    await self.redis.delete(*keys)
                
                keys = await self.redis.keys("content_data:*")
                if keys:
                    await self.redis.delete(*keys)
                
                keys = await self.redis.keys("simhash:*")
                if keys:
                    await self.redis.delete(*keys)
                    
            except Exception as e:
                logger.error(f"Error clearing Redis cache: {e}")
    
    def should_process_url(self, url: str) -> bool:
        """Determine if URL should be processed based on policy."""
        parsed = urlparse(url)
        
        # Prefer HTTPS
        if self.policy.prefer_https and parsed.scheme == 'http':
            https_url = url.replace('http://', 'https://', 1)
            if https_url in self.content_hashes.values():
                return False
        
        return True