"""Tests for content deduplication module."""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
from deduplication.deduplicator import ContentDeduplicator, DuplicationPolicy
from deduplication.hashing import HashingStrategies, MinHashLSHIndex
from deduplication.similarity import SimilarityCalculator


class TestContentDeduplicator:
    """Test cases for ContentDeduplicator class."""
    
    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        redis.sadd = AsyncMock()
        redis.smembers = AsyncMock(return_value=set())
        redis.keys = AsyncMock(return_value=[])
        redis.delete = AsyncMock()
        return redis
    
    @pytest.fixture
    def policy(self):
        """Create default deduplication policy."""
        return DuplicationPolicy()
    
    @pytest.fixture
    def deduplicator(self, mock_redis, policy):
        """Create ContentDeduplicator instance."""
        return ContentDeduplicator(redis_client=mock_redis, policy=policy)
    
    @pytest.mark.asyncio
    async def test_check_unique_content(self, deduplicator):
        """Test checking unique content."""
        content = "This is unique content that has never been seen before."
        url = "https://example.com/unique"
        
        result = await deduplicator.check_duplicate(content, url)
        
        assert result['is_duplicate'] is False
        assert result['duplicate_type'] is None
        assert result['action'] == 'accept'
        assert 'fingerprint' in result
        assert deduplicator.stats['unique_content'] == 1
    
    @pytest.mark.asyncio
    async def test_check_exact_duplicate_in_memory(self, deduplicator):
        """Test checking exact duplicate from memory cache."""
        content = "This is test content for exact matching."
        url1 = "https://example.com/page1"
        url2 = "https://example.com/page2"
        
        # Store first content
        result1 = await deduplicator.check_duplicate(content, url1)
        assert result1['is_duplicate'] is False
        
        # Check duplicate
        result2 = await deduplicator.check_duplicate(content, url2)
        
        assert result2['is_duplicate'] is True
        assert result2['duplicate_type'] == 'exact'
        assert result2['original_url'] == url1
        assert result2['similarity_score'] == 1.0
        assert result2['action'] == 'reject'
        assert deduplicator.stats['exact_duplicates'] == 1
    
    @pytest.mark.asyncio
    async def test_check_exact_duplicate_from_redis(self, deduplicator, mock_redis):
        """Test checking exact duplicate from Redis cache."""
        content = "Test content"
        url = "https://example.com/page"
        
        # Mock Redis response
        fingerprint = deduplicator.hashing.content_fingerprint(content)
        mock_redis.get.return_value = json.dumps({
            'url': 'https://example.com/original',
            'timestamp': datetime.utcnow().isoformat()
        })
        
        result = await deduplicator.check_duplicate(content, url)
        
        assert result['is_duplicate'] is True
        assert result['duplicate_type'] == 'exact'
        assert result['original_url'] == 'https://example.com/original'
        mock_redis.get.assert_called_with(f"content_hash:{fingerprint['sha256']}")
    
    @pytest.mark.asyncio
    async def test_check_near_duplicate(self, deduplicator, mock_redis):
        """Test checking near-duplicate content."""
        content1 = "This is a test document with some content. It has multiple sentences."
        content2 = "This is a test document with some content. It has multiple sentences and a bit more."
        url1 = "https://example.com/page1"
        url2 = "https://example.com/page2"
        
        # Store first content
        await deduplicator.check_duplicate(content1, url1)
        
        # Mock LSH query result
        deduplicator.lsh_index.query = Mock(return_value=[url1])
        
        # Mock Redis content retrieval
        mock_redis.get.return_value = json.dumps({
            'url': url1,
            'content_sample': content1,
            'fingerprint': deduplicator.hashing.content_fingerprint(content1),
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Check near duplicate
        result = await deduplicator.check_duplicate(content2, url2)
        
        assert result['is_duplicate'] is True
        assert result['duplicate_type'] == 'near_duplicate'
        assert result['original_url'] == url1
        assert result['similarity_score'] >= 0.8
        assert result['action'] == 'reject'
        assert len(result['similar_urls']) > 0
    
    @pytest.mark.asyncio
    async def test_check_canonical_url_duplicate(self, deduplicator):
        """Test checking canonical URL duplicate."""
        content = "Test content"
        url = "https://example.com/page?utm_source=test"
        canonical_url = "https://example.com/page"
        
        metadata = {'canonical_url': canonical_url}
        
        # Store canonical URL as existing
        deduplicator.content_hashes['some_hash'] = canonical_url
        
        result = await deduplicator.check_duplicate(content, url, metadata)
        
        assert result['is_duplicate'] is True
        assert result['duplicate_type'] == 'canonical'
        assert result['original_url'] == canonical_url
        assert result['action'] == 'redirect'
        assert deduplicator.stats['canonical_redirects'] == 1
    
    @pytest.mark.asyncio
    async def test_check_similar_content(self, deduplicator, mock_redis):
        """Test checking similar but not duplicate content."""
        content = "This is test content about web crawling and data extraction."
        url = "https://example.com/page"
        
        # Mock similar content from Redis
        similar_data = json.dumps({
            'url': 'https://example.com/similar',
            'simhash': 12345678
        })
        mock_redis.smembers.return_value = {similar_data}
        
        # Mock similarity calculation
        deduplicator.hashing.simhash_similarity = Mock(return_value=0.65)
        
        # Set policy to not reject similar content
        deduplicator.policy.reject_near_duplicates = False
        deduplicator.policy.merge_similar_content = True
        
        result = await deduplicator.check_duplicate(content, url)
        
        assert result['is_duplicate'] is False
        assert result['duplicate_type'] == 'similar'
        assert result['action'] == 'merge'
        assert len(result['similar_content']) > 0
        assert deduplicator.stats['similar_content'] == 1
    
    @pytest.mark.asyncio
    async def test_store_content(self, deduplicator, mock_redis):
        """Test content storage for future deduplication."""
        content = "Test content to store"
        url = "https://example.com/page"
        fingerprint = deduplicator.hashing.content_fingerprint(content)
        
        await deduplicator._store_content(url, content, fingerprint)
        
        # Check in-memory storage
        assert deduplicator.content_hashes[fingerprint['sha256']] == url
        
        # Check Redis calls
        assert mock_redis.setex.call_count >= 2  # content_hash and content_data
        assert mock_redis.sadd.called  # simhash bucket
    
    def test_update_canonical_mapping(self, deduplicator):
        """Test updating canonical URL mapping."""
        url = "https://example.com/page?param=1"
        canonical = "https://example.com/page"
        
        deduplicator.update_canonical_mapping(url, canonical)
        
        assert deduplicator.url_canonical_map[url] == canonical
        assert canonical in deduplicator.duplicate_relationships
        assert url in deduplicator.duplicate_relationships[canonical]
    
    def test_should_process_url_https_preference(self, deduplicator):
        """Test URL processing with HTTPS preference."""
        http_url = "http://example.com/page"
        https_url = "https://example.com/page"
        
        # Store HTTPS version
        deduplicator.content_hashes['hash'] = https_url
        
        # Check if HTTP should be processed
        should_process = deduplicator.should_process_url(http_url)
        
        assert should_process is False
    
    def test_get_duplicate_clusters(self, deduplicator):
        """Test getting duplicate content clusters."""
        deduplicator.duplicate_relationships = {
            'https://example.com/canonical1': [
                'https://example.com/dup1',
                'https://example.com/dup2'
            ],
            'https://example.com/canonical2': [
                'https://example.com/dup3'
            ]
        }
        
        clusters = deduplicator.get_duplicate_clusters()
        
        assert len(clusters) == 2
        assert len(clusters['https://example.com/canonical1']) == 2
        assert len(clusters['https://example.com/canonical2']) == 1
    
    def test_get_statistics(self, deduplicator):
        """Test statistics retrieval."""
        deduplicator.stats = {
            'total_checked': 100,
            'exact_duplicates': 20,
            'near_duplicates': 15,
            'similar_content': 10,
            'unique_content': 55,
            'canonical_redirects': 5
        }
        deduplicator.content_hashes = {'hash1': 'url1', 'hash2': 'url2'}
        deduplicator.url_canonical_map = {'url1': 'canonical1'}
        deduplicator.duplicate_relationships = {'canonical1': ['url1', 'url2']}
        
        stats = deduplicator.get_statistics()
        
        assert stats['total_checked'] == 100
        assert stats['duplicate_rate'] == 0.35  # (20 + 15) / 100
        assert stats['unique_rate'] == 0.55
        assert stats['memory_usage']['content_hashes'] == 2
        assert stats['memory_usage']['canonical_mappings'] == 1
        assert stats['memory_usage']['duplicate_clusters'] == 1
    
    @pytest.mark.asyncio
    async def test_clear_cache(self, deduplicator, mock_redis):
        """Test cache clearing."""
        # Add some data
        deduplicator.content_hashes['hash'] = 'url'
        deduplicator.url_canonical_map['url1'] = 'url2'
        deduplicator.duplicate_relationships['url'] = ['url1', 'url2']
        
        # Mock Redis keys
        mock_redis.keys.side_effect = [
            ['content_hash:1', 'content_hash:2'],
            ['content_data:1', 'content_data:2'],
            ['simhash:1', 'simhash:2']
        ]
        
        await deduplicator.clear_cache()
        
        # Check in-memory caches are cleared
        assert len(deduplicator.content_hashes) == 0
        assert len(deduplicator.url_canonical_map) == 0
        assert len(deduplicator.duplicate_relationships) == 0
        
        # Check Redis delete was called
        assert mock_redis.delete.call_count == 3
    
    @pytest.mark.asyncio
    async def test_policy_exact_duplicate_accept(self, deduplicator):
        """Test accepting exact duplicates based on policy."""
        deduplicator.policy.reject_exact_duplicates = False
        
        content = "Duplicate content"
        url1 = "https://example.com/page1"
        url2 = "https://example.com/page2"
        
        await deduplicator.check_duplicate(content, url1)
        result = await deduplicator.check_duplicate(content, url2)
        
        assert result['is_duplicate'] is True
        assert result['duplicate_type'] == 'exact'
        assert result['action'] == 'accept'
    
    @pytest.mark.asyncio
    async def test_policy_near_duplicate_accept(self, deduplicator):
        """Test accepting near duplicates based on policy."""
        deduplicator.policy.reject_near_duplicates = False
        
        content1 = "This is test content"
        content2 = "This is test content with minor changes"
        url1 = "https://example.com/page1"
        url2 = "https://example.com/page2"
        
        await deduplicator.check_duplicate(content1, url1)
        
        # Mock near duplicate detection
        deduplicator.lsh_index.query = Mock(return_value=[url1])
        deduplicator.redis.get = AsyncMock(return_value=json.dumps({
            'url': url1,
            'content_sample': content1
        }))
        
        result = await deduplicator.check_duplicate(content2, url2)
        
        if result['duplicate_type'] == 'near_duplicate':
            assert result['action'] == 'accept'
    
    @pytest.mark.asyncio
    async def test_redis_error_handling(self, deduplicator, mock_redis):
        """Test handling of Redis errors."""
        mock_redis.get.side_effect = Exception("Redis connection error")
        mock_redis.setex.side_effect = Exception("Redis connection error")
        
        content = "Test content"
        url = "https://example.com/page"
        
        # Should not raise exception
        result = await deduplicator.check_duplicate(content, url)
        
        assert result is not None
        assert 'error' not in result