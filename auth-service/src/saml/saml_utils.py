"""SAML utility functions."""

import base64
import zlib
from datetime import datetime, timedelta
import secrets
from typing import Dict, Any, Optional
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlencode
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
import xmlsec


class SAMLUtils:
    """Utility functions for SAML operations."""
    
    SAML_NAMESPACES = {
        'saml': 'urn:oasis:names:tc:SAML:2.0:assertion',
        'samlp': 'urn:oasis:names:tc:SAML:2.0:protocol',
        'ds': 'http://www.w3.org/2000/09/xmldsig#',
        'xenc': 'http://www.w3.org/2001/04/xmlenc#'
    }
    
    @staticmethod
    def generate_id() -> str:
        """Generate unique SAML ID."""
        return f"_{secrets.token_hex(16)}"
    
    @staticmethod
    def get_timestamp(delta_seconds: int = 0) -> str:
        """Get ISO timestamp for SAML."""
        timestamp = datetime.utcnow() + timedelta(seconds=delta_seconds)
        return timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    @classmethod
    def create_authn_request(
        cls,
        sp_entity_id: str,
        idp_sso_url: str,
        acs_url: str,
        name_id_format: str = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        force_authn: bool = False,
        is_passive: bool = False
    ) -> str:
        """Create SAML AuthnRequest XML."""
        request_id = cls.generate_id()
        issue_instant = cls.get_timestamp()
        
        # Create XML structure
        authn_request = ET.Element(
            '{urn:oasis:names:tc:SAML:2.0:protocol}AuthnRequest',
            attrib={
                'ID': request_id,
                'Version': '2.0',
                'IssueInstant': issue_instant,
                'Destination': idp_sso_url,
                'AssertionConsumerServiceURL': acs_url,
                'ProtocolBinding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST'
            }
        )
        
        if force_authn:
            authn_request.set('ForceAuthn', 'true')
        
        if is_passive:
            authn_request.set('IsPassive', 'true')
        
        # Add Issuer
        issuer = ET.SubElement(
            authn_request,
            '{urn:oasis:names:tc:SAML:2.0:assertion}Issuer'
        )
        issuer.text = sp_entity_id
        
        # Add NameIDPolicy
        ET.SubElement(
            authn_request,
            '{urn:oasis:names:tc:SAML:2.0:protocol}NameIDPolicy',
            attrib={
                'Format': name_id_format,
                'AllowCreate': 'true'
            }
        )
        
        # Convert to string
        return ET.tostring(authn_request, encoding='unicode')
    
    @classmethod
    def encode_request(cls, request: str) -> str:
        """Encode SAML request for HTTP-Redirect binding."""
        # Compress
        compressed = zlib.compress(request.encode('utf-8'))[2:-4]
        # Base64 encode
        encoded = base64.b64encode(compressed).decode('utf-8')
        return encoded
    
    @classmethod
    def decode_response(cls, response: str) -> str:
        """Decode SAML response."""
        # Base64 decode
        decoded = base64.b64decode(response)
        return decoded.decode('utf-8')
    
    @classmethod
    def parse_assertion(cls, response_xml: str) -> Dict[str, Any]:
        """Parse SAML assertion from response."""
        try:
            root = ET.fromstring(response_xml)
            
            # Register namespaces
            for prefix, uri in cls.SAML_NAMESPACES.items():
                ET.register_namespace(prefix, uri)
            
            # Check status
            status_code = root.find('.//samlp:StatusCode', cls.SAML_NAMESPACES)
            if status_code is not None:
                status_value = status_code.get('Value', '')
                if not status_value.endswith(':Success'):
                    error_msg = cls._get_status_message(root)
                    raise ValueError(f"SAML authentication failed: {error_msg}")
            
            # Find assertion
            assertion = root.find('.//saml:Assertion', cls.SAML_NAMESPACES)
            if assertion is None:
                raise ValueError("No assertion found in SAML response")
            
            # Extract user info
            user_info = {}
            
            # Get NameID
            name_id = assertion.find('.//saml:NameID', cls.SAML_NAMESPACES)
            if name_id is not None:
                user_info['name_id'] = name_id.text
                user_info['name_id_format'] = name_id.get('Format', '')
            
            # Get attributes
            attributes = {}
            for attribute in assertion.findall('.//saml:Attribute', cls.SAML_NAMESPACES):
                attr_name = attribute.get('Name')
                attr_values = []
                for value in attribute.findall('.//saml:AttributeValue', cls.SAML_NAMESPACES):
                    if value.text:
                        attr_values.append(value.text)
                
                if attr_values:
                    attributes[attr_name] = attr_values[0] if len(attr_values) == 1 else attr_values
            
            user_info['attributes'] = attributes
            
            # Get conditions
            conditions = assertion.find('.//saml:Conditions', cls.SAML_NAMESPACES)
            if conditions is not None:
                not_before = conditions.get('NotBefore')
                not_on_or_after = conditions.get('NotOnOrAfter')
                
                if not_before:
                    user_info['not_before'] = not_before
                if not_on_or_after:
                    user_info['not_on_or_after'] = not_on_or_after
                
                # Validate time conditions
                now = datetime.utcnow()
                if not_before:
                    nb_time = datetime.fromisoformat(not_before.replace('Z', '+00:00'))
                    if now < nb_time:
                        raise ValueError("SAML assertion not yet valid")
                
                if not_on_or_after:
                    noa_time = datetime.fromisoformat(not_on_or_after.replace('Z', '+00:00'))
                    if now >= noa_time:
                        raise ValueError("SAML assertion has expired")
            
            # Get session info
            authn_statement = assertion.find('.//saml:AuthnStatement', cls.SAML_NAMESPACES)
            if authn_statement is not None:
                session_index = authn_statement.get('SessionIndex')
                if session_index:
                    user_info['session_index'] = session_index
                
                authn_instant = authn_statement.get('AuthnInstant')
                if authn_instant:
                    user_info['authn_instant'] = authn_instant
            
            return user_info
            
        except ET.ParseError as e:
            raise ValueError(f"Invalid SAML response XML: {str(e)}")
    
    @classmethod
    def _get_status_message(cls, root: ET.Element) -> str:
        """Extract status message from SAML response."""
        status_msg = root.find('.//samlp:StatusMessage', cls.SAML_NAMESPACES)
        if status_msg is not None and status_msg.text:
            return status_msg.text
        
        status_code = root.find('.//samlp:StatusCode', cls.SAML_NAMESPACES)
        if status_code is not None:
            return status_code.get('Value', 'Unknown error')
        
        return "Unknown error"
    
    @staticmethod
    def verify_signature(xml_string: str, certificate: str) -> bool:
        """Verify XML signature using certificate."""
        try:
            # Parse XML
            doc = xmlsec.parse_xml(xml_string.encode('utf-8'))
            
            # Find signature node
            signature_node = xmlsec.tree.find_node(doc, xmlsec.constants.NodeSignature)
            if signature_node is None:
                return False
            
            # Create signature context
            ctx = xmlsec.SignatureContext()
            
            # Load certificate
            key = xmlsec.Key.from_memory(certificate, xmlsec.constants.KeyDataFormatCertPem)
            ctx.key = key
            
            # Verify signature
            ctx.verify(signature_node)
            return True
            
        except Exception:
            return False
    
    @staticmethod
    def create_logout_request(
        sp_entity_id: str,
        idp_slo_url: str,
        name_id: str,
        session_index: Optional[str] = None,
        name_id_format: str = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
    ) -> str:
        """Create SAML LogoutRequest XML."""
        request_id = SAMLUtils.generate_id()
        issue_instant = SAMLUtils.get_timestamp()
        
        # Create LogoutRequest
        logout_request = ET.Element(
            '{urn:oasis:names:tc:SAML:2.0:protocol}LogoutRequest',
            attrib={
                'ID': request_id,
                'Version': '2.0',
                'IssueInstant': issue_instant,
                'Destination': idp_slo_url
            }
        )
        
        # Add Issuer
        issuer = ET.SubElement(
            logout_request,
            '{urn:oasis:names:tc:SAML:2.0:assertion}Issuer'
        )
        issuer.text = sp_entity_id
        
        # Add NameID
        name_id_elem = ET.SubElement(
            logout_request,
            '{urn:oasis:names:tc:SAML:2.0:assertion}NameID',
            attrib={'Format': name_id_format}
        )
        name_id_elem.text = name_id
        
        # Add SessionIndex if provided
        if session_index:
            session_elem = ET.SubElement(
                logout_request,
                '{urn:oasis:names:tc:SAML:2.0:protocol}SessionIndex'
            )
            session_elem.text = session_index
        
        return ET.tostring(logout_request, encoding='unicode')
    
    @staticmethod
    def map_attributes(attributes: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
        """Map SAML attributes to user fields using mapping configuration."""
        user_data = {}
        
        for saml_attr, user_field in mapping.items():
            if saml_attr in attributes:
                value = attributes[saml_attr]
                # Handle array values
                if isinstance(value, list) and len(value) == 1:
                    value = value[0]
                user_data[user_field] = value
        
        return user_data