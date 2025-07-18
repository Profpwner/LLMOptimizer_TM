"""Content hashing strategies for deduplication."""

import hashlib
import xxhash
from typing import Union, List, Set, Tuple, Dict, Any, Optional
import re
from simhash import Simhash
from datasketch import MinHash, MinHashLSH
import structlog

logger = structlog.get_logger(__name__)


class HashingStrategies:
    """Various hashing strategies for content deduplication."""
    
    def __init__(self):
        """Initialize hashing strategies."""
        self.stats = {
            'sha256_computed': 0,
            'simhash_computed': 0,
            'minhash_computed': 0,
            'xxhash_computed': 0
        }
    
    def sha256_hash(self, content: Union[str, bytes]) -> str:
        """
        Compute SHA-256 hash of content.
        
        Args:
            content: Content to hash
            
        Returns:
            Hexadecimal hash string
        """
        if isinstance(content, str):
            content = content.encode('utf-8')
        
        self.stats['sha256_computed'] += 1
        return hashlib.sha256(content).hexdigest()
    
    def xxhash64(self, content: Union[str, bytes]) -> str:
        """
        Compute xxHash64 (faster than SHA-256).
        
        Args:
            content: Content to hash
            
        Returns:
            Hexadecimal hash string
        """
        if isinstance(content, str):
            content = content.encode('utf-8')
        
        self.stats['xxhash_computed'] += 1
        return xxhash.xxh64(content).hexdigest()
    
    def simhash(self, text: str, hash_bits: int = 64) -> int:
        """
        Compute SimHash for near-duplicate detection.
        
        Args:
            text: Text content
            hash_bits: Number of hash bits
            
        Returns:
            SimHash value
        """
        # Preprocess text
        text = self._preprocess_text(text)
        
        # Extract features (words or shingles)
        features = self._extract_features(text)
        
        if not features:
            return 0
        
        self.stats['simhash_computed'] += 1
        return Simhash(features, f=hash_bits).value
    
    def minhash(self, text: str, num_perm: int = 128, seed: int = 1) -> MinHash:
        """
        Compute MinHash for similarity estimation.
        
        Args:
            text: Text content
            num_perm: Number of permutations
            seed: Random seed
            
        Returns:
            MinHash object
        """
        # Preprocess text
        text = self._preprocess_text(text)
        
        # Extract shingles
        shingles = self._extract_shingles(text, k=3)
        
        # Create MinHash
        minhash = MinHash(num_perm=num_perm, seed=seed)
        for shingle in shingles:
            minhash.update(shingle.encode('utf-8'))
        
        self.stats['minhash_computed'] += 1
        return minhash
    
    def content_fingerprint(self, content: str) -> Dict[str, Any]:
        """
        Generate comprehensive content fingerprint.
        
        Args:
            content: Content to fingerprint
            
        Returns:
            Dictionary with various hashes and metadata
        """
        # Normalize content
        normalized = self._normalize_content(content)
        
        fingerprint = {
            'sha256': self.sha256_hash(normalized),
            'xxhash': self.xxhash64(normalized),
            'simhash': self.simhash(normalized),
            'length': len(content),
            'normalized_length': len(normalized),
            'word_count': len(normalized.split()),
            'unique_words': len(set(normalized.lower().split()))
        }
        
        return fingerprint
    
    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for hashing."""
        # Convert to lowercase
        text = text.lower()
        
        # Remove HTML tags if present
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove punctuation
        text = re.sub(r'[^\w\s]', ' ', text)
        
        return text.strip()
    
    def _normalize_content(self, content: str) -> str:
        """Normalize content for consistent hashing."""
        # Remove all whitespace variations
        content = re.sub(r'\s+', ' ', content)
        
        # Convert to lowercase
        content = content.lower()
        
        # Remove common variations
        content = re.sub(r'https?://[^\s]+', 'URL', content)  # URLs
        content = re.sub(r'\d{4}-\d{2}-\d{2}', 'DATE', content)  # Dates
        content = re.sub(r'\d+', 'NUM', content)  # Numbers
        
        return content.strip()
    
    def _extract_features(self, text: str, feature_type: str = 'words') -> List[str]:
        """Extract features for SimHash."""
        if feature_type == 'words':
            # Use words as features
            return text.split()
        elif feature_type == 'shingles':
            # Use character shingles
            return self._extract_shingles(text, k=4)
        else:
            raise ValueError(f"Unknown feature type: {feature_type}")
    
    def _extract_shingles(self, text: str, k: int = 3) -> Set[str]:
        """Extract k-shingles from text."""
        shingles = set()
        
        # Word shingles
        words = text.split()
        for i in range(len(words) - k + 1):
            shingle = ' '.join(words[i:i + k])
            shingles.add(shingle)
        
        return shingles
    
    def hamming_distance(self, hash1: int, hash2: int) -> int:
        """Calculate Hamming distance between two hashes."""
        xor = hash1 ^ hash2
        distance = 0
        
        while xor:
            distance += xor & 1
            xor >>= 1
        
        return distance
    
    def simhash_similarity(self, hash1: int, hash2: int, hash_bits: int = 64) -> float:
        """
        Calculate similarity between two SimHashes.
        
        Args:
            hash1: First SimHash
            hash2: Second SimHash
            hash_bits: Number of hash bits
            
        Returns:
            Similarity score (0-1)
        """
        distance = self.hamming_distance(hash1, hash2)
        similarity = 1 - (distance / hash_bits)
        return similarity
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get hashing statistics."""
        return self.stats


class MinHashLSHIndex:
    """MinHash LSH index for efficient similarity search."""
    
    def __init__(self, threshold: float = 0.8, num_perm: int = 128):
        """
        Initialize LSH index.
        
        Args:
            threshold: Similarity threshold
            num_perm: Number of permutations for MinHash
        """
        self.threshold = threshold
        self.num_perm = num_perm
        self.lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
        self.hashing_strategies = HashingStrategies()
        self.stored_items = {}
    
    def insert(self, key: str, content: str):
        """Insert content into LSH index."""
        minhash = self.hashing_strategies.minhash(content, self.num_perm)
        self.lsh.insert(key, minhash)
        self.stored_items[key] = {
            'content_hash': self.hashing_strategies.sha256_hash(content),
            'length': len(content)
        }
    
    def query(self, content: str) -> List[str]:
        """Query for similar content."""
        minhash = self.hashing_strategies.minhash(content, self.num_perm)
        return self.lsh.query(minhash)
    
    def remove(self, key: str):
        """Remove item from index."""
        if key in self.stored_items:
            self.lsh.remove(key)
            del self.stored_items[key]
    
    def get_item_info(self, key: str) -> Optional[Dict[str, Any]]:
        """Get stored information about an item."""
        return self.stored_items.get(key)