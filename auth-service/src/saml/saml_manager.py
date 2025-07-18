"""SAML SSO Manager for handling authentication flow."""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import secrets
import json
from urllib.parse import urlencode, quote

from ..config import settings
from ..models.user import User
from ..models.oauth import OAuthConnection, OAuthProvider
from ..security.tokens import TokenService
from .saml_provider import SAMLProvider, SAMLProviderPresets
from .saml_utils import SAMLUtils


class SAMLManager:
    """Manages SAML SSO authentication flow."""
    
    def __init__(self, db_session, redis_client=None):
        self.db = db_session
        self.redis = redis_client
        self.token_service = TokenService()
        self.providers: Dict[str, SAMLProvider] = {}
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize configured SAML providers."""
        # Example: Initialize from settings
        if hasattr(settings, 'SAML_PROVIDERS'):
            for name, config in settings.SAML_PROVIDERS.items():
                self.add_provider(name, **config)
    
    def add_provider(
        self,
        name: str,
        entity_id: str = None,
        sso_url: str = None,
        slo_url: str = None,
        x509_cert: str = None,
        metadata_url: str = None,
        preset: str = None,
        **kwargs
    ) -> SAMLProvider:
        """Add a SAML provider."""
        if preset:
            # Use preset configuration
            preset_config = self._get_preset_config(preset, **kwargs)
            provider = SAMLProvider(**preset_config)
        else:
            # Manual configuration
            provider = SAMLProvider(
                entity_id=entity_id,
                sso_url=sso_url,
                slo_url=slo_url,
                x509_cert=x509_cert,
                metadata_url=metadata_url,
                **kwargs
            )
        
        provider.validate_config()
        self.providers[name] = provider
        return provider
    
    def _get_preset_config(self, preset: str, **kwargs) -> Dict[str, Any]:
        """Get preset configuration."""
        preset_lower = preset.lower()
        
        if preset_lower == 'okta':
            if 'domain' not in kwargs:
                raise ValueError("Okta preset requires 'domain' parameter")
            return SAMLProviderPresets.okta(kwargs['domain'])
        
        elif preset_lower == 'azure' or preset_lower == 'azure_ad':
            if 'tenant_id' not in kwargs:
                raise ValueError("Azure AD preset requires 'tenant_id' parameter")
            app_id = kwargs.get('app_id', 'default')
            return SAMLProviderPresets.azure_ad(kwargs['tenant_id'], app_id)
        
        elif preset_lower == 'google':
            domain = kwargs.get('domain', '')
            return SAMLProviderPresets.google(domain)
        
        elif preset_lower == 'onelogin':
            if 'subdomain' not in kwargs:
                raise ValueError("OneLogin preset requires 'subdomain' parameter")
            return SAMLProviderPresets.onelogin(kwargs['subdomain'])
        
        else:
            raise ValueError(f"Unknown preset: {preset}")
    
    def get_provider(self, name: str) -> Optional[SAMLProvider]:
        """Get SAML provider by name."""
        return self.providers.get(name)
    
    def list_providers(self) -> List[str]:
        """List available SAML providers."""
        return list(self.providers.keys())
    
    async def create_sso_request(
        self,
        provider_name: str,
        relay_state: Optional[str] = None,
        force_authn: bool = False,
        additional_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create SAML SSO request."""
        provider = self.get_provider(provider_name)
        if not provider:
            raise ValueError(f"Provider {provider_name} not configured")
        
        # Fetch metadata if needed
        if provider.metadata_url and not provider.x509_cert:
            await provider.fetch_metadata()
        
        # Generate SAML request
        sp_entity_id = settings.SAML_SP_ENTITY_ID or settings.FRONTEND_URL
        acs_url = f"{settings.API_URL}/auth/saml/callback/{provider_name}"
        
        authn_request = SAMLUtils.create_authn_request(
            sp_entity_id=sp_entity_id,
            idp_sso_url=provider.sso_url,
            acs_url=acs_url,
            name_id_format=provider.name_id_format,
            force_authn=force_authn
        )
        
        # Generate state for security
        state_data = {
            "provider": provider_name,
            "timestamp": datetime.utcnow().isoformat(),
            "nonce": secrets.token_urlsafe(16),
            "relay_state": relay_state
        }
        
        if additional_params:
            state_data["params"] = additional_params
        
        state = secrets.token_urlsafe(32)
        
        # Store state
        await self._store_state(state, state_data)
        
        # Prepare response based on binding
        if provider.binding.value.endswith('HTTP-Redirect'):
            # HTTP-Redirect binding
            encoded_request = SAMLUtils.encode_request(authn_request)
            params = {
                'SAMLRequest': encoded_request,
                'RelayState': state
            }
            
            sso_url = f"{provider.sso_url}?{urlencode(params)}"
            
            return {
                "url": sso_url,
                "method": "GET",
                "state": state
            }
        else:
            # HTTP-POST binding
            encoded_request = base64.b64encode(authn_request.encode()).decode()
            
            return {
                "url": provider.sso_url,
                "method": "POST",
                "saml_request": encoded_request,
                "relay_state": state,
                "state": state
            }
    
    async def process_sso_response(
        self,
        provider_name: str,
        saml_response: str,
        relay_state: str
    ) -> Dict[str, Any]:
        """Process SAML SSO response."""
        provider = self.get_provider(provider_name)
        if not provider:
            raise ValueError(f"Provider {provider_name} not configured")
        
        # Validate state
        state_data = await self._get_state(relay_state)
        if not state_data:
            raise ValueError("Invalid or expired state")
        
        # Check state data
        if state_data.get("provider") != provider_name:
            raise ValueError("Provider mismatch")
        
        # Check timestamp (allow 10 minutes)
        state_timestamp = datetime.fromisoformat(state_data["timestamp"])
        if datetime.utcnow() - state_timestamp > timedelta(minutes=10):
            raise ValueError("State expired")
        
        # Decode and parse response
        response_xml = SAMLUtils.decode_response(saml_response)
        
        # Verify signature if certificate available
        if provider.x509_cert:
            is_valid = SAMLUtils.verify_signature(response_xml, provider.x509_cert)
            if not is_valid:
                raise ValueError("Invalid SAML signature")
        
        # Parse assertion
        assertion_data = SAMLUtils.parse_assertion(response_xml)
        
        # Map attributes to user data
        user_attributes = SAMLUtils.map_attributes(
            assertion_data.get('attributes', {}),
            provider.attribute_mapping
        )
        
        # Add NameID
        user_attributes['saml_name_id'] = assertion_data.get('name_id')
        
        # Find or create user
        user = await self._find_or_create_user(
            provider_name,
            user_attributes,
            assertion_data
        )
        
        # Create tokens
        access_token = self.token_service.create_access_token(
            user_id=str(user.id),
            org_id=str(user.org_id) if hasattr(user, 'org_id') else None
        )
        
        refresh_token = self.token_service.create_refresh_token(
            user_id=str(user.id)
        )
        
        # Delete used state
        await self._delete_state(relay_state)
        
        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "session_index": assertion_data.get('session_index'),
            "relay_state": state_data.get('relay_state')
        }
    
    async def create_logout_request(
        self,
        provider_name: str,
        user_id: str,
        session_index: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create SAML logout request."""
        provider = self.get_provider(provider_name)
        if not provider:
            raise ValueError(f"Provider {provider_name} not configured")
        
        if not provider.slo_url:
            raise ValueError(f"Provider {provider_name} does not support logout")
        
        # Get user's SAML connection
        connection = await self.db.query(OAuthConnection).filter(
            OAuthConnection.user_id == user_id,
            OAuthConnection.provider == f"saml_{provider_name}"
        ).first()
        
        if not connection:
            raise ValueError("No SAML connection found for user")
        
        # Get NameID from connection metadata
        metadata = connection.metadata or {}
        name_id = metadata.get('saml_name_id')
        if not name_id:
            raise ValueError("No NameID found for user")
        
        # Create logout request
        sp_entity_id = settings.SAML_SP_ENTITY_ID or settings.FRONTEND_URL
        
        logout_request = SAMLUtils.create_logout_request(
            sp_entity_id=sp_entity_id,
            idp_slo_url=provider.slo_url,
            name_id=name_id,
            session_index=session_index or metadata.get('session_index'),
            name_id_format=provider.name_id_format
        )
        
        # Generate relay state
        relay_state = secrets.token_urlsafe(32)
        
        # Store state for logout
        state_data = {
            "provider": provider_name,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "type": "logout"
        }
        await self._store_state(relay_state, state_data)
        
        # Prepare request based on binding
        if provider.binding.value.endswith('HTTP-Redirect'):
            encoded_request = SAMLUtils.encode_request(logout_request)
            params = {
                'SAMLRequest': encoded_request,
                'RelayState': relay_state
            }
            
            logout_url = f"{provider.slo_url}?{urlencode(params)}"
            
            return {
                "url": logout_url,
                "method": "GET"
            }
        else:
            encoded_request = base64.b64encode(logout_request.encode()).decode()
            
            return {
                "url": provider.slo_url,
                "method": "POST",
                "saml_request": encoded_request,
                "relay_state": relay_state
            }
    
    async def _find_or_create_user(
        self,
        provider_name: str,
        user_attributes: Dict[str, Any],
        assertion_data: Dict[str, Any]
    ) -> User:
        """Find or create user from SAML attributes."""
        # Try to find by email
        email = user_attributes.get('email')
        if not email:
            raise ValueError("Email not found in SAML attributes")
        
        user = await self.db.query(User).filter(
            User.email == email
        ).first()
        
        if not user:
            # Create new user
            user = User(
                email=email,
                username=user_attributes.get('username', email.split('@')[0]),
                full_name=user_attributes.get('full_name', ''),
                is_email_verified=True,  # Trust SAML IdP
                status='active',
                metadata={
                    'source': 'saml',
                    'provider': provider_name
                }
            )
            self.db.add(user)
            await self.db.commit()
        
        # Update or create OAuth connection
        connection = await self.db.query(OAuthConnection).filter(
            OAuthConnection.user_id == user.id,
            OAuthConnection.provider == f"saml_{provider_name}"
        ).first()
        
        if not connection:
            connection = OAuthConnection(
                user_id=user.id,
                provider=f"saml_{provider_name}",
                provider_user_id=assertion_data.get('name_id'),
                metadata={
                    'saml_name_id': assertion_data.get('name_id'),
                    'session_index': assertion_data.get('session_index'),
                    'attributes': user_attributes
                }
            )
            self.db.add(connection)
        else:
            # Update metadata
            connection.metadata = {
                'saml_name_id': assertion_data.get('name_id'),
                'session_index': assertion_data.get('session_index'),
                'attributes': user_attributes,
                'last_login': datetime.utcnow().isoformat()
            }
            connection.last_used_at = datetime.utcnow()
        
        await self.db.commit()
        
        return user
    
    async def _store_state(self, state: str, data: Dict[str, Any]):
        """Store SAML state data."""
        if self.redis:
            await self.redis.setex(
                f"saml_state:{state}",
                600,  # 10 minutes
                json.dumps(data)
            )
        else:
            # In-memory fallback (not recommended for production)
            if not hasattr(self, '_state_store'):
                self._state_store = {}
            self._state_store[state] = {
                "data": data,
                "expires": datetime.utcnow() + timedelta(minutes=10)
            }
    
    async def _get_state(self, state: str) -> Optional[Dict[str, Any]]:
        """Get SAML state data."""
        if self.redis:
            data = await self.redis.get(f"saml_state:{state}")
            return json.loads(data) if data else None
        else:
            # In-memory fallback
            if hasattr(self, '_state_store') and state in self._state_store:
                stored = self._state_store[state]
                if stored["expires"] > datetime.utcnow():
                    return stored["data"]
                else:
                    del self._state_store[state]
            return None
    
    async def _delete_state(self, state: str):
        """Delete SAML state data."""
        if self.redis:
            await self.redis.delete(f"saml_state:{state}")
        elif hasattr(self, '_state_store') and state in self._state_store:
            del self._state_store[state]