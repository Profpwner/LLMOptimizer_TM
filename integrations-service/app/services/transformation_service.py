"""Data transformation service for field mapping and data conversion."""

import re
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, date
from decimal import Decimal
import json
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class TransformationType(str, Enum):
    """Types of transformations."""
    DIRECT = "direct"
    FUNCTION = "function"
    TEMPLATE = "template"
    CONDITIONAL = "conditional"
    LOOKUP = "lookup"
    AGGREGATE = "aggregate"


class DataType(str, Enum):
    """Supported data types."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    ARRAY = "array"
    OBJECT = "object"
    JSON = "json"


class ValidationRule:
    """Validation rule for transformed data."""
    
    def __init__(
        self,
        rule_type: str,
        params: Dict[str, Any],
        error_message: Optional[str] = None
    ):
        self.rule_type = rule_type
        self.params = params
        self.error_message = error_message or f"Validation failed: {rule_type}"
    
    def validate(self, value: Any) -> bool:
        """Validate a value against the rule."""
        if self.rule_type == "required":
            return value is not None and value != ""
        elif self.rule_type == "min_length":
            return len(str(value)) >= self.params.get("min", 0)
        elif self.rule_type == "max_length":
            return len(str(value)) <= self.params.get("max", float('inf'))
        elif self.rule_type == "pattern":
            pattern = self.params.get("pattern", ".*")
            return bool(re.match(pattern, str(value)))
        elif self.rule_type == "min_value":
            return float(value) >= self.params.get("min", float('-inf'))
        elif self.rule_type == "max_value":
            return float(value) <= self.params.get("max", float('inf'))
        elif self.rule_type == "enum":
            return value in self.params.get("values", [])
        elif self.rule_type == "email":
            return bool(re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', str(value)))
        elif self.rule_type == "url":
            return bool(re.match(r'^https?://[\w\.-]+(:\d+)?(/.*)?$', str(value)))
        elif self.rule_type == "custom":
            func = self.params.get("function")
            return func(value) if callable(func) else True
        return True


class FieldMapping:
    """Field mapping configuration."""
    
    def __init__(
        self,
        source_field: str,
        target_field: str,
        transformation_type: TransformationType = TransformationType.DIRECT,
        transformation_config: Optional[Dict[str, Any]] = None,
        data_type: Optional[DataType] = None,
        default_value: Any = None,
        validation_rules: Optional[List[ValidationRule]] = None
    ):
        self.source_field = source_field
        self.target_field = target_field
        self.transformation_type = transformation_type
        self.transformation_config = transformation_config or {}
        self.data_type = data_type
        self.default_value = default_value
        self.validation_rules = validation_rules or []


class TransformationService:
    """Service for data transformation and mapping."""
    
    def __init__(self):
        self._custom_functions: Dict[str, Callable] = {}
        self._lookup_tables: Dict[str, Dict[str, Any]] = {}
        self._initialize_builtin_functions()
    
    def _initialize_builtin_functions(self):
        """Initialize built-in transformation functions."""
        self._custom_functions.update({
            "uppercase": lambda x: str(x).upper(),
            "lowercase": lambda x: str(x).lower(),
            "trim": lambda x: str(x).strip(),
            "remove_whitespace": lambda x: re.sub(r'\s+', '', str(x)),
            "snake_case": lambda x: re.sub(r'[\s\-]+', '_', str(x).lower()),
            "camel_case": lambda x: ''.join(word.capitalize() for word in str(x).split()),
            "phone_normalize": self._normalize_phone,
            "email_normalize": lambda x: str(x).lower().strip(),
            "extract_domain": self._extract_domain,
            "parse_full_name": self._parse_full_name,
            "format_currency": self._format_currency,
            "clean_html": self._clean_html,
            "truncate": lambda x, length=100: str(x)[:length],
            "hash": lambda x: hashlib.sha256(str(x).encode()).hexdigest()
        })
    
    def register_function(self, name: str, func: Callable):
        """Register a custom transformation function."""
        self._custom_functions[name] = func
        logger.info(f"Registered custom function: {name}")
    
    def register_lookup_table(self, name: str, table: Dict[str, Any]):
        """Register a lookup table for transformations."""
        self._lookup_tables[name] = table
        logger.info(f"Registered lookup table: {name}")
    
    async def transform_data(
        self,
        source_data: Dict[str, Any],
        field_mappings: List[FieldMapping],
        strict: bool = False
    ) -> Dict[str, Any]:
        """Transform data according to field mappings."""
        result = {}
        errors = []
        
        for mapping in field_mappings:
            try:
                # Get source value
                source_value = self._get_nested_value(source_data, mapping.source_field)
                
                # Apply default if source is None
                if source_value is None:
                    source_value = mapping.default_value
                
                # Transform value
                transformed_value = await self._transform_value(
                    source_value,
                    mapping.transformation_type,
                    mapping.transformation_config
                )
                
                # Convert data type
                if mapping.data_type and transformed_value is not None:
                    transformed_value = self._convert_data_type(
                        transformed_value,
                        mapping.data_type
                    )
                
                # Validate
                for rule in mapping.validation_rules:
                    if not rule.validate(transformed_value):
                        if strict:
                            raise ValueError(f"{mapping.target_field}: {rule.error_message}")
                        else:
                            errors.append(f"{mapping.target_field}: {rule.error_message}")
                            transformed_value = mapping.default_value
                
                # Set in result
                self._set_nested_value(result, mapping.target_field, transformed_value)
                
            except Exception as e:
                error_msg = f"Failed to transform {mapping.source_field} -> {mapping.target_field}: {str(e)}"
                if strict:
                    raise ValueError(error_msg)
                else:
                    errors.append(error_msg)
                    logger.warning(error_msg)
        
        if errors:
            result["_transformation_errors"] = errors
        
        return result
    
    async def _transform_value(
        self,
        value: Any,
        transformation_type: TransformationType,
        config: Dict[str, Any]
    ) -> Any:
        """Apply transformation to a value."""
        if transformation_type == TransformationType.DIRECT:
            return value
        
        elif transformation_type == TransformationType.FUNCTION:
            func_name = config.get("function")
            if func_name in self._custom_functions:
                func = self._custom_functions[func_name]
                args = config.get("args", [])
                kwargs = config.get("kwargs", {})
                return func(value, *args, **kwargs)
            else:
                raise ValueError(f"Unknown function: {func_name}")
        
        elif transformation_type == TransformationType.TEMPLATE:
            template = config.get("template", "{}")
            context = {"value": value, **config.get("context", {})}
            return template.format(**context)
        
        elif transformation_type == TransformationType.CONDITIONAL:
            conditions = config.get("conditions", [])
            for condition in conditions:
                if self._evaluate_condition(value, condition.get("if", {})):
                    return condition.get("then", value)
            return config.get("else", value)
        
        elif transformation_type == TransformationType.LOOKUP:
            table_name = config.get("table")
            if table_name in self._lookup_tables:
                table = self._lookup_tables[table_name]
                return table.get(str(value), config.get("default", value))
            else:
                raise ValueError(f"Unknown lookup table: {table_name}")
        
        elif transformation_type == TransformationType.AGGREGATE:
            if not isinstance(value, list):
                return value
            
            operation = config.get("operation", "join")
            if operation == "join":
                separator = config.get("separator", ", ")
                return separator.join(str(v) for v in value)
            elif operation == "sum":
                return sum(float(v) for v in value if v is not None)
            elif operation == "avg":
                values = [float(v) for v in value if v is not None]
                return sum(values) / len(values) if values else None
            elif operation == "count":
                return len(value)
            elif operation == "first":
                return value[0] if value else None
            elif operation == "last":
                return value[-1] if value else None
            else:
                raise ValueError(f"Unknown aggregate operation: {operation}")
        
        return value
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        parts = path.split('.')
        value = data
        
        for part in parts:
            if isinstance(value, dict):
                # Handle array notation like items[0]
                match = re.match(r'(.+)\[(\d+)\]', part)
                if match:
                    key, index = match.groups()
                    if key in value and isinstance(value[key], list):
                        value = value[key]
                        if int(index) < len(value):
                            value = value[int(index)]
                        else:
                            return None
                    else:
                        return None
                else:
                    value = value.get(part)
            else:
                return None
        
        return value
    
    def _set_nested_value(self, data: Dict[str, Any], path: str, value: Any):
        """Set value in nested dictionary using dot notation."""
        parts = path.split('.')
        current = data
        
        for i, part in enumerate(parts[:-1]):
            if part not in current:
                current[part] = {}
            current = current[part]
        
        current[parts[-1]] = value
    
    def _evaluate_condition(self, value: Any, condition: Dict[str, Any]) -> bool:
        """Evaluate a condition."""
        operator = condition.get("operator", "equals")
        compare_value = condition.get("value")
        
        if operator == "equals":
            return value == compare_value
        elif operator == "not_equals":
            return value != compare_value
        elif operator == "greater_than":
            return float(value) > float(compare_value)
        elif operator == "less_than":
            return float(value) < float(compare_value)
        elif operator == "contains":
            return str(compare_value) in str(value)
        elif operator == "matches":
            return bool(re.match(compare_value, str(value)))
        elif operator == "is_null":
            return value is None
        elif operator == "is_not_null":
            return value is not None
        elif operator == "in":
            return value in compare_value
        elif operator == "not_in":
            return value not in compare_value
        
        return False
    
    def _convert_data_type(self, value: Any, data_type: DataType) -> Any:
        """Convert value to specified data type."""
        if value is None:
            return None
        
        try:
            if data_type == DataType.STRING:
                return str(value)
            elif data_type == DataType.INTEGER:
                return int(float(str(value)))
            elif data_type == DataType.FLOAT:
                return float(value)
            elif data_type == DataType.DECIMAL:
                return Decimal(str(value))
            elif data_type == DataType.BOOLEAN:
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.lower() in ['true', 'yes', '1', 'on']
                return bool(value)
            elif data_type == DataType.DATE:
                if isinstance(value, date):
                    return value
                if isinstance(value, datetime):
                    return value.date()
                if isinstance(value, str):
                    return datetime.fromisoformat(value).date()
            elif data_type == DataType.DATETIME:
                if isinstance(value, datetime):
                    return value
                if isinstance(value, str):
                    return datetime.fromisoformat(value)
            elif data_type == DataType.ARRAY:
                if isinstance(value, list):
                    return value
                if isinstance(value, str) and value.startswith('['):
                    return json.loads(value)
                return [value]
            elif data_type == DataType.OBJECT:
                if isinstance(value, dict):
                    return value
                if isinstance(value, str) and value.startswith('{'):
                    return json.loads(value)
                return {"value": value}
            elif data_type == DataType.JSON:
                if isinstance(value, str):
                    return json.loads(value)
                return value
        except Exception as e:
            logger.warning(f"Failed to convert {value} to {data_type}: {e}")
            raise ValueError(f"Cannot convert {value} to {data_type}")
        
        return value
    
    # Helper transformation functions
    
    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number."""
        # Remove all non-numeric characters
        digits = re.sub(r'\D', '', str(phone))
        
        # Format based on length
        if len(digits) == 10:  # US phone
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':  # US phone with country code
            return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        else:
            return digits
    
    def _extract_domain(self, value: str) -> str:
        """Extract domain from email or URL."""
        value = str(value).lower()
        
        # Email
        if '@' in value:
            return value.split('@')[1]
        
        # URL
        match = re.search(r'(?:https?://)?(?:www\.)?([^/]+)', value)
        if match:
            return match.group(1)
        
        return value
    
    def _parse_full_name(self, name: str) -> Dict[str, str]:
        """Parse full name into components."""
        parts = str(name).strip().split()
        
        result = {
            "first_name": "",
            "middle_name": "",
            "last_name": "",
            "full_name": name
        }
        
        if len(parts) >= 1:
            result["first_name"] = parts[0]
        if len(parts) == 2:
            result["last_name"] = parts[1]
        elif len(parts) >= 3:
            result["middle_name"] = " ".join(parts[1:-1])
            result["last_name"] = parts[-1]
        
        return result
    
    def _format_currency(self, value: Union[str, float], currency: str = "USD") -> str:
        """Format value as currency."""
        try:
            amount = float(value)
            if currency == "USD":
                return f"${amount:,.2f}"
            elif currency == "EUR":
                return f"€{amount:,.2f}"
            elif currency == "GBP":
                return f"£{amount:,.2f}"
            else:
                return f"{currency} {amount:,.2f}"
        except:
            return str(value)
    
    def _clean_html(self, html: str) -> str:
        """Remove HTML tags from string."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(str(html), 'html.parser')
        return soup.get_text(strip=True)
    
    def create_mapping_from_config(self, config: Dict[str, Any]) -> List[FieldMapping]:
        """Create field mappings from configuration dictionary."""
        mappings = []
        
        for mapping_config in config.get("mappings", []):
            # Create validation rules
            validation_rules = []
            for rule_config in mapping_config.get("validation", []):
                rule = ValidationRule(
                    rule_type=rule_config["type"],
                    params=rule_config.get("params", {}),
                    error_message=rule_config.get("error_message")
                )
                validation_rules.append(rule)
            
            # Create field mapping
            mapping = FieldMapping(
                source_field=mapping_config["source"],
                target_field=mapping_config["target"],
                transformation_type=TransformationType(
                    mapping_config.get("transformation_type", "direct")
                ),
                transformation_config=mapping_config.get("transformation_config", {}),
                data_type=DataType(mapping_config["data_type"]) if "data_type" in mapping_config else None,
                default_value=mapping_config.get("default"),
                validation_rules=validation_rules
            )
            mappings.append(mapping)
        
        return mappings
    
    def generate_mapping_template(
        self,
        source_schema: Dict[str, Any],
        target_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a mapping template based on schemas."""
        mappings = []
        
        # Simple field matching based on name similarity
        for target_field, target_info in target_schema.items():
            best_match = None
            best_score = 0
            
            for source_field in source_schema:
                # Calculate similarity score
                score = self._calculate_field_similarity(source_field, target_field)
                if score > best_score:
                    best_score = score
                    best_match = source_field
            
            if best_match and best_score > 0.5:
                mapping = {
                    "source": best_match,
                    "target": target_field,
                    "transformation_type": "direct",
                    "data_type": target_info.get("type", "string")
                }
                
                # Add validation based on target schema
                if target_info.get("required"):
                    mapping["validation"] = [{"type": "required"}]
                
                mappings.append(mapping)
        
        return {"mappings": mappings}
    
    def _calculate_field_similarity(self, field1: str, field2: str) -> float:
        """Calculate similarity between two field names."""
        # Normalize field names
        f1 = field1.lower().replace('_', '').replace('-', '')
        f2 = field2.lower().replace('_', '').replace('-', '')
        
        # Exact match
        if f1 == f2:
            return 1.0
        
        # One contains the other
        if f1 in f2 or f2 in f1:
            return 0.8
        
        # Common patterns
        patterns = [
            (r'firstname|fname', r'first_name'),
            (r'lastname|lname', r'last_name'),
            (r'email|emailaddress', r'email'),
            (r'phone|phonenumber|tel', r'phone'),
            (r'company|companyname|org', r'company'),
            (r'addr|address', r'address'),
            (r'zip|zipcode|postal', r'postal_code')
        ]
        
        for pattern1, pattern2 in patterns:
            if (re.search(pattern1, f1) and re.search(pattern2, f2)) or \
               (re.search(pattern2, f1) and re.search(pattern1, f2)):
                return 0.7
        
        return 0.0


# Singleton instance
transformation_service = TransformationService()