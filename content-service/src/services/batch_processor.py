import csv
import json
import io
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class BatchProcessor:
    """Service for processing batch file uploads"""
    
    def __init__(self):
        self.max_items = 1000
        self.max_file_size = 10 * 1024 * 1024  # 10MB
    
    async def parse_file(self, content: bytes, file_type: str) -> List[Dict[str, Any]]:
        """Parse uploaded file and extract content items"""
        try:
            if len(content) > self.max_file_size:
                raise ValueError(f"File size exceeds maximum limit of {self.max_file_size} bytes")
            
            if file_type == "text/csv":
                return await self._parse_csv(content)
            elif file_type == "application/json":
                return await self._parse_json(content)
            elif file_type == "text/plain":
                return await self._parse_text(content)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
                
        except Exception as e:
            logger.error(f"Error parsing file: {e}")
            raise
    
    async def _parse_csv(self, content: bytes) -> List[Dict[str, Any]]:
        """Parse CSV file"""
        items = []
        
        try:
            # Decode content
            text_content = content.decode('utf-8-sig')  # Handle BOM
            
            # Create CSV reader
            csv_file = io.StringIO(text_content)
            reader = csv.DictReader(csv_file)
            
            # Validate headers
            if not reader.fieldnames:
                raise ValueError("CSV file has no headers")
            
            required_fields = {'content'}
            optional_fields = {'title', 'keywords', 'target_audience', 'content_type'}
            
            # Check for at least the required fields
            headers_set = set(reader.fieldnames)
            if not required_fields.issubset(headers_set):
                raise ValueError(f"CSV must contain at least these columns: {required_fields}")
            
            # Parse rows
            for idx, row in enumerate(reader):
                if idx >= self.max_items:
                    logger.warning(f"Reached maximum items limit ({self.max_items})")
                    break
                
                # Skip empty rows
                if not row.get('content', '').strip():
                    continue
                
                # Parse keywords if present
                keywords = []
                if 'keywords' in row and row['keywords']:
                    # Support both comma and semicolon separated keywords
                    keywords = [k.strip() for k in row['keywords'].replace(';', ',').split(',') if k.strip()]
                
                item = {
                    'content': row['content'].strip(),
                    'title': row.get('title', '').strip() or f"Item {idx + 1}",
                    'keywords': keywords,
                    'target_audience': row.get('target_audience', '').strip(),
                    'content_type': row.get('content_type', 'article').strip(),
                    'metadata': {
                        'row_number': idx + 1,
                        'source': 'csv'
                    }
                }
                
                items.append(item)
            
            if not items:
                raise ValueError("No valid content items found in CSV")
            
            return items
            
        except UnicodeDecodeError:
            raise ValueError("Unable to decode CSV file. Please ensure it's UTF-8 encoded")
    
    async def _parse_json(self, content: bytes) -> List[Dict[str, Any]]:
        """Parse JSON file"""
        try:
            # Decode and parse JSON
            data = json.loads(content.decode('utf-8'))
            
            # Support both array and object with items array
            if isinstance(data, list):
                items_data = data
            elif isinstance(data, dict) and 'items' in data:
                items_data = data['items']
            else:
                raise ValueError("JSON must be an array or object with 'items' array")
            
            items = []
            for idx, item_data in enumerate(items_data):
                if idx >= self.max_items:
                    logger.warning(f"Reached maximum items limit ({self.max_items})")
                    break
                
                if not isinstance(item_data, dict):
                    logger.warning(f"Skipping non-object item at index {idx}")
                    continue
                
                if not item_data.get('content', '').strip():
                    continue
                
                # Handle keywords - could be string or array
                keywords = []
                if 'keywords' in item_data:
                    if isinstance(item_data['keywords'], list):
                        keywords = item_data['keywords']
                    elif isinstance(item_data['keywords'], str):
                        keywords = [k.strip() for k in item_data['keywords'].split(',') if k.strip()]
                
                item = {
                    'content': item_data['content'].strip(),
                    'title': item_data.get('title', '').strip() or f"Item {idx + 1}",
                    'keywords': keywords,
                    'target_audience': item_data.get('target_audience', '').strip(),
                    'content_type': item_data.get('content_type', 'article').strip(),
                    'metadata': {
                        'item_index': idx,
                        'source': 'json',
                        **item_data.get('metadata', {})
                    }
                }
                
                items.append(item)
            
            if not items:
                raise ValueError("No valid content items found in JSON")
            
            return items
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")
    
    async def _parse_text(self, content: bytes) -> List[Dict[str, Any]]:
        """Parse plain text file"""
        try:
            # Decode content
            text_content = content.decode('utf-8').strip()
            
            if not text_content:
                raise ValueError("Text file is empty")
            
            # Split by double newlines or custom delimiters
            # Support different content separation patterns
            items = []
            
            # Try to detect separation pattern
            if '\n---\n' in text_content:
                # Markdown-style separator
                sections = text_content.split('\n---\n')
            elif '\n\n\n' in text_content:
                # Triple newline separator
                sections = text_content.split('\n\n\n')
            elif '\n====\n' in text_content:
                # Alternative separator
                sections = text_content.split('\n====\n')
            else:
                # Default to double newline
                sections = text_content.split('\n\n')
            
            for idx, section in enumerate(sections):
                if idx >= self.max_items:
                    logger.warning(f"Reached maximum items limit ({self.max_items})")
                    break
                
                section = section.strip()
                if not section:
                    continue
                
                # Try to extract title from first line if it looks like a heading
                lines = section.split('\n')
                title = f"Item {idx + 1}"
                content_start = 0
                
                if lines and (lines[0].startswith('#') or lines[0].isupper() or len(lines[0]) < 100):
                    title = lines[0].strip('#').strip()
                    content_start = 1
                
                content = '\n'.join(lines[content_start:]).strip()
                
                if not content:
                    content = section
                
                item = {
                    'content': content,
                    'title': title,
                    'keywords': [],
                    'target_audience': '',
                    'content_type': 'article',
                    'metadata': {
                        'section_index': idx,
                        'source': 'text'
                    }
                }
                
                items.append(item)
            
            if not items:
                # If no sections found, treat entire content as one item
                items.append({
                    'content': text_content,
                    'title': 'Imported Content',
                    'keywords': [],
                    'target_audience': '',
                    'content_type': 'article',
                    'metadata': {
                        'source': 'text',
                        'single_item': True
                    }
                })
            
            return items
            
        except UnicodeDecodeError:
            raise ValueError("Unable to decode text file. Please ensure it's UTF-8 encoded")