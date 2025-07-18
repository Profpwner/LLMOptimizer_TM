"""Logging configuration."""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict

from app.core.config import get_settings

settings = get_settings()


class JSONFormatter(logging.Formatter):
    """JSON log formatter."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": settings.service_name,
            "environment": settings.environment,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info",
            ]:
                log_data[key] = value
        
        return json.dumps(log_data)


def setup_logging():
    """Setup logging configuration."""
    # Clear existing handlers
    logging.root.handlers = []
    
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    
    # Set formatter based on format setting
    if settings.log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )
    
    # Configure root logger
    logging.root.setLevel(settings.log_level)
    logging.root.addHandler(handler)
    
    # Configure specific loggers
    logging.getLogger("uvicorn").setLevel(settings.log_level)
    logging.getLogger("fastapi").setLevel(settings.log_level)
    
    # Reduce noise from external libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)