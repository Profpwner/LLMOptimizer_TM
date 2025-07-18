"""Content filtering utilities for extraction."""

import re
from typing import List, Dict, Any, Optional, Set, Tuple
from bs4 import BeautifulSoup, NavigableString, Tag
from collections import Counter
import structlog

logger = structlog.get_logger(__name__)


class ContentFilter:
    """Filter and clean extracted content."""
    
    # Common navigation patterns
    NAV_PATTERNS = [
        r'nav(?:igation)?',
        r'menu',
        r'sidebar',
        r'header',
        r'footer',
        r'breadcrumb',
        r'toolbar'
    ]
    
    # Advertisement patterns
    AD_PATTERNS = [
        r'ad(?:vertisement)?',
        r'sponsor(?:ed)?',
        r'banner',
        r'promo(?:tion)?',
        r'dfp',  # DoubleClick for Publishers
        r'adsense',
        r'outbrain',
        r'taboola',
        r'commercial'
    ]
    
    # Comment section patterns
    COMMENT_PATTERNS = [
        r'comment(?:s)?',
        r'disqus',
        r'discuss(?:ion)?',
        r'reply',
        r'response',
        r'feedback',
        r'user[\-_]?comment'
    ]
    
    # Related content patterns
    RELATED_PATTERNS = [
        r'related',
        r'similar',
        r'recommended',
        r'suggested',
        r'more[\-_]?like',
        r'you[\-_]?may[\-_]?(?:also[\-_]?)?like',
        r'trending',
        r'popular'
    ]
    
    def __init__(self):
        """Initialize content filter."""
        self.filter_stats = {
            'total_filtered': 0,
            'navigation_removed': 0,
            'ads_removed': 0,
            'comments_removed': 0,
            'boilerplate_removed': 0
        }
    
    def extract_main_content(
        self,
        html: str,
        remove_navigation: bool = True,
        remove_ads: bool = True,
        remove_comments: bool = True,
        min_text_length: int = 100
    ) -> Dict[str, Any]:
        """
        Extract main content from HTML.
        
        Args:
            html: HTML content
            remove_navigation: Remove navigation elements
            remove_ads: Remove advertisement elements
            remove_comments: Remove comment sections
            min_text_length: Minimum text length for content blocks
            
        Returns:
            Extracted and filtered content
        """
        self.filter_stats['total_filtered'] += 1
        
        soup = BeautifulSoup(html, 'lxml')
        
        # Remove unwanted elements
        if remove_navigation:
            self._remove_navigation(soup)
        if remove_ads:
            self._remove_advertisements(soup)
        if remove_comments:
            self._remove_comments(soup)
        
        # Remove script and style elements
        for element in soup(['script', 'style', 'noscript']):
            element.decompose()
        
        # Find main content
        main_content = self._find_main_content(soup, min_text_length)
        
        # Extract related content
        related_content = self._extract_related_content(soup)
        
        # Clean and structure the content
        cleaned_content = self._clean_content(main_content)
        
        return {
            'main_content': cleaned_content,
            'related_content': related_content,
            'navigation': self._extract_navigation(soup) if not remove_navigation else [],
            'metadata': self._extract_content_metadata(soup)
        }
    
    def _remove_navigation(self, soup: BeautifulSoup):
        """Remove navigation elements."""
        nav_selector = self._build_selector_from_patterns(self.NAV_PATTERNS)
        
        # Remove by tag
        for nav in soup.find_all(['nav', 'header', 'footer']):
            nav.decompose()
            self.filter_stats['navigation_removed'] += 1
        
        # Remove by class/id patterns
        for element in soup.select(nav_selector):
            element.decompose()
            self.filter_stats['navigation_removed'] += 1
    
    def _remove_advertisements(self, soup: BeautifulSoup):
        """Remove advertisement elements."""
        ad_selector = self._build_selector_from_patterns(self.AD_PATTERNS)
        
        # Remove by patterns
        for element in soup.select(ad_selector):
            element.decompose()
            self.filter_stats['ads_removed'] += 1
        
        # Remove iframes likely to be ads
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src', '').lower()
            if any(pattern in src for pattern in ['doubleclick', 'googlesyndication', 'amazon-adsystem']):
                iframe.decompose()
                self.filter_stats['ads_removed'] += 1
    
    def _remove_comments(self, soup: BeautifulSoup):
        """Remove comment sections."""
        comment_selector = self._build_selector_from_patterns(self.COMMENT_PATTERNS)
        
        for element in soup.select(comment_selector):
            element.decompose()
            self.filter_stats['comments_removed'] += 1
    
    def _build_selector_from_patterns(self, patterns: List[str]) -> str:
        """Build CSS selector from patterns."""
        selectors = []
        for pattern in patterns:
            selectors.extend([
                f'[class*="{pattern}"]',
                f'[id*="{pattern}"]',
                f'[data-*="{pattern}"]'
            ])
        return ', '.join(selectors)
    
    def _find_main_content(self, soup: BeautifulSoup, min_text_length: int) -> Optional[Tag]:
        """Find the main content area using heuristics."""
        # Priority selectors for main content
        main_selectors = [
            'main', 'article', '[role="main"]', '[role="article"]',
            '#main', '#content', '#main-content',
            '.main', '.content', '.article', '.post',
            '[itemtype*="Article"]', '[itemtype*="NewsArticle"]',
            '[itemtype*="BlogPosting"]'
        ]
        
        # Try priority selectors first
        for selector in main_selectors:
            element = soup.select_one(selector)
            if element and len(element.get_text(strip=True)) >= min_text_length:
                return element
        
        # Fallback: find largest content block
        content_blocks = []
        
        for element in soup.find_all(['div', 'section', 'article']):
            text = element.get_text(strip=True)
            if len(text) >= min_text_length:
                # Calculate content density
                link_density = self._calculate_link_density(element)
                if link_density < 0.3:  # Low link density indicates content
                    content_blocks.append((
                        len(text),
                        link_density,
                        element
                    ))
        
        if content_blocks:
            # Sort by text length (descending) and link density (ascending)
            content_blocks.sort(key=lambda x: (-x[0], x[1]))
            return content_blocks[0][2]
        
        return soup.body if soup.body else soup
    
    def _calculate_link_density(self, element: Tag) -> float:
        """Calculate the ratio of link text to total text."""
        total_text = len(element.get_text(strip=True))
        if total_text == 0:
            return 1.0
        
        link_text = sum(len(a.get_text(strip=True)) for a in element.find_all('a'))
        return link_text / total_text
    
    def _extract_related_content(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract related content sections."""
        related_selector = self._build_selector_from_patterns(self.RELATED_PATTERNS)
        related_content = []
        
        for element in soup.select(related_selector):
            # Extract links from related sections
            links = []
            for link in element.find_all('a', href=True):
                links.append({
                    'text': link.get_text(strip=True),
                    'url': link['href']
                })
            
            if links:
                related_content.append({
                    'section': element.get('class', [''])[0] or element.get('id', 'related'),
                    'links': links[:10]  # Limit to 10 related items
                })
        
        return related_content
    
    def _clean_content(self, element: Optional[Tag]) -> Dict[str, Any]:
        """Clean and structure content."""
        if not element:
            return {'text': '', 'html': '', 'structure': {}}
        
        # Remove boilerplate phrases
        self._remove_boilerplate(element)
        
        # Extract structured content
        structure = {
            'headings': self._extract_headings(element),
            'paragraphs': self._extract_paragraphs(element),
            'lists': self._extract_lists(element),
            'images': self._extract_images(element),
            'tables': self._extract_tables(element),
            'quotes': self._extract_quotes(element)
        }
        
        # Get clean text and HTML
        clean_html = str(element)
        clean_text = element.get_text(separator='\n', strip=True)
        
        return {
            'text': clean_text,
            'html': clean_html,
            'structure': structure,
            'word_count': len(clean_text.split()),
            'char_count': len(clean_text)
        }
    
    def _remove_boilerplate(self, element: Tag):
        """Remove common boilerplate phrases."""
        boilerplate_phrases = [
            r'share\s+this\s+article',
            r'follow\s+us\s+on',
            r'subscribe\s+to\s+our\s+newsletter',
            r'sign\s+up\s+for\s+updates',
            r'click\s+here\s+to',
            r'advertisement',
            r'continue\s+reading',
            r'read\s+more'
        ]
        
        for descendant in element.descendants:
            if isinstance(descendant, NavigableString):
                text = str(descendant)
                for phrase in boilerplate_phrases:
                    if re.search(phrase, text, re.IGNORECASE):
                        parent = descendant.parent
                        if parent and parent.name in ['p', 'div', 'span']:
                            parent.decompose()
                            self.filter_stats['boilerplate_removed'] += 1
                            break
    
    def _extract_headings(self, element: Tag) -> List[Dict[str, Any]]:
        """Extract heading structure."""
        headings = []
        for i in range(1, 7):
            for heading in element.find_all(f'h{i}'):
                headings.append({
                    'level': i,
                    'text': heading.get_text(strip=True),
                    'id': heading.get('id')
                })
        return headings
    
    def _extract_paragraphs(self, element: Tag) -> List[str]:
        """Extract paragraph text."""
        paragraphs = []
        for p in element.find_all('p'):
            text = p.get_text(strip=True)
            if len(text) > 20:  # Filter out very short paragraphs
                paragraphs.append(text)
        return paragraphs
    
    def _extract_lists(self, element: Tag) -> List[Dict[str, Any]]:
        """Extract list content."""
        lists = []
        for list_elem in element.find_all(['ul', 'ol']):
            list_data = {
                'type': list_elem.name,
                'items': []
            }
            for li in list_elem.find_all('li', recursive=False):
                list_data['items'].append(li.get_text(strip=True))
            
            if list_data['items']:
                lists.append(list_data)
        
        return lists
    
    def _extract_images(self, element: Tag) -> List[Dict[str, Any]]:
        """Extract image information."""
        images = []
        for img in element.find_all('img'):
            image_data = {
                'src': img.get('src'),
                'alt': img.get('alt', ''),
                'title': img.get('title', ''),
                'width': img.get('width'),
                'height': img.get('height')
            }
            if image_data['src']:
                images.append(image_data)
        return images
    
    def _extract_tables(self, element: Tag) -> List[Dict[str, Any]]:
        """Extract table data."""
        tables = []
        for table in element.find_all('table'):
            table_data = {
                'headers': [],
                'rows': []
            }
            
            # Extract headers
            for th in table.find_all('th'):
                table_data['headers'].append(th.get_text(strip=True))
            
            # Extract rows
            for tr in table.find_all('tr'):
                row = []
                for td in tr.find_all('td'):
                    row.append(td.get_text(strip=True))
                if row:
                    table_data['rows'].append(row)
            
            if table_data['headers'] or table_data['rows']:
                tables.append(table_data)
        
        return tables
    
    def _extract_quotes(self, element: Tag) -> List[Dict[str, Any]]:
        """Extract quotes and citations."""
        quotes = []
        for quote in element.find_all(['blockquote', 'q']):
            quote_data = {
                'text': quote.get_text(strip=True),
                'cite': quote.get('cite')
            }
            
            # Look for citation
            cite = quote.find('cite')
            if cite:
                quote_data['author'] = cite.get_text(strip=True)
            
            quotes.append(quote_data)
        
        return quotes
    
    def _extract_navigation(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract navigation structure."""
        navigation = []
        
        for nav in soup.find_all(['nav', '[role="navigation"]']):
            nav_data = {
                'type': 'navigation',
                'links': []
            }
            
            for link in nav.find_all('a', href=True):
                nav_data['links'].append({
                    'text': link.get_text(strip=True),
                    'url': link['href']
                })
            
            if nav_data['links']:
                navigation.append(nav_data)
        
        return navigation
    
    def _extract_content_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract content-specific metadata."""
        metadata = {
            'has_video': bool(soup.find_all(['video', 'iframe[src*="youtube"]', 'iframe[src*="vimeo"]'])),
            'has_audio': bool(soup.find_all('audio')),
            'has_forms': bool(soup.find_all('form')),
            'has_tables': bool(soup.find_all('table')),
            'has_code': bool(soup.find_all(['code', 'pre'])),
            'link_count': len(soup.find_all('a', href=True)),
            'image_count': len(soup.find_all('img')),
            'heading_count': len(soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']))
        }
        
        return metadata
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get filtering statistics."""
        return self.filter_stats