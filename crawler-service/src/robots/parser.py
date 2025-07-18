"""Advanced Robots.txt parser with full directive support"""

import re
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass, field

import aiohttp
from reppy.robots import Robots
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class RobotsRule:
    """Represents a single robots.txt rule"""
    user_agent: str
    allowed_paths: List[str] = field(default_factory=list)
    disallowed_paths: List[str] = field(default_factory=list)
    crawl_delay: Optional[float] = None
    request_rate: Optional[Tuple[int, int]] = None  # (requests, seconds)
    sitemaps: List[str] = field(default_factory=list)
    
    
class RobotsParser:
    """
    Advanced robots.txt parser supporting:
    - User-agent specific rules
    - Crawl-delay and Request-rate directives
    - Sitemap discovery
    - Wildcard patterns
    - Comments and extensions
    """
    
    def __init__(
        self,
        user_agent: str = "LLMOptimizer",
        timeout: float = 10.0,
        max_size: int = 500_000  # 500KB max
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_size = max_size
        
        # Compiled regex patterns
        self._patterns = {
            "user_agent": re.compile(r"^\s*user-agent\s*:\s*(.+)$", re.I),
            "allow": re.compile(r"^\s*allow\s*:\s*(.+)$", re.I),
            "disallow": re.compile(r"^\s*disallow\s*:\s*(.+)$", re.I),
            "crawl_delay": re.compile(r"^\s*crawl-delay\s*:\s*(\d+\.?\d*)$", re.I),
            "request_rate": re.compile(r"^\s*request-rate\s*:\s*(\d+)/(\d+)$", re.I),
            "sitemap": re.compile(r"^\s*sitemap\s*:\s*(.+)$", re.I),
            "comment": re.compile(r"^\s*#"),
        }
        
    async def fetch_robots_txt(self, domain: str) -> Optional[str]:
        """Fetch robots.txt content from domain"""
        robots_url = f"https://{domain}/robots.txt"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    robots_url,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                    allow_redirects=True
                ) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        # Check size limit
                        if len(content) > self.max_size:
                            logger.warning(
                                "robots.txt exceeds size limit",
                                domain=domain,
                                size=len(content)
                            )
                            content = content[:self.max_size]
                            
                        return content
                    elif response.status == 404:
                        logger.info("No robots.txt found", domain=domain)
                        return None
                    else:
                        logger.warning(
                            "Failed to fetch robots.txt",
                            domain=domain,
                            status=response.status
                        )
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("Timeout fetching robots.txt", domain=domain)
            return None
        except Exception as e:
            logger.error(
                "Error fetching robots.txt",
                domain=domain,
                error=str(e)
            )
            return None
            
    def parse(self, content: str, domain: str) -> Dict[str, RobotsRule]:
        """Parse robots.txt content into rules"""
        rules: Dict[str, RobotsRule] = {}
        current_agents: List[str] = []
        global_sitemaps: List[str] = []
        
        lines = content.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or self._patterns["comment"].match(line):
                continue
                
            # Check for User-agent
            match = self._patterns["user_agent"].match(line)
            if match:
                agent = match.group(1).strip().lower()
                current_agents = [agent]
                
                # Initialize rule for this agent if not exists
                if agent not in rules:
                    rules[agent] = RobotsRule(user_agent=agent)
                continue
                
            # Skip if no current agents
            if not current_agents:
                # Check for global sitemap
                match = self._patterns["sitemap"].match(line)
                if match:
                    sitemap_url = match.group(1).strip()
                    if self._is_valid_url(sitemap_url):
                        global_sitemaps.append(sitemap_url)
                continue
                
            # Parse directives for current agents
            for agent in current_agents:
                if agent not in rules:
                    rules[agent] = RobotsRule(user_agent=agent)
                    
                rule = rules[agent]
                
                # Allow directive
                match = self._patterns["allow"].match(line)
                if match:
                    path = match.group(1).strip()
                    if path:
                        rule.allowed_paths.append(path)
                    continue
                    
                # Disallow directive
                match = self._patterns["disallow"].match(line)
                if match:
                    path = match.group(1).strip()
                    if path:
                        rule.disallowed_paths.append(path)
                    continue
                    
                # Crawl-delay directive
                match = self._patterns["crawl_delay"].match(line)
                if match:
                    try:
                        rule.crawl_delay = float(match.group(1))
                    except ValueError:
                        pass
                    continue
                    
                # Request-rate directive
                match = self._patterns["request_rate"].match(line)
                if match:
                    try:
                        requests = int(match.group(1))
                        seconds = int(match.group(2))
                        rule.request_rate = (requests, seconds)
                    except ValueError:
                        pass
                    continue
                    
                # Sitemap directive
                match = self._patterns["sitemap"].match(line)
                if match:
                    sitemap_url = match.group(1).strip()
                    if self._is_valid_url(sitemap_url):
                        # Make absolute URL if relative
                        if not sitemap_url.startswith(('http://', 'https://')):
                            sitemap_url = urljoin(f"https://{domain}", sitemap_url)
                        rule.sitemaps.append(sitemap_url)
                        
        # Add global sitemaps to all rules
        for rule in rules.values():
            rule.sitemaps.extend(global_sitemaps)
            
        # Ensure we have a default rule
        if "*" not in rules:
            rules["*"] = RobotsRule(user_agent="*", sitemaps=global_sitemaps)
            
        return rules
        
    def can_crawl(
        self,
        url: str,
        rules: Dict[str, RobotsRule],
        user_agent: Optional[str] = None
    ) -> bool:
        """Check if URL can be crawled according to rules"""
        user_agent = user_agent or self.user_agent
        
        # Find applicable rule
        rule = self._find_applicable_rule(rules, user_agent)
        if not rule:
            return True  # No rules means allow
            
        parsed_url = urlparse(url)
        path = parsed_url.path
        
        # Check allowed paths first (they take precedence)
        for pattern in rule.allowed_paths:
            if self._matches_pattern(path, pattern):
                return True
                
        # Check disallowed paths
        for pattern in rule.disallowed_paths:
            if self._matches_pattern(path, pattern):
                return False
                
        # No matching rules means allow
        return True
        
    def get_crawl_delay(
        self,
        rules: Dict[str, RobotsRule],
        user_agent: Optional[str] = None
    ) -> Optional[float]:
        """Get crawl delay for user agent"""
        user_agent = user_agent or self.user_agent
        rule = self._find_applicable_rule(rules, user_agent)
        
        if rule:
            # Convert request rate to crawl delay if needed
            if rule.crawl_delay:
                return rule.crawl_delay
            elif rule.request_rate:
                requests, seconds = rule.request_rate
                return seconds / requests
                
        return None
        
    def get_sitemaps(
        self,
        rules: Dict[str, RobotsRule]
    ) -> List[str]:
        """Get all sitemap URLs from rules"""
        sitemaps = set()
        
        for rule in rules.values():
            sitemaps.update(rule.sitemaps)
            
        return list(sitemaps)
        
    def _find_applicable_rule(
        self,
        rules: Dict[str, RobotsRule],
        user_agent: str
    ) -> Optional[RobotsRule]:
        """Find the most specific applicable rule for user agent"""
        user_agent_lower = user_agent.lower()
        
        # Try exact match first
        if user_agent_lower in rules:
            return rules[user_agent_lower]
            
        # Try prefix match
        for agent, rule in rules.items():
            if user_agent_lower.startswith(agent.lower()):
                return rule
                
        # Try wildcard match
        if "*" in rules:
            return rules["*"]
            
        return None
        
    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if path matches robot pattern (with wildcards)"""
        # Handle empty pattern
        if not pattern:
            return False
            
        # Convert robot pattern to regex
        regex_pattern = re.escape(pattern)
        regex_pattern = regex_pattern.replace(r'\*', '.*')
        regex_pattern = regex_pattern.replace(r'\$', '$')
        
        # Add start anchor
        if not regex_pattern.startswith('^'):
            regex_pattern = '^' + regex_pattern
            
        try:
            return bool(re.match(regex_pattern, path))
        except re.error:
            logger.error(
                "Invalid robots pattern",
                pattern=pattern,
                regex=regex_pattern
            )
            return False
            
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid"""
        try:
            result = urlparse(url)
            return bool(result.scheme and result.netloc) or url.startswith('/')
        except Exception:
            return False
            
    async def parse_from_url(self, domain: str) -> Optional[Dict[str, RobotsRule]]:
        """Fetch and parse robots.txt from domain"""
        content = await self.fetch_robots_txt(domain)
        
        if content:
            return self.parse(content, domain)
            
        # Return default permissive rules if no robots.txt
        return {
            "*": RobotsRule(user_agent="*")
        }
        
    def parse_with_reppy(self, content: str, url: str) -> Robots:
        """Parse using reppy library for compatibility"""
        try:
            return Robots.parse(url, content)
        except Exception as e:
            logger.error(
                "Failed to parse with reppy",
                url=url,
                error=str(e)
            )
            return None