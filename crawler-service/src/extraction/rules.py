"""Custom extraction rules engine for flexible data extraction."""

import re
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from bs4 import BeautifulSoup, Tag
import json
from jsonpath_ng import parse as jsonpath_parse
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ExtractionRule:
    """Define a custom extraction rule."""
    
    name: str
    selector: Optional[str] = None  # CSS selector
    xpath: Optional[str] = None  # XPath expression
    regex: Optional[str] = None  # Regular expression
    jsonpath: Optional[str] = None  # JSONPath expression
    
    # Extraction options
    attribute: Optional[str] = None  # Extract specific attribute
    extract_text: bool = True  # Extract text content
    extract_all: bool = False  # Extract all matches or just first
    
    # Transformation
    transform: Optional[Callable[[Any], Any]] = None
    default: Any = None
    
    # Validation
    required: bool = False
    validator: Optional[Callable[[Any], bool]] = None
    
    # Nested rules
    children: List['ExtractionRule'] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate rule configuration."""
        if not any([self.selector, self.xpath, self.regex, self.jsonpath]):
            raise ValueError("At least one selector type must be specified")


class RuleEngine:
    """Engine for applying extraction rules to content."""
    
    def __init__(self):
        """Initialize the rule engine."""
        self.rules_registry: Dict[str, List[ExtractionRule]] = {}
        self.extraction_stats = {
            'total_extractions': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'validation_failures': 0
        }
    
    def register_rules(self, category: str, rules: List[ExtractionRule]):
        """Register extraction rules for a category."""
        self.rules_registry[category] = rules
        logger.info(f"Registered {len(rules)} rules for category: {category}")
    
    async def extract(
        self,
        content: Union[str, Dict],
        category: str,
        content_type: str = 'html'
    ) -> Dict[str, Any]:
        """
        Apply extraction rules to content.
        
        Args:
            content: Content to extract from (HTML string or JSON dict)
            category: Rule category to apply
            content_type: Type of content ('html' or 'json')
            
        Returns:
            Extracted data
        """
        self.extraction_stats['total_extractions'] += 1
        
        if category not in self.rules_registry:
            logger.warning(f"No rules registered for category: {category}")
            return {}
        
        rules = self.rules_registry[category]
        
        if content_type == 'html':
            soup = BeautifulSoup(content, 'lxml') if isinstance(content, str) else content
            return await self._extract_from_html(soup, rules)
        elif content_type == 'json':
            data = json.loads(content) if isinstance(content, str) else content
            return await self._extract_from_json(data, rules)
        else:
            raise ValueError(f"Unsupported content type: {content_type}")
    
    async def _extract_from_html(
        self,
        soup: BeautifulSoup,
        rules: List[ExtractionRule]
    ) -> Dict[str, Any]:
        """Extract data from HTML using rules."""
        results = {}
        
        for rule in rules:
            try:
                value = await self._apply_html_rule(soup, rule)
                
                # Validate if required
                if rule.required and not value:
                    logger.warning(f"Required field '{rule.name}' not found")
                    self.extraction_stats['validation_failures'] += 1
                
                # Apply validator if present
                if value and rule.validator and not rule.validator(value):
                    logger.warning(f"Validation failed for field '{rule.name}'")
                    self.extraction_stats['validation_failures'] += 1
                    value = rule.default
                
                results[rule.name] = value if value is not None else rule.default
                self.extraction_stats['successful_extractions'] += 1
                
            except Exception as e:
                logger.error(f"Error applying rule '{rule.name}': {e}")
                self.extraction_stats['failed_extractions'] += 1
                results[rule.name] = rule.default
        
        return results
    
    async def _apply_html_rule(
        self,
        soup: BeautifulSoup,
        rule: ExtractionRule
    ) -> Any:
        """Apply a single HTML extraction rule."""
        elements = []
        
        # CSS selector
        if rule.selector:
            if rule.extract_all:
                elements = soup.select(rule.selector)
            else:
                element = soup.select_one(rule.selector)
                elements = [element] if element else []
        
        # XPath (using lxml if available)
        elif rule.xpath:
            try:
                from lxml import etree
                tree = etree.HTML(str(soup))
                xpath_results = tree.xpath(rule.xpath)
                
                if not rule.extract_all and xpath_results:
                    xpath_results = xpath_results[:1]
                
                # Convert lxml elements back to BeautifulSoup
                for result in xpath_results:
                    if isinstance(result, str):
                        elements.append(result)
                    else:
                        elements.append(BeautifulSoup(etree.tostring(result), 'lxml'))
                        
            except ImportError:
                logger.warning("lxml not available for XPath extraction")
        
        # Extract values from elements
        values = []
        for element in elements:
            value = self._extract_from_element(element, rule)
            
            # Apply regex if specified
            if value and rule.regex:
                match = re.search(rule.regex, str(value))
                value = match.group(0) if match else None
            
            # Apply transformation
            if value is not None and rule.transform:
                value = rule.transform(value)
            
            if value is not None:
                values.append(value)
        
        # Process children rules if present
        if rule.children and elements:
            child_results = []
            for element in elements:
                child_data = {}
                for child_rule in rule.children:
                    child_value = await self._apply_html_rule(element, child_rule)
                    child_data[child_rule.name] = child_value
                child_results.append(child_data)
            
            return child_results if rule.extract_all else (child_results[0] if child_results else None)
        
        # Return results
        if rule.extract_all:
            return values
        else:
            return values[0] if values else None
    
    def _extract_from_element(
        self,
        element: Union[Tag, str],
        rule: ExtractionRule
    ) -> Optional[str]:
        """Extract value from a single element."""
        if isinstance(element, str):
            return element
        
        if rule.attribute:
            return element.get(rule.attribute)
        elif rule.extract_text:
            return element.get_text(strip=True)
        else:
            return str(element)
    
    async def _extract_from_json(
        self,
        data: Dict,
        rules: List[ExtractionRule]
    ) -> Dict[str, Any]:
        """Extract data from JSON using rules."""
        results = {}
        
        for rule in rules:
            try:
                value = None
                
                # JSONPath extraction
                if rule.jsonpath:
                    jsonpath_expr = jsonpath_parse(rule.jsonpath)
                    matches = jsonpath_expr.find(data)
                    
                    if matches:
                        if rule.extract_all:
                            value = [match.value for match in matches]
                        else:
                            value = matches[0].value
                
                # Regex extraction on string values
                if value and rule.regex and isinstance(value, str):
                    match = re.search(rule.regex, value)
                    value = match.group(0) if match else None
                
                # Apply transformation
                if value is not None and rule.transform:
                    value = rule.transform(value)
                
                # Validation
                if rule.required and not value:
                    logger.warning(f"Required field '{rule.name}' not found")
                    self.extraction_stats['validation_failures'] += 1
                
                if value and rule.validator and not rule.validator(value):
                    logger.warning(f"Validation failed for field '{rule.name}'")
                    self.extraction_stats['validation_failures'] += 1
                    value = rule.default
                
                results[rule.name] = value if value is not None else rule.default
                self.extraction_stats['successful_extractions'] += 1
                
            except Exception as e:
                logger.error(f"Error applying rule '{rule.name}': {e}")
                self.extraction_stats['failed_extractions'] += 1
                results[rule.name] = rule.default
        
        return results
    
    def create_common_rules(self) -> Dict[str, List[ExtractionRule]]:
        """Create common extraction rule sets."""
        return {
            'article': [
                ExtractionRule(
                    name='title',
                    selector='h1, article h1, .article-title, .post-title',
                    required=True
                ),
                ExtractionRule(
                    name='author',
                    selector='.author, .by-line, .article-author, [rel="author"]'
                ),
                ExtractionRule(
                    name='date',
                    selector='time, .date, .publish-date, .article-date',
                    attribute='datetime',
                    transform=lambda x: x if x else None
                ),
                ExtractionRule(
                    name='content',
                    selector='article, .article-content, .post-content, .entry-content',
                    children=[
                        ExtractionRule(
                            name='paragraphs',
                            selector='p',
                            extract_all=True
                        ),
                        ExtractionRule(
                            name='images',
                            selector='img',
                            attribute='src',
                            extract_all=True
                        )
                    ]
                ),
                ExtractionRule(
                    name='tags',
                    selector='.tag, .tags a, .article-tags a',
                    extract_all=True
                ),
                ExtractionRule(
                    name='category',
                    selector='.category, .article-category'
                )
            ],
            
            'product': [
                ExtractionRule(
                    name='name',
                    selector='h1.product-name, .product-title, [itemprop="name"]',
                    required=True
                ),
                ExtractionRule(
                    name='price',
                    selector='.price, .product-price, [itemprop="price"]',
                    regex=r'[\d,]+\.?\d*',
                    transform=lambda x: float(x.replace(',', '')) if x else None
                ),
                ExtractionRule(
                    name='currency',
                    selector='[itemprop="priceCurrency"]',
                    attribute='content',
                    default='USD'
                ),
                ExtractionRule(
                    name='availability',
                    selector='.availability, .stock-status, [itemprop="availability"]'
                ),
                ExtractionRule(
                    name='rating',
                    selector='.rating, .stars, [itemprop="ratingValue"]',
                    regex=r'[\d\.]+',
                    transform=lambda x: float(x) if x else None
                ),
                ExtractionRule(
                    name='reviews_count',
                    selector='.reviews-count, [itemprop="reviewCount"]',
                    regex=r'\d+',
                    transform=lambda x: int(x) if x else 0
                ),
                ExtractionRule(
                    name='images',
                    selector='.product-images img, .gallery img',
                    attribute='src',
                    extract_all=True
                ),
                ExtractionRule(
                    name='description',
                    selector='.product-description, [itemprop="description"]'
                ),
                ExtractionRule(
                    name='specifications',
                    selector='.specifications, .product-specs',
                    children=[
                        ExtractionRule(
                            name='items',
                            selector='li, tr',
                            extract_all=True
                        )
                    ]
                )
            ],
            
            'contact': [
                ExtractionRule(
                    name='phone',
                    selector='[href^="tel:"], .phone, .telephone',
                    regex=r'[\d\-\+\(\)\s]+',
                    extract_all=True
                ),
                ExtractionRule(
                    name='email',
                    selector='[href^="mailto:"], .email',
                    regex=r'[\w\.-]+@[\w\.-]+\.\w+',
                    extract_all=True
                ),
                ExtractionRule(
                    name='address',
                    selector='.address, [itemprop="address"], address'
                ),
                ExtractionRule(
                    name='social_links',
                    selector='a[href*="facebook.com"], a[href*="twitter.com"], a[href*="linkedin.com"], a[href*="instagram.com"]',
                    attribute='href',
                    extract_all=True
                )
            ]
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get extraction statistics."""
        success_rate = (
            self.extraction_stats['successful_extractions'] /
            max(self.extraction_stats['total_extractions'], 1)
        )
        
        return {
            **self.extraction_stats,
            'success_rate': round(success_rate, 2),
            'registered_categories': list(self.rules_registry.keys()),
            'total_rules': sum(len(rules) for rules in self.rules_registry.values())
        }