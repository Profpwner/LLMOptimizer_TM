"""GitHub integration implementation."""

import hmac
import hashlib
import jwt
import time
from typing import Dict, Any, List, Optional, AsyncIterator
from datetime import datetime, timedelta
import urllib.parse
import logging
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from app.integrations.base import BaseIntegration, IntegrationError, AuthenticationError
from app.integrations.registry import IntegrationRegistry
from app.models import IntegrationType, OAuthToken, SyncJob
from app.core.config import get_settings, INTEGRATION_CONFIGS
from app.utils.crypto import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)
settings = get_settings()


@IntegrationRegistry.register(IntegrationType.GITHUB)
class GitHubIntegration(BaseIntegration):
    """GitHub integration supporting OAuth and GitHub App authentication."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = INTEGRATION_CONFIGS["github"]
        self.api_base_url = self.config["api_base_url"]
        self._installation_token = None
        self._installation_token_expires_at = None
        
    async def get_authorization_url(self, state: str) -> str:
        """Generate GitHub OAuth authorization URL."""
        params = {
            "client_id": settings.github_client_id,
            "redirect_uri": settings.github_redirect_uri,
            "scope": " ".join(self.config["scopes"]),
            "state": state,
        }
        return f"{self.config['auth_url']}?{urllib.parse.urlencode(params)}"
    
    async def exchange_code_for_token(self, code: str) -> OAuthToken:
        """Exchange authorization code for access token."""
        data = {
            "client_id": settings.github_client_id,
            "client_secret": settings.github_client_secret,
            "redirect_uri": settings.github_redirect_uri,
            "code": code,
        }
        
        response = await self.http_client.post(
            self.config["token_url"],
            data=data,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded"
            },
        )
        
        if response.status_code != 200:
            raise AuthenticationError(f"Token exchange failed: {response.text}")
        
        token_data = response.json()
        
        if "error" in token_data:
            raise AuthenticationError(f"Token exchange failed: {token_data['error_description']}")
        
        # GitHub tokens don't expire by default
        expires_at = None
        if "expires_in" in token_data:
            expires_at = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
        
        return OAuthToken(
            access_token=encrypt_token(token_data["access_token"], settings.encryption_key),
            refresh_token=encrypt_token(token_data.get("refresh_token", ""), settings.encryption_key) if token_data.get("refresh_token") else None,
            token_type=token_data.get("token_type", "Bearer"),
            expires_at=expires_at,
            scope=token_data.get("scope", ""),
            encrypted=True,
        )
    
    async def refresh_access_token(self) -> OAuthToken:
        """Refresh GitHub access token (GitHub tokens typically don't expire)."""
        # GitHub OAuth tokens don't typically expire or have refresh tokens
        # If using GitHub App, we need to refresh the installation token
        if self.integration.config.custom_fields.get("github_app_id"):
            return await self._refresh_installation_token()
        
        raise AuthenticationError("GitHub OAuth tokens do not support refresh")
    
    async def _generate_jwt_token(self, app_id: str, private_key: str) -> str:
        """Generate JWT token for GitHub App authentication."""
        # Current time
        now = int(time.time())
        
        # JWT claims
        payload = {
            "iat": now - 60,  # Issued at time (60 seconds in the past to allow for clock drift)
            "exp": now + (10 * 60),  # Expiration time (10 minutes from now)
            "iss": app_id  # Issuer (GitHub App ID)
        }
        
        # Load private key
        private_key_obj = serialization.load_pem_private_key(
            private_key.encode(),
            password=None,
            backend=default_backend()
        )
        
        # Generate JWT
        token = jwt.encode(
            payload,
            private_key_obj,
            algorithm="RS256"
        )
        
        return token
    
    async def _get_installation_token(self, installation_id: str) -> Dict[str, Any]:
        """Get installation access token for GitHub App."""
        app_id = self.integration.config.custom_fields.get("github_app_id")
        private_key = self.integration.config.custom_fields.get("github_app_private_key")
        
        if not app_id or not private_key:
            raise AuthenticationError("GitHub App credentials not configured")
        
        # Generate JWT
        jwt_token = await self._generate_jwt_token(app_id, private_key)
        
        # Get installation token
        response = await self.http_client.post(
            f"{self.api_base_url}/app/installations/{installation_id}/access_tokens",
            headers={
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"Bearer {jwt_token}"
            }
        )
        
        if response.status_code != 201:
            raise AuthenticationError(f"Failed to get installation token: {response.text}")
        
        return response.json()
    
    async def _refresh_installation_token(self) -> OAuthToken:
        """Refresh GitHub App installation token."""
        installation_id = self.integration.config.custom_fields.get("github_app_installation_id")
        if not installation_id:
            raise AuthenticationError("GitHub App installation ID not configured")
        
        token_data = await self._get_installation_token(installation_id)
        
        expires_at = datetime.fromisoformat(token_data["expires_at"].replace("Z", "+00:00"))
        
        return OAuthToken(
            access_token=encrypt_token(token_data["token"], settings.encryption_key),
            refresh_token=None,
            token_type="Bearer",
            expires_at=expires_at,
            scope=" ".join(token_data.get("permissions", {}).keys()),
            encrypted=True,
        )
    
    async def test_connection(self) -> bool:
        """Test GitHub connection."""
        try:
            response = await self.make_api_request(
                "GET",
                f"{self.api_base_url}/user"
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    async def sync_data(self, job: SyncJob) -> Dict[str, Any]:
        """Sync data with GitHub."""
        results = {
            "total_processed": 0,
            "created": 0,
            "updated": 0,
            "errors": 0,
            "entity_results": {}
        }
        
        for entity_type in job.entity_types:
            try:
                if entity_type == "repositories":
                    entity_results = await self._sync_repositories(job)
                elif entity_type == "issues":
                    entity_results = await self._sync_issues(job)
                elif entity_type == "pull_requests":
                    entity_results = await self._sync_pull_requests(job)
                elif entity_type == "commits":
                    entity_results = await self._sync_commits(job)
                elif entity_type == "releases":
                    entity_results = await self._sync_releases(job)
                elif entity_type == "workflows":
                    entity_results = await self._sync_workflows(job)
                elif entity_type == "organizations":
                    entity_results = await self._sync_organizations(job)
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
    
    async def _sync_repositories(self, job: SyncJob) -> Dict[str, Any]:
        """Sync repositories with GitHub."""
        results = {"processed": 0, "created": 0, "updated": 0, "errors": 0}
        
        # Determine endpoint based on filters
        if job.filters.get("organization"):
            url = f"{self.api_base_url}/orgs/{job.filters['organization']}/repos"
        elif job.filters.get("user"):
            url = f"{self.api_base_url}/users/{job.filters['user']}/repos"
        else:
            url = f"{self.api_base_url}/user/repos"
        
        params = {
            "per_page": 100,
            "sort": "updated",
            "direction": "desc"
        }
        
        if job.filters.get("type"):
            params["type"] = job.filters["type"]  # all, owner, public, private, member
        
        async for repo in self.paginate_api_results("GET", url, params):
            try:
                results["processed"] += 1
                
                # Get additional repo details if needed
                if job.options.get("include_details", False):
                    repo_details = await self._get_repository_details(repo["full_name"])
                    repo.update(repo_details)
                
                # Process repository
                await self.log_sync_operation(
                    job.id,
                    "INFO",
                    "process_repository",
                    "repository",
                    f"Processed repository: {repo['full_name']}",
                    entity_id=str(repo["id"]),
                    details={
                        "github_id": repo["id"],
                        "full_name": repo["full_name"],
                        "private": repo["private"],
                        "stars": repo["stargazers_count"],
                        "language": repo["language"]
                    }
                )
                
            except Exception as e:
                results["errors"] += 1
                logger.error(f"Error processing repository: {e}")
        
        return results
    
    async def _sync_issues(self, job: SyncJob) -> Dict[str, Any]:
        """Sync issues with GitHub."""
        results = {"processed": 0, "created": 0, "updated": 0, "errors": 0}
        
        # Get repository from filters
        repo = job.filters.get("repository")
        if not repo:
            raise IntegrationError("Repository filter is required for syncing issues")
        
        url = f"{self.api_base_url}/repos/{repo}/issues"
        
        params = {
            "per_page": 100,
            "state": job.filters.get("state", "all"),  # open, closed, all
            "sort": "updated",
            "direction": "desc"
        }
        
        if job.filters.get("labels"):
            params["labels"] = job.filters["labels"]
        if job.filters.get("since"):
            params["since"] = job.filters["since"]
        
        async for issue in self.paginate_api_results("GET", url, params):
            try:
                # Skip pull requests (they appear in issues endpoint too)
                if "pull_request" in issue:
                    continue
                
                results["processed"] += 1
                
                # Process issue
                await self.log_sync_operation(
                    job.id,
                    "INFO",
                    "process_issue",
                    "issue",
                    f"Processed issue: #{issue['number']} - {issue['title']}",
                    entity_id=str(issue["id"]),
                    details={
                        "github_id": issue["id"],
                        "number": issue["number"],
                        "state": issue["state"],
                        "labels": [label["name"] for label in issue.get("labels", [])]
                    }
                )
                
            except Exception as e:
                results["errors"] += 1
                logger.error(f"Error processing issue: {e}")
        
        return results
    
    async def _sync_pull_requests(self, job: SyncJob) -> Dict[str, Any]:
        """Sync pull requests with GitHub."""
        results = {"processed": 0, "created": 0, "updated": 0, "errors": 0}
        
        repo = job.filters.get("repository")
        if not repo:
            raise IntegrationError("Repository filter is required for syncing pull requests")
        
        url = f"{self.api_base_url}/repos/{repo}/pulls"
        
        params = {
            "per_page": 100,
            "state": job.filters.get("state", "all"),  # open, closed, all
            "sort": "updated",
            "direction": "desc"
        }
        
        async for pr in self.paginate_api_results("GET", url, params):
            try:
                results["processed"] += 1
                
                # Get additional PR details if needed
                if job.options.get("include_details", False):
                    pr_details = await self._get_pull_request_details(repo, pr["number"])
                    pr.update(pr_details)
                
                # Process pull request
                await self.log_sync_operation(
                    job.id,
                    "INFO",
                    "process_pull_request",
                    "pull_request",
                    f"Processed PR: #{pr['number']} - {pr['title']}",
                    entity_id=str(pr["id"]),
                    details={
                        "github_id": pr["id"],
                        "number": pr["number"],
                        "state": pr["state"],
                        "merged": pr.get("merged", False),
                        "draft": pr.get("draft", False)
                    }
                )
                
            except Exception as e:
                results["errors"] += 1
                logger.error(f"Error processing pull request: {e}")
        
        return results
    
    async def _sync_commits(self, job: SyncJob) -> Dict[str, Any]:
        """Sync commits with GitHub."""
        results = {"processed": 0, "created": 0, "updated": 0, "errors": 0}
        
        repo = job.filters.get("repository")
        if not repo:
            raise IntegrationError("Repository filter is required for syncing commits")
        
        url = f"{self.api_base_url}/repos/{repo}/commits"
        
        params = {
            "per_page": 100
        }
        
        if job.filters.get("sha"):
            params["sha"] = job.filters["sha"]  # branch, tag, or SHA
        if job.filters.get("since"):
            params["since"] = job.filters["since"]
        if job.filters.get("until"):
            params["until"] = job.filters["until"]
        
        async for commit in self.paginate_api_results("GET", url, params):
            try:
                results["processed"] += 1
                
                # Process commit
                await self.log_sync_operation(
                    job.id,
                    "INFO",
                    "process_commit",
                    "commit",
                    f"Processed commit: {commit['sha'][:7]} - {commit['commit']['message'].split('\\n')[0]}",
                    entity_id=commit["sha"],
                    details={
                        "sha": commit["sha"],
                        "author": commit["commit"]["author"]["name"],
                        "date": commit["commit"]["author"]["date"]
                    }
                )
                
            except Exception as e:
                results["errors"] += 1
                logger.error(f"Error processing commit: {e}")
        
        return results
    
    async def _sync_releases(self, job: SyncJob) -> Dict[str, Any]:
        """Sync releases with GitHub."""
        results = {"processed": 0, "created": 0, "updated": 0, "errors": 0}
        
        repo = job.filters.get("repository")
        if not repo:
            raise IntegrationError("Repository filter is required for syncing releases")
        
        url = f"{self.api_base_url}/repos/{repo}/releases"
        
        params = {"per_page": 100}
        
        async for release in self.paginate_api_results("GET", url, params):
            try:
                results["processed"] += 1
                
                # Process release
                await self.log_sync_operation(
                    job.id,
                    "INFO",
                    "process_release",
                    "release",
                    f"Processed release: {release['tag_name']} - {release['name']}",
                    entity_id=str(release["id"]),
                    details={
                        "github_id": release["id"],
                        "tag_name": release["tag_name"],
                        "prerelease": release["prerelease"],
                        "draft": release["draft"]
                    }
                )
                
            except Exception as e:
                results["errors"] += 1
                logger.error(f"Error processing release: {e}")
        
        return results
    
    async def _sync_workflows(self, job: SyncJob) -> Dict[str, Any]:
        """Sync GitHub Actions workflows."""
        results = {"processed": 0, "created": 0, "updated": 0, "errors": 0}
        
        repo = job.filters.get("repository")
        if not repo:
            raise IntegrationError("Repository filter is required for syncing workflows")
        
        # Get workflows
        url = f"{self.api_base_url}/repos/{repo}/actions/workflows"
        params = {"per_page": 100}
        
        async for workflow in self.paginate_api_results("GET", url, params):
            try:
                results["processed"] += 1
                
                # Get workflow runs if requested
                if job.options.get("include_runs", False):
                    runs = await self._get_workflow_runs(repo, workflow["id"])
                    workflow["recent_runs"] = runs[:5]  # Last 5 runs
                
                # Process workflow
                await self.log_sync_operation(
                    job.id,
                    "INFO",
                    "process_workflow",
                    "workflow",
                    f"Processed workflow: {workflow['name']}",
                    entity_id=str(workflow["id"]),
                    details={
                        "github_id": workflow["id"],
                        "name": workflow["name"],
                        "state": workflow["state"],
                        "path": workflow["path"]
                    }
                )
                
            except Exception as e:
                results["errors"] += 1
                logger.error(f"Error processing workflow: {e}")
        
        return results
    
    async def _sync_organizations(self, job: SyncJob) -> Dict[str, Any]:
        """Sync organizations with GitHub."""
        results = {"processed": 0, "created": 0, "updated": 0, "errors": 0}
        
        # Get user's organizations
        url = f"{self.api_base_url}/user/orgs"
        params = {"per_page": 100}
        
        async for org in self.paginate_api_results("GET", url, params):
            try:
                results["processed"] += 1
                
                # Get org details
                org_details = await self._get_organization_details(org["login"])
                org.update(org_details)
                
                # Process organization
                await self.log_sync_operation(
                    job.id,
                    "INFO",
                    "process_organization",
                    "organization",
                    f"Processed organization: {org['login']}",
                    entity_id=str(org["id"]),
                    details={
                        "github_id": org["id"],
                        "login": org["login"],
                        "type": org.get("type"),
                        "public_repos": org.get("public_repos", 0)
                    }
                )
                
            except Exception as e:
                results["errors"] += 1
                logger.error(f"Error processing organization: {e}")
        
        return results
    
    async def _get_repository_details(self, repo_name: str) -> Dict[str, Any]:
        """Get detailed repository information."""
        response = await self.make_api_request(
            "GET",
            f"{self.api_base_url}/repos/{repo_name}"
        )
        return response.json() if response.status_code == 200 else {}
    
    async def _get_pull_request_details(self, repo: str, pr_number: int) -> Dict[str, Any]:
        """Get detailed pull request information."""
        response = await self.make_api_request(
            "GET",
            f"{self.api_base_url}/repos/{repo}/pulls/{pr_number}"
        )
        return response.json() if response.status_code == 200 else {}
    
    async def _get_workflow_runs(self, repo: str, workflow_id: int) -> List[Dict[str, Any]]:
        """Get workflow runs."""
        response = await self.make_api_request(
            "GET",
            f"{self.api_base_url}/repos/{repo}/actions/workflows/{workflow_id}/runs",
            params={"per_page": 10}
        )
        return response.json().get("workflow_runs", []) if response.status_code == 200 else []
    
    async def _get_organization_details(self, org_name: str) -> Dict[str, Any]:
        """Get detailed organization information."""
        response = await self.make_api_request(
            "GET",
            f"{self.api_base_url}/orgs/{org_name}"
        )
        return response.json() if response.status_code == 200 else {}
    
    async def create_issue(self, repo: str, issue_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new issue."""
        response = await self.make_api_request(
            "POST",
            f"{self.api_base_url}/repos/{repo}/issues",
            json=issue_data
        )
        
        if response.status_code != 201:
            raise IntegrationError(f"Failed to create issue: {response.text}")
        
        return response.json()
    
    async def create_pull_request(self, repo: str, pr_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new pull request."""
        response = await self.make_api_request(
            "POST",
            f"{self.api_base_url}/repos/{repo}/pulls",
            json=pr_data
        )
        
        if response.status_code != 201:
            raise IntegrationError(f"Failed to create pull request: {response.text}")
        
        return response.json()
    
    async def trigger_workflow(self, repo: str, workflow_id: str, ref: str, inputs: Optional[Dict[str, Any]] = None) -> bool:
        """Trigger a GitHub Actions workflow."""
        data = {
            "ref": ref,  # branch or tag
            "inputs": inputs or {}
        }
        
        response = await self.make_api_request(
            "POST",
            f"{self.api_base_url}/repos/{repo}/actions/workflows/{workflow_id}/dispatches",
            json=data
        )
        
        return response.status_code == 204
    
    async def handle_webhook(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Handle GitHub webhook."""
        logger.info(f"Handling GitHub webhook: {event_type}")
        
        # GitHub sends event type in X-GitHub-Event header
        if event_type == "push":
            await self._handle_push_event(payload)
        elif event_type == "pull_request":
            await self._handle_pull_request_event(payload)
        elif event_type == "issues":
            await self._handle_issues_event(payload)
        elif event_type == "release":
            await self._handle_release_event(payload)
        elif event_type == "workflow_run":
            await self._handle_workflow_run_event(payload)
        elif event_type == "repository":
            await self._handle_repository_event(payload)
        else:
            logger.warning(f"Unknown webhook event type: {event_type}")
    
    async def _handle_push_event(self, payload: Dict[str, Any]) -> None:
        """Handle push event."""
        repo = payload["repository"]["full_name"]
        ref = payload["ref"]
        commits = payload.get("commits", [])
        logger.info(f"Push to {repo} on {ref} with {len(commits)} commits")
        # Implement push event logic
    
    async def _handle_pull_request_event(self, payload: Dict[str, Any]) -> None:
        """Handle pull request event."""
        action = payload["action"]
        pr = payload["pull_request"]
        logger.info(f"Pull request {action}: #{pr['number']} - {pr['title']}")
        # Implement pull request event logic
    
    async def _handle_issues_event(self, payload: Dict[str, Any]) -> None:
        """Handle issues event."""
        action = payload["action"]
        issue = payload["issue"]
        logger.info(f"Issue {action}: #{issue['number']} - {issue['title']}")
        # Implement issues event logic
    
    async def _handle_release_event(self, payload: Dict[str, Any]) -> None:
        """Handle release event."""
        action = payload["action"]
        release = payload["release"]
        logger.info(f"Release {action}: {release['tag_name']} - {release['name']}")
        # Implement release event logic
    
    async def _handle_workflow_run_event(self, payload: Dict[str, Any]) -> None:
        """Handle workflow run event."""
        action = payload["action"]
        workflow_run = payload["workflow_run"]
        logger.info(f"Workflow run {action}: {workflow_run['name']} - {workflow_run['status']}")
        # Implement workflow run event logic
    
    async def _handle_repository_event(self, payload: Dict[str, Any]) -> None:
        """Handle repository event."""
        action = payload["action"]
        repo = payload["repository"]
        logger.info(f"Repository {action}: {repo['full_name']}")
        # Implement repository event logic
    
    def verify_webhook_signature(self, signature: str, payload: bytes) -> bool:
        """Verify GitHub webhook signature."""
        if not settings.webhook_secret:
            logger.warning("No webhook secret configured")
            return False
        
        # GitHub uses HMAC-SHA256 with 'sha256=' prefix
        if not signature.startswith('sha256='):
            return False
        
        expected_signature = 'sha256=' + hmac.new(
            settings.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    def extract_results_from_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract results from GitHub API response."""
        # GitHub returns different structures for different endpoints
        if isinstance(data, list):
            return data
        elif "items" in data:  # Search results
            return data["items"]
        elif "workflow_runs" in data:  # Workflow runs
            return data["workflow_runs"]
        elif "workflows" in data:  # Workflows
            return data["workflows"]
        return []
    
    def has_more_pages(self, data: Dict[str, Any], current_page: int) -> bool:
        """Check if there are more pages in GitHub response."""
        # GitHub uses Link header for pagination
        # This would need to be handled in the paginate_api_results method
        # by checking response headers
        return False
    
    async def search_code(self, query: str, **kwargs) -> AsyncIterator[Dict[str, Any]]:
        """Search code across GitHub."""
        url = f"{self.api_base_url}/search/code"
        params = {
            "q": query,
            "per_page": 100,
            **kwargs
        }
        
        async for result in self.paginate_api_results("GET", url, params):
            yield result
    
    async def get_rate_limit(self) -> Dict[str, Any]:
        """Get current rate limit status."""
        response = await self.make_api_request(
            "GET",
            f"{self.api_base_url}/rate_limit"
        )
        
        if response.status_code == 200:
            return response.json()
        return {}