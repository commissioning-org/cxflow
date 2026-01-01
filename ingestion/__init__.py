"""
Data Ingestion Package

Provides data ingestion from various sources including Power Automate.
"""

from .knowledge_base import (
    PowerAutomateClient as KnowledgeBaseClient,
    KnowledgeBaseIngestor,
    IngestionConfig as KnowledgeBaseConfig,
)

from .cx_energy import (
    PowerAutomateClient as CXEnergyClient,
    CXEnergyIngestor,
    IngestionConfig as CXEnergyConfig,
)

__all__ = [
    # Knowledge Base
    "KnowledgeBaseClient",
    "KnowledgeBaseIngestor",
    "KnowledgeBaseConfig",
    # CX Energy
    "CXEnergyClient",
    "CXEnergyIngestor",
    "CXEnergyConfig",
]
