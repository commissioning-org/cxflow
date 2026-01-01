"""
Knowledge Base Ingestion Package

Handles data ingestion from Power Automate workflows into the knowledge base.
"""

from .client import PowerAutomateClient
from .ingestor import KnowledgeBaseIngestor
from .config import IngestionConfig

__all__ = [
    "PowerAutomateClient",
    "KnowledgeBaseIngestor",
    "IngestionConfig",
]

__version__ = "1.0.0"
