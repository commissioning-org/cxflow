"""
Configuration for Power Automate Knowledge Base Ingestion.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from pathlib import Path
from urllib.parse import urlencode


@dataclass
class IngestionConfig:
    """Configuration for Power Automate data ingestion."""
    
    # Power Automate Webhook Configuration
    webhook_url: str = field(default_factory=lambda: os.getenv(
        "POWER_AUTOMATE_WEBHOOK_URL",
        "https://3eeeffe7fbb2ec6eac086222fffec8.14.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/3a852aa38d424061b03c0ba231fffc37/triggers/manual/paths/invoke"
    ))
    
    # API Parameters
    api_version: str = "1"
    sp: str = "/triggers/manual/run"
    sv: str = "1.0"
    sig: str = field(default_factory=lambda: os.getenv(
        "POWER_AUTOMATE_SIG",
        "id4hC6KXFPY6flw5jQS-TfQ9q6gs9MjKcqo2qO-q7Fw"
    ))
    
    # Storage Configuration
    storage_path: Path = field(default_factory=lambda: Path(
        os.getenv("KNOWLEDGE_BASE_PATH", "./data/knowledge_base")
    ))
    
    # Request Configuration
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Processing Configuration
    batch_size: int = 100
    validate_data: bool = True
    
    @property
    def full_url(self) -> str:
        """Get the full webhook URL with properly encoded query parameters."""
        params = urlencode({
            "api-version": self.api_version,
            "sp": self.sp,
            "sv": self.sv,
            "sig": self.sig,
        })
        return f"{self.webhook_url}?{params}"
    
    @property
    def query_params(self) -> Dict[str, str]:
        """Get query parameters as dictionary."""
        return {
            "api-version": self.api_version,
            "sp": self.sp,
            "sv": self.sv,
            "sig": self.sig,
        }
    
    def ensure_storage_path(self) -> Path:
        """Ensure storage directory exists."""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        return self.storage_path


# Default configuration instance
DEFAULT_CONFIG = IngestionConfig()
