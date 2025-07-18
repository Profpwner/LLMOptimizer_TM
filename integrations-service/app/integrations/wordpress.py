"""WordPress integration implementation."""

import base64
import hmac
import hashlib
from typing import Dict, Any, List, Optional, AsyncIterator
from datetime import datetime, timedelta
import urllib.parse
import logging
import re
from bs4 import BeautifulSoup

from app.integrations.base import BaseIntegration, IntegrationError, AuthenticationError
from app.integrations.registry import IntegrationRegistry
from app.models import IntegrationType, OAuthToken, SyncJob
from app.core.config import get_settings, INTEGRATION_CONFIGS
from app.utils.crypto import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)
settings = get_settings()


@IntegrationRegistry.register(IntegrationType.WORDPRESS)
class WordPressIntegration(BaseIntegration):
    """WordPress integration supporting REST API with Application Passwords."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = INTEGRATION_CONFIGS["wordpress"]
        self.api_version = self.config["api_version"]
        self._site_url = None
        self._gutenberg_parser = GutenbergBlockParser()
        
    @property
    async def site_url(self) -> str:
        """Get WordPress site URL."""
        if not self._site_url:
            self._site_url = self.integration.config.api_endpoint or settings.wordpress_api_endpoint
        return self._site_url
    
    async def setup_application_password(self, username: str, password: str, app_name: str = "LLMOptimizer") -> Dict[str, Any]:
        """Setup WordPress Application Password for API access."""
        site_url = await self.site_url
        
        # First authenticate with regular credentials
        auth_header = base64.b64encode(f"{username}:{password}".encode()).decode()
        
        # Create application password
        response = await self.http_client.post(
            f"{site_url}/wp-json/wp/v2/users/me/application-passwords",
            headers={
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/json"
            },
            json={
                "name": app_name
            }
        )
        
        if response.status_code != 201:
            raise AuthenticationError(f"Failed to create application password: {response.text}")
        
        data = response.json()
        
        # Store the application password
        app_password = data["password"]
        app_uuid = data["uuid"]
        
        # Create auth token for storage
        auth_token = base64.b64encode(f"{username}:{app_password}".encode()).decode()
        
        return {
            "username": username,
            "app_password": app_password,
            "app_uuid": app_uuid,
            "auth_token": auth_token
        }
    
    async def test_connection(self) -> bool:
        """Test WordPress connection."""
        try:
            site_url = await self.site_url
            response = await self.make_api_request(
                "GET",
                f"{site_url}/wp-json/wp/v2/posts",
                params={"per_page": 1}
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    async def make_api_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Override to handle WordPress authentication."""
        # Prepare headers
        request_headers = headers or {}
        
        # Add WordPress authentication
        if self.integration.api_key:
            # Application Password authentication
            request_headers["Authorization"] = f"Basic {self.integration.api_key}"
        elif self.integration.oauth_token:
            # OAuth token (if using OAuth plugin)
            token = decrypt_token(
                self.integration.oauth_token.access_token,
                settings.encryption_key
            ) if self.integration.oauth_token.encrypted else self.integration.oauth_token.access_token
            request_headers["Authorization"] = f"Bearer {token}"
        
        # Call parent method with modified headers
        return await super().make_api_request(
            method=method,
            url=url,
            headers=request_headers,
            params=params,
            json=json,
            data=data
        )
    
    async def sync_data(self, job: SyncJob) -> Dict[str, Any]:
        """Sync data with WordPress."""
        results = {
            "total_processed": 0,
            "created": 0,
            "updated": 0,
            "errors": 0,
            "entity_results": {}
        }
        
        for entity_type in job.entity_types:
            try:
                if entity_type == "posts":
                    entity_results = await self._sync_posts(job)
                elif entity_type == "pages":
                    entity_results = await self._sync_pages(job)
                elif entity_type == "media":
                    entity_results = await self._sync_media(job)
                elif entity_type == "users":
                    entity_results = await self._sync_users(job)
                elif entity_type == "categories":
                    entity_results = await self._sync_categories(job)
                elif entity_type == "tags":
                    entity_results = await self._sync_tags(job)
                elif entity_type.startswith("custom_post_type:"):
                    # Handle custom post types
                    post_type = entity_type.split(":", 1)[1]
                    entity_results = await self._sync_custom_post_type(job, post_type)
                else:
                    logger.warning(f"Unknown entity type: {entity_type}")
                    continue
                
                results["entity_results"][entity_type] = entity_results
                results["total_processed"] += entity_results["processed"]
                results["created"] += entity_results["created"]
                results["updated"] += entity_results["updated"]
                results["errors"] += entity_results["errors"]
                
            except Exception as e:
                logger.error(f"Error syncing {entity_type}: {e}")
                results["errors"] += 1
                await self.log_sync_operation(
                    job.id,
                    "ERROR",
                    f"sync_{entity_type}",
                    entity_type,
                    f"Failed to sync {entity_type}: {str(e)}",
                    error={"type": type(e).__name__, "message": str(e)}
                )
        
        return results
    
    async def _sync_posts(self, job: SyncJob) -> Dict[str, Any]:
        """Sync posts with WordPress."""
        return await self._sync_content_type(job, "posts", "post")
    
    async def _sync_pages(self, job: SyncJob) -> Dict[str, Any]:
        """Sync pages with WordPress."""
        return await self._sync_content_type(job, "pages", "page")
    
    async def _sync_custom_post_type(self, job: SyncJob, post_type: str) -> Dict[str, Any]:
        """Sync custom post type with WordPress."""
        return await self._sync_content_type(job, post_type, post_type)
    
    async def _sync_content_type(self, job: SyncJob, endpoint: str, content_type: str) -> Dict[str, Any]:
        """Generic sync for WordPress content types."""
        results = {"processed": 0, "created": 0, "updated": 0, "errors": 0}
        
        site_url = await self.site_url
        url = f"{site_url}/wp-json/wp/v2/{endpoint}"
        
        # Build query parameters
        params = {
            "per_page": 100,
            "_embed": "true"  # Include embedded data (author, featured media, etc.)
        }
        
        # Add filters from job
        if job.filters:
            if "status" in job.filters:
                params["status"] = job.filters["status"]
            if "author" in job.filters:
                params["author"] = job.filters["author"]
            if "categories" in job.filters:
                params["categories"] = job.filters["categories"]
            if "tags" in job.filters:
                params["tags"] = job.filters["tags"]
            if "after" in job.filters:
                params["after"] = job.filters["after"]
            if "before" in job.filters:
                params["before"] = job.filters["before"]
        
        async for item in self.paginate_api_results("GET", url, params):
            try:
                results["processed"] += 1
                
                # Parse content
                parsed_content = await self._parse_content(item)
                
                # Process item
                await self.log_sync_operation(
                    job.id,
                    "INFO",
                    f"process_{content_type}",
                    content_type,
                    f"Processed {content_type}: {item.get('title', {}).get('rendered', 'No title')}",
                    entity_id=str(item.get("id")),
                    details={
                        "wordpress_id": item.get("id"),
                        "slug": item.get("slug"),
                        "status": item.get("status")
                    }
                )
                
                # Here you would:
                # 1. Transform WordPress content to your internal format
                # 2. Check if content exists in your system
                # 3. Create or update as needed
                
            except Exception as e:
                results["errors"] += 1
                logger.error(f"Error processing {content_type}: {e}")
                await self.log_sync_operation(
                    job.id,
                    "ERROR",
                    f"process_{content_type}",
                    content_type,
                    f"Failed to process {content_type}: {str(e)}",
                    entity_id=str(item.get("id")),
                    error={"type": type(e).__name__, "message": str(e)}
                )
        
        return results
    
    async def _sync_media(self, job: SyncJob) -> Dict[str, Any]:
        """Sync media library with WordPress."""
        results = {"processed": 0, "created": 0, "updated": 0, "errors": 0}
        
        site_url = await self.site_url
        url = f"{site_url}/wp-json/wp/v2/media"
        
        params = {
            "per_page": 50,  # Media queries can be heavy
            "_embed": "true"
        }
        
        async for media in self.paginate_api_results("GET", url, params):
            try:
                results["processed"] += 1
                
                # Process media item
                await self.log_sync_operation(
                    job.id,
                    "INFO",
                    "process_media",
                    "media",
                    f"Processed media: {media.get('title', {}).get('rendered', 'No title')}",
                    entity_id=str(media.get("id")),
                    details={
                        "wordpress_id": media.get("id"),
                        "media_type": media.get("media_type"),
                        "mime_type": media.get("mime_type"),
                        "source_url": media.get("source_url")
                    }
                )
                
            except Exception as e:
                results["errors"] += 1
                logger.error(f"Error processing media: {e}")
        
        return results
    
    async def _sync_users(self, job: SyncJob) -> Dict[str, Any]:
        """Sync users with WordPress."""
        results = {"processed": 0, "created": 0, "updated": 0, "errors": 0}
        
        site_url = await self.site_url
        url = f"{site_url}/wp-json/wp/v2/users"
        
        params = {"per_page": 100, "context": "edit"}  # Edit context gives more fields
        
        async for user in self.paginate_api_results("GET", url, params):
            try:
                results["processed"] += 1
                
                # Process user
                await self.log_sync_operation(
                    job.id,
                    "INFO",
                    "process_user",
                    "user",
                    f"Processed user: {user.get('name', 'No name')}",
                    entity_id=str(user.get("id")),
                    details={
                        "wordpress_id": user.get("id"),
                        "username": user.get("username"),
                        "email": user.get("email"),
                        "roles": user.get("roles", [])
                    }
                )
                
            except Exception as e:
                results["errors"] += 1
                logger.error(f"Error processing user: {e}")
        
        return results
    
    async def _sync_categories(self, job: SyncJob) -> Dict[str, Any]:
        """Sync categories with WordPress."""
        return await self._sync_taxonomy(job, "categories", "category")
    
    async def _sync_tags(self, job: SyncJob) -> Dict[str, Any]:
        """Sync tags with WordPress."""
        return await self._sync_taxonomy(job, "tags", "tag")
    
    async def _sync_taxonomy(self, job: SyncJob, endpoint: str, taxonomy_type: str) -> Dict[str, Any]:
        """Generic sync for WordPress taxonomies."""
        results = {"processed": 0, "created": 0, "updated": 0, "errors": 0}
        
        site_url = await self.site_url
        url = f"{site_url}/wp-json/wp/v2/{endpoint}"
        
        params = {"per_page": 100}
        
        async for term in self.paginate_api_results("GET", url, params):
            try:
                results["processed"] += 1
                
                # Process taxonomy term
                await self.log_sync_operation(
                    job.id,
                    "INFO",
                    f"process_{taxonomy_type}",
                    taxonomy_type,
                    f"Processed {taxonomy_type}: {term.get('name', 'No name')}",
                    entity_id=str(term.get("id")),
                    details={
                        "wordpress_id": term.get("id"),
                        "slug": term.get("slug"),
                        "count": term.get("count")
                    }
                )
                
            except Exception as e:
                results["errors"] += 1
                logger.error(f"Error processing {taxonomy_type}: {e}")
        
        return results
    
    async def _parse_content(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Parse WordPress content including Gutenberg blocks."""
        parsed = {
            "title": self._clean_html(item.get("title", {}).get("rendered", "")),
            "content": item.get("content", {}).get("rendered", ""),
            "excerpt": self._clean_html(item.get("excerpt", {}).get("rendered", "")),
            "blocks": []
        }
        
        # Parse Gutenberg blocks if present
        if "content" in item and "raw" in item["content"]:
            parsed["blocks"] = self._gutenberg_parser.parse(item["content"]["raw"])
        
        # Extract meta fields
        if "meta" in item:
            parsed["meta"] = item["meta"]
        
        # Extract custom fields (ACF, etc.)
        if "acf" in item:
            parsed["custom_fields"] = item["acf"]
        
        return parsed
    
    def _clean_html(self, html_content: str) -> str:
        """Clean HTML content to plain text."""
        if not html_content:
            return ""
        
        soup = BeautifulSoup(html_content, 'html.parser')
        return soup.get_text(strip=True)
    
    async def create_post(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new post in WordPress."""
        site_url = await self.site_url
        url = f"{site_url}/wp-json/wp/v2/posts"
        
        response = await self.make_api_request("POST", url, json=post_data)
        
        if response.status_code != 201:
            raise IntegrationError(f"Failed to create post: {response.text}")
        
        return response.json()
    
    async def update_post(self, post_id: int, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing post in WordPress."""
        site_url = await self.site_url
        url = f"{site_url}/wp-json/wp/v2/posts/{post_id}"
        
        response = await self.make_api_request("POST", url, json=post_data)
        
        if response.status_code != 200:
            raise IntegrationError(f"Failed to update post: {response.text}")
        
        return response.json()
    
    async def upload_media(self, file_path: str, media_data: Dict[str, Any]) -> Dict[str, Any]:
        """Upload media file to WordPress."""
        site_url = await self.site_url
        url = f"{site_url}/wp-json/wp/v2/media"
        
        # Read file
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Prepare multipart data
        files = {'file': (media_data.get('title', 'upload'), file_content)}
        
        response = await self.make_api_request(
            "POST",
            url,
            data=media_data,
            files=files
        )
        
        if response.status_code != 201:
            raise IntegrationError(f"Failed to upload media: {response.text}")
        
        return response.json()
    
    async def handle_webhook(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Handle WordPress webhook."""
        logger.info(f"Handling WordPress webhook: {event_type}")
        
        # WordPress webhooks typically come from plugins like WP Webhooks
        if event_type == "post_published":
            await self._handle_post_published(payload)
        elif event_type == "post_updated":
            await self._handle_post_updated(payload)
        elif event_type == "post_deleted":
            await self._handle_post_deleted(payload)
        elif event_type == "comment_posted":
            await self._handle_comment_posted(payload)
        elif event_type == "user_registered":
            await self._handle_user_registered(payload)
        else:
            logger.warning(f"Unknown webhook event type: {event_type}")
    
    async def _handle_post_published(self, payload: Dict[str, Any]) -> None:
        """Handle post published webhook."""
        post_id = payload.get("ID")
        logger.info(f"Post published: {post_id}")
        # Implement post published logic
    
    async def _handle_post_updated(self, payload: Dict[str, Any]) -> None:
        """Handle post updated webhook."""
        post_id = payload.get("ID")
        logger.info(f"Post updated: {post_id}")
        # Implement post updated logic
    
    async def _handle_post_deleted(self, payload: Dict[str, Any]) -> None:
        """Handle post deleted webhook."""
        post_id = payload.get("ID")
        logger.info(f"Post deleted: {post_id}")
        # Implement post deleted logic
    
    async def _handle_comment_posted(self, payload: Dict[str, Any]) -> None:
        """Handle comment posted webhook."""
        comment_id = payload.get("comment_ID")
        logger.info(f"Comment posted: {comment_id}")
        # Implement comment posted logic
    
    async def _handle_user_registered(self, payload: Dict[str, Any]) -> None:
        """Handle user registered webhook."""
        user_id = payload.get("ID")
        logger.info(f"User registered: {user_id}")
        # Implement user registered logic
    
    def verify_webhook_signature(self, signature: str, payload: bytes) -> bool:
        """Verify WordPress webhook signature."""
        if not settings.webhook_secret:
            logger.warning("No webhook secret configured")
            return False
        
        # WordPress webhook signature verification depends on the plugin
        # This is a generic HMAC-SHA256 implementation
        expected_signature = hmac.new(
            settings.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    def extract_results_from_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract results from WordPress API response."""
        # WordPress returns array directly
        if isinstance(data, list):
            return data
        return []
    
    def has_more_pages(self, data: Dict[str, Any], current_page: int) -> bool:
        """Check if there are more pages in WordPress response."""
        # WordPress uses Link header for pagination
        # This would need to be handled in the paginate_api_results method
        # by checking response headers
        return False
    
    async def get_custom_post_types(self) -> List[Dict[str, Any]]:
        """Get all custom post types."""
        site_url = await self.site_url
        url = f"{site_url}/wp-json/wp/v2/types"
        
        response = await self.make_api_request("GET", url)
        
        if response.status_code == 200:
            return response.json()
        return []
    
    async def get_custom_taxonomies(self) -> List[Dict[str, Any]]:
        """Get all custom taxonomies."""
        site_url = await self.site_url
        url = f"{site_url}/wp-json/wp/v2/taxonomies"
        
        response = await self.make_api_request("GET", url)
        
        if response.status_code == 200:
            return response.json()
        return []
    
    async def get_plugins(self) -> List[Dict[str, Any]]:
        """Get installed plugins (requires admin access)."""
        site_url = await self.site_url
        url = f"{site_url}/wp-json/wp/v2/plugins"
        
        try:
            response = await self.make_api_request("GET", url)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.warning(f"Failed to get plugins: {e}")
        return []


class GutenbergBlockParser:
    """Parser for Gutenberg blocks."""
    
    def __init__(self):
        self.block_pattern = re.compile(
            r'<!-- wp:([a-z][a-z0-9-]*/)?([a-z][a-z0-9-]*) ?({[^}]*})? ?/?-->'
        )
    
    def parse(self, content: str) -> List[Dict[str, Any]]:
        """Parse Gutenberg blocks from content."""
        blocks = []
        
        # Find all block comments
        matches = self.block_pattern.finditer(content)
        
        for match in matches:
            namespace = match.group(1) or 'core/'
            block_name = match.group(2)
            attributes_json = match.group(3)
            
            block = {
                "name": f"{namespace}{block_name}",
                "attributes": {}
            }
            
            # Parse attributes if present
            if attributes_json:
                try:
                    import json
                    block["attributes"] = json.loads(attributes_json)
                except Exception as e:
                    logger.warning(f"Failed to parse block attributes: {e}")
            
            blocks.append(block)
        
        return blocks