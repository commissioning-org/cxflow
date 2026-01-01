"""
CX Performance Capacity Ingestion Package

Handles data ingestion from Power Automate workflows for capacity data.
"""

from .client import PowerAutomateClient
from .ingestor import CapacityIngestor
from .config import IngestionConfig

__all__ = [
    "PowerAutomateClient",
    "CapacityIngestor",
    "IngestionConfig",
]

__version__ = "1.0.0"
