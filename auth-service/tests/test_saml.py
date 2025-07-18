"""Tests for SAML SSO functionality."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
import base64
import zlib
from lxml import etree
from urllib.parse import urlparse, parse_qs

from src.saml.saml_provider import SAMLProvider, get_preset_provider
from src.saml.saml_utils import SAMLUtils
from src.saml.saml_manager import SAMLManager
from src.models.user import User, UserStatus
from src.models.saml import SAMLAccount


class TestSAMLProvider:
    """Test SAML provider functionality."""
    
    def test_saml_provider_initialization(self):
        """Test SAML provider initialization."""
        provider = SAMLProvider(
            entity_id="http://localhost:8000",
            sso_url="https://idp.example.com/sso",
            slo_url="https://idp.example.com/slo",
            x509_cert="-----BEGIN CERTIFICATE-----\nMIITest...\n-----END CERTIFICATE-----",
            attribute_mapping={
                "email": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
                "name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name"
            }
        )
        
        assert provider.entity_id == "http://localhost:8000"
        assert provider.sso_url == "https://idp.example.com/sso"
        assert provider.slo_url == "https://idp.example.com/slo"
        assert "email" in provider.attribute_mapping
    
    def test_preset_providers(self):
        """Test preset SAML provider configurations."""
        # Test Okta preset
        okta_provider = get_preset_provider("okta", "test.okta.com")
        assert okta_provider.entity_id == "http://www.okta.com/test"
        assert "test.okta.com" in okta_provider.sso_url
        
        # Test Azure AD preset
        azure_provider = get_preset_provider("azure", tenant_id="test-tenant")
        assert "login.microsoftonline.com/test-tenant" in azure_provider.sso_url
        
        # Test Google Workspace preset
        google_provider = get_preset_provider("google", domain="example.com")
        assert google_provider.entity_id == "google.com"
        assert "accounts.google.com" in google_provider.sso_url


class TestSAMLUtils:
    """Test SAML utility functions."""
    
    def test_create_authn_request(self):
        """Test SAML authentication request creation."""
        request_xml, request_id = SAMLUtils.create_authn_request(
            sp_entity_id="http://localhost:8000",
            idp_sso_url="https://idp.example.com/sso",
            acs_url="http://localhost:8000/saml/acs",
            name_id_format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
        )
        
        assert request_xml is not None
        assert request_id is not None
        assert len(request_id) > 0
        
        # Parse and validate XML
        root = etree.fromstring(request_xml.encode())
        assert root.get("ID") == request_id
        assert root.get("Version") == "2.0"
        assert root.get("Destination") == "https://idp.example.com/sso"
    
    def test_encode_decode_request(self):
        """Test SAML request encoding and decoding."""
        original_xml = "<samlp:AuthnRequest>Test Request</samlp:AuthnRequest>"
        
        # Encode
        encoded = SAMLUtils.encode_request(original_xml)
        assert isinstance(encoded, str)
        
        # Decode
        decoded = SAMLUtils.decode_request(encoded)
        assert decoded == original_xml
    
    def test_parse_saml_response(self):
        """Test parsing SAML response."""
        # Create mock SAML response
        response_xml = """
        <samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                        xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                        ID="response123" Version="2.0" IssueInstant="2024-01-01T00:00:00Z"
                        Destination="http://localhost:8000/saml/acs">
            <saml:Issuer>https://idp.example.com</saml:Issuer>
            <samlp:Status>
                <samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/>
            </samlp:Status>
            <saml:Assertion ID="assertion123" Version="2.0">
                <saml:Subject>
                    <saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">
                        user@example.com
                    </saml:NameID>
                </saml:Subject>
                <saml:AttributeStatement>
                    <saml:Attribute Name="email">
                        <saml:AttributeValue>user@example.com</saml:AttributeValue>
                    </saml:Attribute>
                    <saml:Attribute Name="name">
                        <saml:AttributeValue>Test User</saml:AttributeValue>
                    </saml:Attribute>
                </saml:AttributeStatement>
            </saml:Assertion>
        </samlp:Response>
        """
        
        encoded_response = base64.b64encode(response_xml.encode()).decode()
        parsed_data = SAMLUtils.parse_saml_response(encoded_response)
        
        assert parsed_data["success"] is True
        assert parsed_data["name_id"] == "user@example.com"
        assert parsed_data["attributes"]["email"] == ["user@example.com"]
        assert parsed_data["attributes"]["name"] == ["Test User"]
    
    def test_verify_signature_mock(self):
        """Test signature verification (mocked)."""
        response_xml = "<samlp:Response>Test</samlp:Response>"
        cert = "-----BEGIN CERTIFICATE-----\nMIITest...\n-----END CERTIFICATE-----"
        
        # Mock xmlsec verification
        with patch("xmlsec.SignatureContext") as mock_context:
            mock_context.return_value.verify.return_value = None  # No exception means valid
            
            result = SAMLUtils.verify_signature(response_xml, cert)
            assert result is True
    
    def test_extract_attributes(self):
        """Test attribute extraction with mapping."""
        attributes = {
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress": ["user@example.com"],
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name": ["Test User"],
            "department": ["Engineering"]
        }
        
        mapping = {
            "email": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
            "name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
            "dept": "department"
        }
        
        extracted = SAMLUtils.extract_attributes(attributes, mapping)
        
        assert extracted["email"] == "user@example.com"
        assert extracted["name"] == "Test User"
        assert extracted["dept"] == "Engineering"


class TestSAMLManager:
    """Test SAML manager functionality."""
    
    @pytest.fixture
    def saml_manager(self, db, redis_client):
        """Create SAML manager instance."""
        manager = SAMLManager(db, redis_client)
        manager.providers = {
            "okta": SAMLProvider(
                entity_id="http://localhost:8000",
                sso_url="https://test.okta.com/sso/saml",
                x509_cert="test-cert"
            )
        }
        return manager
    
    @pytest.mark.asyncio
    async def test_initiate_sso(self, saml_manager: SAMLManager):
        """Test initiating SAML SSO."""
        provider_name = "okta"
        
        sso_url, relay_state = await saml_manager.initiate_sso(
            provider_name,
            relay_state="http://localhost:8000/dashboard"
        )
        
        assert sso_url is not None
        assert relay_state is not None
        
        # Parse SSO URL
        parsed_url = urlparse(sso_url)
        query_params = parse_qs(parsed_url.query)
        
        assert "SAMLRequest" in query_params
        assert "RelayState" in query_params
        
        # Verify request ID is stored
        stored_data = await saml_manager.redis.get(f"saml_request:{relay_state}")
        assert stored_data is not None
    
    @pytest.mark.asyncio
    async def test_process_sso_response_new_user(
        self,
        saml_manager: SAMLManager,
        db
    ):
        """Test processing SAML response for new user."""
        provider_name = "okta"
        relay_state = "test-relay-state"
        
        # Store request data
        request_data = {
            "provider": provider_name,
            "request_id": "test-request-id",
            "timestamp": datetime.utcnow().isoformat()
        }
        await saml_manager.redis.setex(
            f"saml_request:{relay_state}",
            600,
            json.dumps(request_data)
        )
        
        # Mock SAML response
        mock_saml_data = {
            "success": True,
            "name_id": "user@example.com",
            "attributes": {
                "email": ["user@example.com"],
                "name": ["SAML User"],
                "department": ["IT"]
            },
            "session_index": "session123"
        }
        
        with patch.object(SAMLUtils, "parse_saml_response", return_value=mock_saml_data):
            with patch.object(SAMLUtils, "verify_signature", return_value=True):
                user, session_data = await saml_manager.process_sso_response(
                    provider_name,
                    "mock-saml-response",
                    relay_state
                )
        
        assert user is not None
        assert user.email == "user@example.com"
        assert user.full_name == "SAML User"
        assert user.status == UserStatus.ACTIVE
        assert user.email_verified is True
        
        # Check SAML account was created
        saml_account = await db.query(SAMLAccount).filter(
            SAMLAccount.user_id == user.id
        ).first()
        
        assert saml_account is not None
        assert saml_account.provider == provider_name
        assert saml_account.name_id == "user@example.com"
    
    @pytest.mark.asyncio
    async def test_process_sso_response_existing_user(
        self,
        saml_manager: SAMLManager,
        test_user: User,
        db
    ):
        """Test processing SAML response for existing user."""
        provider_name = "okta"
        relay_state = "test-relay-state"
        
        # Create existing SAML account
        saml_account = SAMLAccount(
            user_id=test_user.id,
            provider=provider_name,
            name_id=test_user.email,
            attributes={"email": test_user.email}
        )
        db.add(saml_account)
        await db.commit()
        
        # Store request data
        request_data = {
            "provider": provider_name,
            "request_id": "test-request-id",
            "timestamp": datetime.utcnow().isoformat()
        }
        await saml_manager.redis.setex(
            f"saml_request:{relay_state}",
            600,
            json.dumps(request_data)
        )
        
        # Mock SAML response
        mock_saml_data = {
            "success": True,
            "name_id": test_user.email,
            "attributes": {
                "email": [test_user.email],
                "name": [test_user.full_name]
            },
            "session_index": "session123"
        }
        
        with patch.object(SAMLUtils, "parse_saml_response", return_value=mock_saml_data):
            with patch.object(SAMLUtils, "verify_signature", return_value=True):
                user, session_data = await saml_manager.process_sso_response(
                    provider_name,
                    "mock-saml-response",
                    relay_state
                )
        
        assert user.id == test_user.id
        assert session_data["session_index"] == "session123"
    
    @pytest.mark.asyncio
    async def test_process_sso_response_invalid_signature(
        self,
        saml_manager: SAMLManager
    ):
        """Test processing SAML response with invalid signature."""
        provider_name = "okta"
        relay_state = "test-relay-state"
        
        # Store request data
        request_data = {
            "provider": provider_name,
            "request_id": "test-request-id",
            "timestamp": datetime.utcnow().isoformat()
        }
        await saml_manager.redis.setex(
            f"saml_request:{relay_state}",
            600,
            json.dumps(request_data)
        )
        
        with patch.object(SAMLUtils, "verify_signature", return_value=False):
            with pytest.raises(ValueError, match="Invalid SAML signature"):
                await saml_manager.process_sso_response(
                    provider_name,
                    "mock-saml-response",
                    relay_state
                )
    
    @pytest.mark.asyncio
    async def test_initiate_slo(self, saml_manager: SAMLManager, test_user: User, db):
        """Test initiating SAML logout."""
        provider_name = "okta"
        
        # Create SAML account with session
        saml_account = SAMLAccount(
            user_id=test_user.id,
            provider=provider_name,
            name_id=test_user.email,
            session_index="session123"
        )
        db.add(saml_account)
        await db.commit()
        
        slo_url = await saml_manager.initiate_slo(
            test_user,
            provider_name,
            "session123"
        )
        
        assert slo_url is not None
        
        # Parse SLO URL
        parsed_url = urlparse(slo_url)
        query_params = parse_qs(parsed_url.query)
        
        assert "SAMLRequest" in query_params


class TestSAMLIntegration:
    """Integration tests for SAML functionality."""
    
    @pytest.mark.asyncio
    async def test_saml_sso_initiation(self, test_client):
        """Test initiating SAML SSO flow."""
        response = test_client.get(
            "/api/v1/auth/saml/okta/login",
            params={"relay_state": "http://localhost:8000/dashboard"}
        )
        
        assert response.status_code == 307  # Redirect
        location = response.headers["location"]
        
        # Verify redirect to IdP
        assert "okta.com" in location or "saml" in location
        
        # Parse redirect URL
        parsed_url = urlparse(location)
        query_params = parse_qs(parsed_url.query)
        
        assert "SAMLRequest" in query_params
        assert "RelayState" in query_params
    
    @pytest.mark.asyncio
    async def test_saml_acs_endpoint(self, test_client, redis_client):
        """Test SAML Assertion Consumer Service endpoint."""
        provider_name = "okta"
        relay_state = "test-relay-123"
        
        # Store request data
        request_data = {
            "provider": provider_name,
            "request_id": "req123",
            "timestamp": datetime.utcnow().isoformat()
        }
        await redis_client.setex(
            f"saml_request:{relay_state}",
            600,
            json.dumps(request_data)
        )
        
        # Mock SAML response
        with patch("src.saml.saml_utils.SAMLUtils.parse_saml_response") as mock_parse:
            mock_parse.return_value = {
                "success": True,
                "name_id": "saml@example.com",
                "attributes": {
                    "email": ["saml@example.com"],
                    "name": ["SAML User"]
                }
            }
            
            with patch("src.saml.saml_utils.SAMLUtils.verify_signature") as mock_verify:
                mock_verify.return_value = True
                
                response = test_client.post(
                    f"/api/v1/auth/saml/{provider_name}/acs",
                    data={
                        "SAMLResponse": base64.b64encode(b"mock-response").decode(),
                        "RelayState": relay_state
                    }
                )
                
                assert response.status_code == 200
                data = response.json()
                
                assert "access_token" in data
                assert "token_type" in data
                assert data["token_type"] == "bearer"