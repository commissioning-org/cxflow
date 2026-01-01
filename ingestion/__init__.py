"""
Data Ingestion Package

Provides data ingestion from various sources including Power Automate.
"""

from .knowledge_base import (
    PowerAutomateClient,
    KnowledgeBaseIngestor,
    IngestionConfig,
)

__all__ = [
    "PowerAutomateClient",
    "KnowledgeBaseIngestor",
    "IngestionConfig",
]
