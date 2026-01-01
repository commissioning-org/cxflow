"""
CX Performance Ingestion Package

Handles data ingestion from Power Automate workflows for CX Performance data.
"""

from .capacity import (
    PowerAutomateClient as CapacityClient,
    CapacityIngestor,
    IngestionConfig as CapacityConfig,
)

__all__ = [
    "CapacityClient",
    "CapacityIngestor",
    "CapacityConfig",
]

__version__ = "1.0.0"
