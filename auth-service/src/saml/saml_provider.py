"""SAML Identity Provider configuration and metadata."""

from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
import xml.etree.ElementTree as ET
from urllib.parse import urlparse


class SAMLBinding(str, Enum):
    """SAML binding types."""
    HTTP_POST = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
    HTTP_REDIRECT = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
    SOAP = "urn:oasis:names:tc:SAML:2.0:bindings:SOAP"


class SAMLProvider:
    """SAML Identity Provider configuration."""
    
    def __init__(
        self,
        entity_id: str,
        sso_url: str,
        slo_url: Optional[str] = None,
        x509_cert: Optional[str] = None,
        metadata_url: Optional[str] = None,
        name_id_format: str = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        binding: SAMLBinding = SAMLBinding.HTTP_POST,
        attribute_mapping: Optional[Dict[str, str]] = None
    ):
        self.entity_id = entity_id
        self.sso_url = sso_url
        self.slo_url = slo_url
        self.x509_cert = x509_cert
        self.metadata_url = metadata_url
        self.name_id_format = name_id_format
        self.binding = binding
        self.attribute_mapping = attribute_mapping or self._default_attribute_mapping()
        
        # Metadata cache
        self._metadata = None
        self._metadata_fetched_at = None
    
    def _default_attribute_mapping(self) -> Dict[str, str]:
        """Default SAML attribute mappings."""
        return {
            # SAML attribute -> User field
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress": "email",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name": "full_name",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname": "first_name",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname": "last_name",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier": "saml_name_id",
            
            # Alternative mappings
            "email": "email",
            "mail": "email",
            "emailAddress": "email",
            "name": "full_name",
            "displayName": "full_name",
            "givenName": "first_name",
            "sn": "last_name",
            "surname": "last_name",
            "uid": "username",
            "user": "username"
        }
    
    async def fetch_metadata(self, force: bool = False) -> Optional[str]:
        """Fetch IdP metadata from URL."""
        if not self.metadata_url:
            return None
        
        # Check cache
        if not force and self._metadata and self._metadata_fetched_at:
            # Cache for 24 hours
            if (datetime.utcnow() - self._metadata_fetched_at).total_seconds() < 86400:
                return self._metadata
        
        # Fetch metadata
        import httpx
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(self.metadata_url, timeout=30)
                response.raise_for_status()
                
                self._metadata = response.text
                self._metadata_fetched_at = datetime.utcnow()
                
                # Parse and update configuration
                self._parse_metadata(self._metadata)
                
                return self._metadata
            except Exception as e:
                raise ValueError(f"Failed to fetch metadata: {str(e)}")
    
    def _parse_metadata(self, metadata_xml: str):
        """Parse IdP metadata and update configuration."""
        try:
            root = ET.fromstring(metadata_xml)
            
            # Remove namespace for easier parsing
            for elem in root.getiterator():
                if '}' in elem.tag:
                    elem.tag = elem.tag.split('}', 1)[1]
            
            # Update entity ID
            if 'entityID' in root.attrib:
                self.entity_id = root.attrib['entityID']
            
            # Find SSO service
            for sso in root.findall(".//SingleSignOnService"):
                if sso.attrib.get('Binding') == self.binding.value:
                    self.sso_url = sso.attrib['Location']
                    break
            
            # Find SLO service
            for slo in root.findall(".//SingleLogoutService"):
                if slo.attrib.get('Binding') == self.binding.value:
                    self.slo_url = slo.attrib['Location']
                    break
            
            # Extract certificate
            cert_elem = root.find(".//X509Certificate")
            if cert_elem is not None and cert_elem.text:
                # Clean certificate
                cert = cert_elem.text.strip()
                cert = cert.replace('\n', '').replace('\r', '')
                self.x509_cert = f"-----BEGIN CERTIFICATE-----\n{cert}\n-----END CERTIFICATE-----"
            
        except Exception as e:
            raise ValueError(f"Failed to parse metadata: {str(e)}")
    
    def get_sso_url(self, relay_state: Optional[str] = None) -> str:
        """Get SSO URL with optional relay state."""
        url = self.sso_url
        if relay_state and self.binding == SAMLBinding.HTTP_REDIRECT:
            # Add relay state to URL for redirect binding
            separator = '&' if '?' in url else '?'
            url = f"{url}{separator}RelayState={relay_state}"
        return url
    
    def validate_config(self) -> bool:
        """Validate provider configuration."""
        if not self.entity_id:
            raise ValueError("Entity ID is required")
        
        if not self.sso_url:
            raise ValueError("SSO URL is required")
        
        # Validate URLs
        try:
            urlparse(self.sso_url)
            if self.slo_url:
                urlparse(self.slo_url)
            if self.metadata_url:
                urlparse(self.metadata_url)
        except Exception:
            raise ValueError("Invalid URL format")
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_id": self.entity_id,
            "sso_url": self.sso_url,
            "slo_url": self.slo_url,
            "has_certificate": bool(self.x509_cert),
            "metadata_url": self.metadata_url,
            "name_id_format": self.name_id_format,
            "binding": self.binding.value,
            "attribute_mapping": self.attribute_mapping
        }


class SAMLProviderPresets:
    """Preset configurations for common SAML providers."""
    
    @staticmethod
    def okta(domain: str) -> Dict[str, Any]:
        """Okta SAML configuration."""
        return {
            "entity_id": f"http://www.okta.com/{domain}",
            "metadata_url": f"https://{domain}/app/appid/sso/saml/metadata",
            "name_id_format": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            "binding": SAMLBinding.HTTP_POST
        }
    
    @staticmethod
    def azure_ad(tenant_id: str, app_id: str) -> Dict[str, Any]:
        """Azure AD SAML configuration."""
        return {
            "entity_id": f"https://sts.windows.net/{tenant_id}/",
            "metadata_url": f"https://login.microsoftonline.com/{tenant_id}/federationmetadata/2007-06/federationmetadata.xml",
            "name_id_format": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            "binding": SAMLBinding.HTTP_POST,
            "attribute_mapping": {
                "http://schemas.microsoft.com/identity/claims/displayname": "full_name",
                "http://schemas.microsoft.com/identity/claims/objectidentifier": "azure_object_id",
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress": "email",
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname": "first_name",
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname": "last_name"
            }
        }
    
    @staticmethod
    def google(domain: str) -> Dict[str, Any]:
        """Google Workspace SAML configuration."""
        return {
            "entity_id": "google.com",
            "sso_url": "https://accounts.google.com/o/saml2/idp",
            "metadata_url": "https://accounts.google.com/o/saml2/metadata",
            "name_id_format": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            "binding": SAMLBinding.HTTP_POST
        }
    
    @staticmethod
    def onelogin(subdomain: str) -> Dict[str, Any]:
        """OneLogin SAML configuration."""
        return {
            "entity_id": f"https://app.onelogin.com/saml/metadata/{subdomain}",
            "metadata_url": f"https://{subdomain}.onelogin.com/saml/metadata/apps/",
            "name_id_format": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            "binding": SAMLBinding.HTTP_POST
        }