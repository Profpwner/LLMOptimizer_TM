"""Content analysis and structure detection module."""

import re
from typing import Dict, List, Optional, Any, Tuple
from collections import Counter
import statistics
from bs4 import BeautifulSoup
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
import structlog

logger = structlog.get_logger(__name__)


class ContentAnalyzer:
    """Analyze content structure, quality, and characteristics."""
    
    def __init__(self):
        """Initialize content analyzer."""
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=100,
            stop_words='english',
            ngram_range=(1, 2)
        )
    
    async def analyze_content(
        self,
        content: str,
        mime_type: str,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive content analysis.
        
        Args:
            content: Text content to analyze
            mime_type: Detected MIME type
            language: Detected language
            
        Returns:
            Analysis results including structure, quality, and metrics
        """
        results = {
            'content_type': mime_type,
            'language': language,
            'metrics': {},
            'structure': {},
            'quality': {},
            'keywords': [],
            'entities': [],
            'summary': {}
        }
        
        if mime_type.startswith('text/html'):
            html_analysis = await self._analyze_html(content)
            results.update(html_analysis)
        elif mime_type == 'application/json':
            json_analysis = self._analyze_json_structure(content)
            results['structure'] = json_analysis
        elif mime_type.startswith('text/'):
            text_analysis = await self._analyze_text(content)
            results.update(text_analysis)
        
        # Common metrics for all text content
        if mime_type.startswith(('text/', 'application/json', 'application/xml')):
            results['metrics'] = self._calculate_text_metrics(content)
            results['quality'] = await self._assess_content_quality(content, results['metrics'])
        
        return results
    
    async def _analyze_html(self, html_content: str) -> Dict[str, Any]:
        """Analyze HTML structure and content."""
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        analysis = {
            'structure': {
                'title': soup.title.string if soup.title else None,
                'headings': self._extract_headings(soup),
                'links': self._analyze_links(soup),
                'images': self._analyze_images(soup),
                'forms': self._analyze_forms(soup),
                'tables': len(soup.find_all('table')),
                'lists': len(soup.find_all(['ul', 'ol'])),
                'semantic_elements': self._count_semantic_elements(soup)
            },
            'metadata': self._extract_metadata(soup),
            'main_content': await self._extract_main_content(soup),
            'navigation': self._identify_navigation(soup),
            'accessibility': self._check_accessibility(soup)
        }
        
        # Extract text for keyword analysis
        text_content = soup.get_text(separator=' ', strip=True)
        if text_content:
            analysis['keywords'] = await self._extract_keywords(text_content)
        
        return analysis
    
    def _extract_headings(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract and analyze heading structure."""
        headings = []
        for i in range(1, 7):
            for heading in soup.find_all(f'h{i}'):
                headings.append({
                    'level': i,
                    'text': heading.get_text(strip=True),
                    'id': heading.get('id'),
                    'class': heading.get('class')
                })
        return headings
    
    def _analyze_links(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Analyze link structure and types."""
        links = soup.find_all('a', href=True)
        
        internal_links = []
        external_links = []
        anchor_links = []
        
        for link in links:
            href = link['href']
            text = link.get_text(strip=True)
            
            if href.startswith('#'):
                anchor_links.append({'href': href, 'text': text})
            elif href.startswith(('http://', 'https://')):
                external_links.append({'href': href, 'text': text})
            else:
                internal_links.append({'href': href, 'text': text})
        
        return {
            'total': len(links),
            'internal': len(internal_links),
            'external': len(external_links),
            'anchors': len(anchor_links),
            'samples': {
                'internal': internal_links[:5],
                'external': external_links[:5],
                'anchors': anchor_links[:5]
            }
        }
    
    def _analyze_images(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Analyze image usage and accessibility."""
        images = soup.find_all('img')
        
        with_alt = 0
        without_alt = 0
        lazy_loaded = 0
        
        for img in images:
            if img.get('alt'):
                with_alt += 1
            else:
                without_alt += 1
            
            if img.get('loading') == 'lazy' or 'lazy' in img.get('class', []):
                lazy_loaded += 1
        
        return {
            'total': len(images),
            'with_alt_text': with_alt,
            'without_alt_text': without_alt,
            'lazy_loaded': lazy_loaded,
            'formats': self._count_image_formats(images)
        }
    
    def _count_image_formats(self, images) -> Dict[str, int]:
        """Count different image formats."""
        formats = Counter()
        for img in images:
            src = img.get('src', '')
            if src:
                ext = src.split('.')[-1].lower()
                if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg']:
                    formats[ext] += 1
        return dict(formats)
    
    def _analyze_forms(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Analyze form elements."""
        forms = []
        for form in soup.find_all('form'):
            form_data = {
                'action': form.get('action'),
                'method': form.get('method', 'get').upper(),
                'inputs': len(form.find_all('input')),
                'textareas': len(form.find_all('textarea')),
                'selects': len(form.find_all('select')),
                'buttons': len(form.find_all(['button', 'input[type="submit"]']))
            }
            forms.append(form_data)
        return forms
    
    def _count_semantic_elements(self, soup: BeautifulSoup) -> Dict[str, int]:
        """Count HTML5 semantic elements."""
        semantic_tags = [
            'article', 'aside', 'details', 'figcaption', 'figure',
            'footer', 'header', 'main', 'mark', 'nav', 'section',
            'summary', 'time'
        ]
        
        counts = {}
        for tag in semantic_tags:
            count = len(soup.find_all(tag))
            if count > 0:
                counts[tag] = count
        
        return counts
    
    def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract metadata from HTML head."""
        metadata = {
            'meta_tags': {},
            'open_graph': {},
            'twitter_card': {},
            'schema_org': []
        }
        
        # Standard meta tags
        for meta in soup.find_all('meta'):
            name = meta.get('name') or meta.get('property')
            content = meta.get('content')
            
            if name and content:
                if name.startswith('og:'):
                    metadata['open_graph'][name] = content
                elif name.startswith('twitter:'):
                    metadata['twitter_card'][name] = content
                else:
                    metadata['meta_tags'][name] = content
        
        # JSON-LD structured data
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(script.string)
                metadata['schema_org'].append(data)
            except:
                pass
        
        return metadata
    
    async def _extract_main_content(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract main content area using heuristics."""
        # Common main content indicators
        main_selectors = [
            'main', 'article', '[role="main"]', '#main', '#content',
            '.main', '.content', '.post', '.article'
        ]
        
        main_content = None
        for selector in main_selectors:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        # Fallback: find largest text block
        if not main_content:
            text_blocks = []
            for elem in soup.find_all(['div', 'section', 'article']):
                text = elem.get_text(strip=True)
                if len(text) > 100:
                    text_blocks.append((len(text), elem))
            
            if text_blocks:
                text_blocks.sort(reverse=True)
                main_content = text_blocks[0][1]
        
        if main_content:
            text = main_content.get_text(separator=' ', strip=True)
            return {
                'text': text[:1000],  # First 1000 chars
                'length': len(text),
                'word_count': len(text.split()),
                'detected_by': 'selector' if main_content else 'heuristic'
            }
        
        return {'text': '', 'length': 0, 'word_count': 0, 'detected_by': 'none'}
    
    def _identify_navigation(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Identify navigation elements."""
        nav_elements = []
        
        # Find nav elements
        for nav in soup.find_all(['nav', '[role="navigation"]']):
            links = nav.find_all('a')
            nav_elements.append({
                'type': 'nav_element',
                'link_count': len(links),
                'links': [{'text': a.get_text(strip=True), 'href': a.get('href')} 
                         for a in links[:10]]
            })
        
        # Find header/footer navigation
        for container in soup.find_all(['header', 'footer']):
            links = container.find_all('a')
            if len(links) > 3:
                nav_elements.append({
                    'type': container.name,
                    'link_count': len(links),
                    'links': [{'text': a.get_text(strip=True), 'href': a.get('href')} 
                             for a in links[:10]]
                })
        
        return nav_elements
    
    def _check_accessibility(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Check basic accessibility features."""
        return {
            'lang_attribute': bool(soup.html and soup.html.get('lang')),
            'images_with_alt': len(soup.find_all('img', alt=True)),
            'images_without_alt': len(soup.find_all('img', alt=False)),
            'form_labels': len(soup.find_all('label')),
            'aria_landmarks': len(soup.find_all(attrs={'role': True})),
            'skip_links': bool(soup.find('a', href='#main') or soup.find('a', href='#content'))
        }
    
    async def _analyze_text(self, text_content: str) -> Dict[str, Any]:
        """Analyze plain text content."""
        return {
            'structure': {
                'paragraphs': len(re.findall(r'\n\n+', text_content)),
                'sentences': len(re.findall(r'[.!?]+', text_content)),
                'has_sections': bool(re.search(r'^#{1,6}\s+', text_content, re.MULTILINE))
            },
            'keywords': await self._extract_keywords(text_content)
        }
    
    def _analyze_json_structure(self, content: str) -> Dict[str, Any]:
        """Analyze JSON structure."""
        try:
            import json
            data = json.loads(content)
            
            def analyze_structure(obj, depth=0):
                if depth > 10:  # Prevent infinite recursion
                    return {'type': 'deep_nested'}
                
                if isinstance(obj, dict):
                    return {
                        'type': 'object',
                        'keys': list(obj.keys())[:10],
                        'size': len(obj)
                    }
                elif isinstance(obj, list):
                    return {
                        'type': 'array',
                        'length': len(obj),
                        'item_types': list(set(type(item).__name__ for item in obj[:10]))
                    }
                else:
                    return {'type': type(obj).__name__}
            
            return analyze_structure(data)
        except:
            return {'error': 'Invalid JSON'}
    
    def _calculate_text_metrics(self, content: str) -> Dict[str, Any]:
        """Calculate various text metrics."""
        words = content.split()
        sentences = re.findall(r'[.!?]+', content)
        
        # Calculate readability metrics
        avg_word_length = sum(len(word) for word in words) / len(words) if words else 0
        avg_sentence_length = len(words) / len(sentences) if sentences else 0
        
        # Simple readability score (Flesch Reading Ease approximation)
        if sentences and words:
            syllable_count = sum(self._count_syllables(word) for word in words)
            avg_syllables_per_word = syllable_count / len(words)
            flesch_score = 206.835 - 1.015 * avg_sentence_length - 84.6 * avg_syllables_per_word
            flesch_score = max(0, min(100, flesch_score))
        else:
            flesch_score = 0
        
        return {
            'character_count': len(content),
            'word_count': len(words),
            'sentence_count': len(sentences),
            'average_word_length': round(avg_word_length, 2),
            'average_sentence_length': round(avg_sentence_length, 2),
            'readability_score': round(flesch_score, 2),
            'unique_words': len(set(words)),
            'lexical_diversity': round(len(set(words)) / len(words), 2) if words else 0
        }
    
    def _count_syllables(self, word: str) -> int:
        """Estimate syllable count in a word."""
        word = word.lower()
        count = 0
        vowels = 'aeiouy'
        
        if word[0] in vowels:
            count += 1
        
        for index in range(1, len(word)):
            if word[index] in vowels and word[index - 1] not in vowels:
                count += 1
        
        if word.endswith('e'):
            count -= 1
        
        if word.endswith('le') and len(word) > 2 and word[-3] not in vowels:
            count += 1
        
        if count == 0:
            count = 1
        
        return count
    
    async def _assess_content_quality(
        self, 
        content: str, 
        metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess overall content quality."""
        quality_score = 0
        factors = []
        
        # Length check
        if 300 <= metrics['word_count'] <= 3000:
            quality_score += 20
            factors.append('appropriate_length')
        elif metrics['word_count'] < 100:
            factors.append('too_short')
        else:
            factors.append('too_long')
        
        # Readability check
        if 30 <= metrics['readability_score'] <= 70:
            quality_score += 20
            factors.append('good_readability')
        elif metrics['readability_score'] < 30:
            factors.append('too_complex')
        else:
            factors.append('too_simple')
        
        # Lexical diversity
        if metrics['lexical_diversity'] > 0.5:
            quality_score += 20
            factors.append('good_vocabulary')
        else:
            factors.append('repetitive_vocabulary')
        
        # Sentence variety
        if 10 <= metrics['average_sentence_length'] <= 25:
            quality_score += 20
            factors.append('good_sentence_structure')
        
        # Structure check
        if metrics['sentence_count'] > 5:
            quality_score += 20
            factors.append('well_structured')
        
        return {
            'score': quality_score,
            'factors': factors,
            'recommendations': self._generate_quality_recommendations(factors)
        }
    
    def _generate_quality_recommendations(self, factors: List[str]) -> List[str]:
        """Generate content quality improvement recommendations."""
        recommendations = []
        
        if 'too_short' in factors:
            recommendations.append('Add more detailed information to improve content depth')
        if 'too_long' in factors:
            recommendations.append('Consider breaking content into smaller, focused sections')
        if 'too_complex' in factors:
            recommendations.append('Simplify language and use shorter sentences')
        if 'too_simple' in factors:
            recommendations.append('Add more sophisticated vocabulary and complex ideas')
        if 'repetitive_vocabulary' in factors:
            recommendations.append('Use synonyms and varied expressions')
        
        return recommendations
    
    async def _extract_keywords(self, text: str, max_keywords: int = 20) -> List[Dict[str, Any]]:
        """Extract keywords using TF-IDF."""
        try:
            # Clean text
            clean_text = re.sub(r'[^\w\s]', ' ', text)
            clean_text = re.sub(r'\s+', ' ', clean_text)
            
            # Fit TF-IDF
            tfidf_matrix = self.tfidf_vectorizer.fit_transform([clean_text])
            feature_names = self.tfidf_vectorizer.get_feature_names_out()
            
            # Get scores
            scores = tfidf_matrix.toarray()[0]
            keyword_scores = [(feature_names[i], scores[i]) 
                             for i in scores.argsort()[-max_keywords:][::-1]]
            
            return [
                {'keyword': keyword, 'score': round(score, 3)}
                for keyword, score in keyword_scores if score > 0
            ]
        except Exception as e:
            logger.warning(f"Keyword extraction failed: {e}")
            return []