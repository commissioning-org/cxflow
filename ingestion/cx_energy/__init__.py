"""
CX Energy Ingestion Package

Handles data ingestion from Power Automate workflows for CX Energy data.
"""

from .client import PowerAutomateClient
from .ingestor import CXEnergyIngestor
from .config import IngestionConfig

__all__ = [
    "PowerAutomateClient",
    "CXEnergyIngestor",
    "IngestionConfig",
]

__version__ = "1.0.0"
