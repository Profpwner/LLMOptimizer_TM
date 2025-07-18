"""Structured data extraction from web pages."""

import json
import re
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import extruct
from rdflib import Graph
import structlog

logger = structlog.get_logger(__name__)


class StructuredDataExtractor:
    """Extract structured data from HTML content."""
    
    def __init__(self):
        """Initialize the structured data extractor."""
        self.extraction_stats = {
            'total_extractions': 0,
            'json_ld_found': 0,
            'microdata_found': 0,
            'rdfa_found': 0,
            'opengraph_found': 0,
            'twitter_found': 0
        }
    
    async def extract_all(
        self,
        html: str,
        url: str,
        extract_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Extract all structured data from HTML.
        
        Args:
            html: HTML content
            url: Page URL for resolving relative URLs
            extract_metadata: Whether to extract additional metadata
            
        Returns:
            Dictionary containing all extracted structured data
        """
        self.extraction_stats['total_extractions'] += 1
        
        result = {
            'url': url,
            'structured_data': {},
            'metadata': {},
            'entities': [],
            'canonical_url': None,
            'alternate_urls': [],
            'social_profiles': []
        }
        
        soup = BeautifulSoup(html, 'lxml')
        
        # Extract using extruct library
        try:
            extracted = extruct.extract(
                html,
                base_url=url,
                syntaxes=['json-ld', 'microdata', 'rdfa', 'opengraph'],
                uniform=True
            )
            
            # Process JSON-LD
            if extracted.get('json-ld'):
                self.extraction_stats['json_ld_found'] += 1
                result['structured_data']['json_ld'] = self._process_json_ld(
                    extracted['json-ld']
                )
            
            # Process Microdata
            if extracted.get('microdata'):
                self.extraction_stats['microdata_found'] += 1
                result['structured_data']['microdata'] = self._process_microdata(
                    extracted['microdata']
                )
            
            # Process RDFa
            if extracted.get('rdfa'):
                self.extraction_stats['rdfa_found'] += 1
                result['structured_data']['rdfa'] = self._process_rdfa(
                    extracted['rdfa']
                )
            
            # Process OpenGraph
            if extracted.get('opengraph'):
                self.extraction_stats['opengraph_found'] += 1
                result['structured_data']['opengraph'] = self._process_opengraph(
                    extracted['opengraph']
                )
            
        except Exception as e:
            logger.error(f"Error extracting structured data: {e}")
        
        # Extract Twitter Card data
        twitter_data = self._extract_twitter_card(soup)
        if twitter_data:
            self.extraction_stats['twitter_found'] += 1
            result['structured_data']['twitter_card'] = twitter_data
        
        # Extract canonical and alternate URLs
        canonical = self._extract_canonical_url(soup, url)
        if canonical:
            result['canonical_url'] = canonical
        
        result['alternate_urls'] = self._extract_alternate_urls(soup, url)
        
        # Extract additional metadata
        if extract_metadata:
            result['metadata'] = await self._extract_metadata(soup, url)
            
            # Extract entities from structured data
            result['entities'] = self._extract_entities(result['structured_data'])
            
            # Extract social profiles
            result['social_profiles'] = self._extract_social_profiles(
                soup, result['structured_data']
            )
        
        return result
    
    def _process_json_ld(self, json_ld_data: List[Dict]) -> List[Dict[str, Any]]:
        """Process JSON-LD structured data."""
        processed = []
        
        for item in json_ld_data:
            if isinstance(item, dict):
                # Flatten @graph if present
                if '@graph' in item:
                    graph_items = item['@graph']
                    if isinstance(graph_items, list):
                        processed.extend(self._process_json_ld(graph_items))
                else:
                    processed_item = self._normalize_json_ld_item(item)
                    if processed_item:
                        processed.append(processed_item)
        
        return processed
    
    def _normalize_json_ld_item(self, item: Dict) -> Optional[Dict[str, Any]]:
        """Normalize a single JSON-LD item."""
        if not isinstance(item, dict):
            return None
        
        normalized = {}
        
        # Extract type
        item_type = item.get('@type', item.get('type'))
        if item_type:
            normalized['type'] = item_type
        
        # Extract common properties
        for key, value in item.items():
            if key.startswith('@'):
                continue
            
            # Handle nested structures
            if isinstance(value, dict) and '@value' in value:
                normalized[key] = value['@value']
            else:
                normalized[key] = value
        
        return normalized if normalized else None
    
    def _process_microdata(self, microdata: List[Dict]) -> List[Dict[str, Any]]:
        """Process Microdata structured data."""
        processed = []
        
        for item in microdata:
            if isinstance(item, dict):
                processed_item = {
                    'type': item.get('type', ['Unknown'])[0] if item.get('type') else 'Unknown',
                    'properties': item.get('properties', {})
                }
                
                # Handle nested items
                if 'children' in item:
                    processed_item['children'] = self._process_microdata(item['children'])
                
                processed.append(processed_item)
        
        return processed
    
    def _process_rdfa(self, rdfa_data: List[Dict]) -> List[Dict[str, Any]]:
        """Process RDFa structured data."""
        processed = []
        
        try:
            # Create RDF graph
            g = Graph()
            
            for item in rdfa_data:
                if isinstance(item, dict):
                    # Extract subject, predicate, object triples
                    subject = item.get('@id', item.get('subject'))
                    
                    if subject:
                        properties = {}
                        for key, value in item.items():
                            if key not in ['@id', '@type', 'subject']:
                                properties[key] = value
                        
                        processed.append({
                            'subject': subject,
                            'type': item.get('@type', item.get('type')),
                            'properties': properties
                        })
        
        except Exception as e:
            logger.warning(f"Error processing RDFa: {e}")
        
        return processed
    
    def _process_opengraph(self, og_data: List[Dict]) -> Dict[str, Any]:
        """Process OpenGraph data."""
        og_processed = {}
        
        for item in og_data:
            if isinstance(item, dict):
                for key, value in item.items():
                    # Remove 'og:' prefix
                    clean_key = key.replace('og:', '') if key.startswith('og:') else key
                    og_processed[clean_key] = value
        
        return og_processed
    
    def _extract_twitter_card(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract Twitter Card metadata."""
        twitter_data = {}
        
        for meta in soup.find_all('meta'):
            name = meta.get('name', '')
            property_attr = meta.get('property', '')
            content = meta.get('content')
            
            if content and (name.startswith('twitter:') or property_attr.startswith('twitter:')):
                key = name.replace('twitter:', '') or property_attr.replace('twitter:', '')
                twitter_data[key] = content
        
        return twitter_data if twitter_data else None
    
    def _extract_canonical_url(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Extract canonical URL."""
        canonical = soup.find('link', rel='canonical')
        if canonical and canonical.get('href'):
            return urljoin(base_url, canonical['href'])
        
        # Check OpenGraph URL as fallback
        og_url = soup.find('meta', property='og:url')
        if og_url and og_url.get('content'):
            return urljoin(base_url, og_url['content'])
        
        return None
    
    def _extract_alternate_urls(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Extract alternate URLs (language versions, mobile, etc.)."""
        alternates = []
        
        for link in soup.find_all('link', rel='alternate'):
            href = link.get('href')
            if href:
                alternate = {
                    'url': urljoin(base_url, href),
                    'hreflang': link.get('hreflang'),
                    'type': link.get('type'),
                    'title': link.get('title')
                }
                alternates.append({k: v for k, v in alternate.items() if v})
        
        return alternates
    
    async def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Extract additional metadata from the page."""
        metadata = {
            'title': None,
            'description': None,
            'keywords': [],
            'author': None,
            'publisher': None,
            'date_published': None,
            'date_modified': None,
            'language': None,
            'robots': None,
            'viewport': None,
            'favicon': None,
            'rss_feeds': [],
            'site_name': None
        }
        
        # Title
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.get_text(strip=True)
        
        # Meta tags
        for meta in soup.find_all('meta'):
            name = meta.get('name', '').lower()
            property_attr = meta.get('property', '').lower()
            content = meta.get('content', '')
            
            if not content:
                continue
            
            # Description
            if name == 'description' or property_attr == 'og:description':
                metadata['description'] = content
            
            # Keywords
            elif name == 'keywords':
                metadata['keywords'] = [k.strip() for k in content.split(',') if k.strip()]
            
            # Author
            elif name == 'author' or property_attr == 'article:author':
                metadata['author'] = content
            
            # Publisher
            elif property_attr == 'article:publisher':
                metadata['publisher'] = content
            
            # Dates
            elif property_attr == 'article:published_time':
                metadata['date_published'] = content
            elif property_attr == 'article:modified_time':
                metadata['date_modified'] = content
            
            # Language
            elif name == 'language' or property_attr == 'og:locale':
                metadata['language'] = content
            
            # Robots
            elif name == 'robots':
                metadata['robots'] = content
            
            # Viewport
            elif name == 'viewport':
                metadata['viewport'] = content
            
            # Site name
            elif property_attr == 'og:site_name':
                metadata['site_name'] = content
        
        # Language from HTML tag
        if not metadata['language']:
            html_tag = soup.find('html')
            if html_tag:
                metadata['language'] = html_tag.get('lang')
        
        # Favicon
        favicon = soup.find('link', rel=lambda x: x and 'icon' in x)
        if favicon and favicon.get('href'):
            metadata['favicon'] = urljoin(url, favicon['href'])
        
        # RSS feeds
        rss_feeds = soup.find_all('link', type='application/rss+xml')
        for feed in rss_feeds:
            href = feed.get('href')
            if href:
                metadata['rss_feeds'].append({
                    'url': urljoin(url, href),
                    'title': feed.get('title', 'RSS Feed')
                })
        
        return metadata
    
    def _extract_entities(self, structured_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract entities from structured data."""
        entities = []
        
        # Extract from JSON-LD
        if 'json_ld' in structured_data:
            for item in structured_data['json_ld']:
                entity = self._extract_entity_from_json_ld(item)
                if entity:
                    entities.append(entity)
        
        # Extract from Microdata
        if 'microdata' in structured_data:
            for item in structured_data['microdata']:
                entity = self._extract_entity_from_microdata(item)
                if entity:
                    entities.append(entity)
        
        return entities
    
    def _extract_entity_from_json_ld(self, item: Dict) -> Optional[Dict[str, Any]]:
        """Extract entity information from JSON-LD item."""
        entity_type = item.get('type', '')
        
        # Map of schema.org types to entity categories
        entity_mapping = {
            'Person': 'person',
            'Organization': 'organization',
            'LocalBusiness': 'business',
            'Product': 'product',
            'Event': 'event',
            'Article': 'article',
            'VideoObject': 'video',
            'ImageObject': 'image',
            'Recipe': 'recipe',
            'Course': 'course'
        }
        
        for schema_type, entity_category in entity_mapping.items():
            if schema_type in str(entity_type):
                return {
                    'category': entity_category,
                    'type': entity_type,
                    'name': item.get('name'),
                    'description': item.get('description'),
                    'url': item.get('url'),
                    'properties': {k: v for k, v in item.items() 
                                 if k not in ['type', 'name', 'description', 'url']}
                }
        
        return None
    
    def _extract_entity_from_microdata(self, item: Dict) -> Optional[Dict[str, Any]]:
        """Extract entity information from Microdata item."""
        properties = item.get('properties', {})
        
        return {
            'category': 'microdata',
            'type': item.get('type'),
            'name': properties.get('name'),
            'description': properties.get('description'),
            'url': properties.get('url'),
            'properties': properties
        }
    
    def _extract_social_profiles(
        self,
        soup: BeautifulSoup,
        structured_data: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Extract social media profile links."""
        social_profiles = []
        social_patterns = {
            'facebook': r'facebook\.com/[\w\-\.]+',
            'twitter': r'twitter\.com/[\w\-\.]+',
            'instagram': r'instagram\.com/[\w\-\.]+',
            'linkedin': r'linkedin\.com/(?:company|in)/[\w\-\.]+',
            'youtube': r'youtube\.com/(?:user|channel)/[\w\-\.]+',
            'github': r'github\.com/[\w\-\.]+',
            'pinterest': r'pinterest\.com/[\w\-\.]+',
            'tiktok': r'tiktok\.com/@[\w\-\.]+'
        }
        
        # Check all links
        for link in soup.find_all('a', href=True):
            href = link['href']
            for platform, pattern in social_patterns.items():
                if re.search(pattern, href, re.IGNORECASE):
                    social_profiles.append({
                        'platform': platform,
                        'url': href,
                        'text': link.get_text(strip=True)
                    })
                    break
        
        # Check structured data
        if 'json_ld' in structured_data:
            for item in structured_data['json_ld']:
                same_as = item.get('sameAs', [])
                if isinstance(same_as, list):
                    for url in same_as:
                        for platform, pattern in social_patterns.items():
                            if re.search(pattern, url, re.IGNORECASE):
                                social_profiles.append({
                                    'platform': platform,
                                    'url': url,
                                    'source': 'structured_data'
                                })
                                break
        
        # Remove duplicates
        seen = set()
        unique_profiles = []
        for profile in social_profiles:
            key = (profile['platform'], profile['url'])
            if key not in seen:
                seen.add(key)
                unique_profiles.append(profile)
        
        return unique_profiles
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get extraction statistics."""
        return {
            **self.extraction_stats,
            'success_rate': {
                'json_ld': self.extraction_stats['json_ld_found'] / max(self.extraction_stats['total_extractions'], 1),
                'microdata': self.extraction_stats['microdata_found'] / max(self.extraction_stats['total_extractions'], 1),
                'rdfa': self.extraction_stats['rdfa_found'] / max(self.extraction_stats['total_extractions'], 1),
                'opengraph': self.extraction_stats['opengraph_found'] / max(self.extraction_stats['total_extractions'], 1),
                'twitter': self.extraction_stats['twitter_found'] / max(self.extraction_stats['total_extractions'], 1)
            }
        }