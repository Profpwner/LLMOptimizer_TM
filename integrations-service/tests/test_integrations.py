"""Integration tests for all integrations."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from app.models import Integration, IntegrationType, IntegrationStatus, OAuthToken, SyncJob, SyncDirection
from app.integrations import HubSpotIntegration, SalesforceIntegration, WordPressIntegration, GitHubIntegration
from app.services import transformation_service, FieldMapping, DataType, TransformationType


@pytest.fixture
def mock_integration():
    """Create a mock integration."""
    return Integration(
        id="test-integration-id",
        user_id="test-user",
        organization_id="test-org",
        integration_type=IntegrationType.HUBSPOT,
        name="Test Integration",
        status=IntegrationStatus.CONNECTED,
        oauth_token=OAuthToken(
            access_token="test-token",
            refresh_token="test-refresh-token",
            token_type="Bearer",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            encrypted=False
        )
    )


@pytest.fixture
def mock_sync_job():
    """Create a mock sync job."""
    return SyncJob(
        id="test-job-id",
        integration_id="test-integration-id",
        user_id="test-user",
        organization_id="test-org",
        entity_types=["contacts", "companies"],
        direction=SyncDirection.INBOUND,
        filters={"status": "active"},
        options={"include_details": True}
    )


class TestHubSpotIntegration:
    """Test HubSpot integration."""
    
    @pytest.mark.asyncio
    async def test_test_connection(self, mock_integration):
        """Test connection testing."""
        integration = HubSpotIntegration(mock_integration)
        
        with patch.object(integration, 'make_api_request') as mock_request:
            mock_request.return_value = Mock(status_code=200)
            
            result = await integration.test_connection()
            assert result is True
            
            mock_request.assert_called_once_with(
                "GET",
                "https://api.hubapi.com/account-info/v3/details"
            )
    
    @pytest.mark.asyncio
    async def test_sync_contacts(self, mock_integration, mock_sync_job):
        """Test syncing contacts."""
        integration = HubSpotIntegration(mock_integration)
        mock_sync_job.entity_types = ["contacts"]
        
        # Mock API response
        mock_contacts = [
            {
                "id": "1",
                "properties": {
                    "email": "test@example.com",
                    "firstname": "John",
                    "lastname": "Doe"
                }
            }
        ]
        
        with patch.object(integration, 'paginate_api_results', AsyncMock(return_value=mock_contacts.__iter__())):
            with patch.object(integration, 'log_sync_operation', AsyncMock()):
                results = await integration.sync_data(mock_sync_job)
                
                assert results["total_processed"] == 1
                assert results["entity_results"]["contacts"]["processed"] == 1


class TestSalesforceIntegration:
    """Test Salesforce integration."""
    
    @pytest.mark.asyncio
    async def test_soql_query(self, mock_integration):
        """Test SOQL query execution."""
        mock_integration.integration_type = IntegrationType.SALESFORCE
        mock_integration.config.api_endpoint = "https://test.salesforce.com"
        
        integration = SalesforceIntegration(mock_integration)
        
        # Mock API response
        mock_response = {
            "done": True,
            "records": [
                {"Id": "001xxx", "Name": "Test Lead", "Email": "lead@example.com"}
            ]
        }
        
        with patch.object(integration, 'make_api_request') as mock_request:
            mock_request.return_value = Mock(
                status_code=200,
                json=lambda: mock_response
            )
            
            records = []
            async for record in integration._query_salesforce("SELECT Id, Name FROM Lead"):
                records.append(record)
            
            assert len(records) == 1
            assert records[0]["Name"] == "Test Lead"


class TestWordPressIntegration:
    """Test WordPress integration."""
    
    @pytest.mark.asyncio
    async def test_create_post(self, mock_integration):
        """Test creating a WordPress post."""
        mock_integration.integration_type = IntegrationType.WORDPRESS
        mock_integration.config.api_endpoint = "https://test.wordpress.com"
        mock_integration.api_key = "test-api-key"
        
        integration = WordPressIntegration(mock_integration)
        
        post_data = {
            "title": "Test Post",
            "content": "This is a test post",
            "status": "draft"
        }
        
        with patch.object(integration, 'make_api_request') as mock_request:
            mock_request.return_value = Mock(
                status_code=201,
                json=lambda: {"id": 123, **post_data}
            )
            
            result = await integration.create_post(post_data)
            assert result["id"] == 123
            assert result["title"] == "Test Post"


class TestGitHubIntegration:
    """Test GitHub integration."""
    
    @pytest.mark.asyncio
    async def test_webhook_signature_verification(self, mock_integration):
        """Test GitHub webhook signature verification."""
        mock_integration.integration_type = IntegrationType.GITHUB
        integration = GitHubIntegration(mock_integration)
        
        payload = b'{"action": "opened", "number": 1}'
        secret = "test-secret"
        
        with patch('app.core.config.get_settings') as mock_settings:
            mock_settings.return_value.webhook_secret = secret
            
            # Generate valid signature
            import hmac
            import hashlib
            signature = 'sha256=' + hmac.new(
                secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Test valid signature
            assert integration.verify_webhook_signature(signature, payload) is True
            
            # Test invalid signature
            assert integration.verify_webhook_signature("sha256=invalid", payload) is False


class TestDataTransformation:
    """Test data transformation service."""
    
    @pytest.mark.asyncio
    async def test_field_mapping(self):
        """Test field mapping transformation."""
        source_data = {
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john.doe@example.com",
            "phoneNumber": "1234567890",
            "companyName": "Acme Corp"
        }
        
        mappings = [
            FieldMapping(
                source_field="firstName",
                target_field="first_name",
                data_type=DataType.STRING
            ),
            FieldMapping(
                source_field="lastName",
                target_field="last_name",
                data_type=DataType.STRING
            ),
            FieldMapping(
                source_field="emailAddress",
                target_field="email",
                transformation_type=TransformationType.FUNCTION,
                transformation_config={"function": "email_normalize"},
                data_type=DataType.STRING
            ),
            FieldMapping(
                source_field="phoneNumber",
                target_field="phone",
                transformation_type=TransformationType.FUNCTION,
                transformation_config={"function": "phone_normalize"},
                data_type=DataType.STRING
            ),
            FieldMapping(
                source_field="companyName",
                target_field="company",
                data_type=DataType.STRING
            )
        ]
        
        result = await transformation_service.transform_data(source_data, mappings)
        
        assert result["first_name"] == "John"
        assert result["last_name"] == "Doe"
        assert result["email"] == "john.doe@example.com"
        assert result["phone"] == "(123) 456-7890"
        assert result["company"] == "Acme Corp"
    
    @pytest.mark.asyncio
    async def test_conditional_transformation(self):
        """Test conditional transformation."""
        source_data = {
            "status": "active",
            "score": 85
        }
        
        mapping = FieldMapping(
            source_field="score",
            target_field="grade",
            transformation_type=TransformationType.CONDITIONAL,
            transformation_config={
                "conditions": [
                    {"if": {"operator": "greater_than", "value": 90}, "then": "A"},
                    {"if": {"operator": "greater_than", "value": 80}, "then": "B"},
                    {"if": {"operator": "greater_than", "value": 70}, "then": "C"}
                ],
                "else": "F"
            }
        )
        
        result = await transformation_service.transform_data(source_data, [mapping])
        assert result["grade"] == "B"


@pytest.mark.asyncio
async def test_integration_workflow():
    """Test a complete integration workflow."""
    # This test demonstrates how different integrations work together
    
    # 1. Create integrations
    hubspot_integration = Integration(
        id="hubspot-1",
        user_id="user-1",
        organization_id="org-1",
        integration_type=IntegrationType.HUBSPOT,
        name="HubSpot CRM",
        status=IntegrationStatus.CONNECTED
    )
    
    salesforce_integration = Integration(
        id="salesforce-1",
        user_id="user-1",
        organization_id="org-1",
        integration_type=IntegrationType.SALESFORCE,
        name="Salesforce",
        status=IntegrationStatus.CONNECTED
    )
    
    # 2. Define field mappings for data transformation
    hubspot_to_salesforce_mappings = [
        FieldMapping(
            source_field="properties.firstname",
            target_field="FirstName",
            data_type=DataType.STRING
        ),
        FieldMapping(
            source_field="properties.lastname",
            target_field="LastName",
            data_type=DataType.STRING
        ),
        FieldMapping(
            source_field="properties.email",
            target_field="Email",
            data_type=DataType.STRING
        ),
        FieldMapping(
            source_field="properties.company",
            target_field="Company",
            data_type=DataType.STRING
        )
    ]
    
    # 3. Mock data from HubSpot
    hubspot_contact = {
        "id": "123",
        "properties": {
            "firstname": "Jane",
            "lastname": "Smith",
            "email": "jane.smith@example.com",
            "company": "Tech Corp"
        }
    }
    
    # 4. Transform data
    salesforce_lead = await transformation_service.transform_data(
        hubspot_contact,
        hubspot_to_salesforce_mappings
    )
    
    assert salesforce_lead["FirstName"] == "Jane"
    assert salesforce_lead["LastName"] == "Smith"
    assert salesforce_lead["Email"] == "jane.smith@example.com"
    assert salesforce_lead["Company"] == "Tech Corp"