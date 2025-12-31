"""
Power Automate Sync Workflow Module
"""

from .power_automate_sync import (
    # Core classes
    CXFlowSyncWorkflow,
    PowerAutomateSyncClient,
    MemoryManager,
    MacroManager,
    MetadataManager,
    
    # Data models
    SyncPayload,
    SyncResult,
    SyncType,
    SyncStatus,
    MemoryEntry,
    MacroDefinition,
    MetadataRecord,
    DataPayload,
    
    # Convenience functions
    get_workflow,
    sync_to_power_automate,
    sync_to_power_automate_async,
    set_memory,
    get_memory,
    register_macro,
    set_metadata,
    record_event,
    
    # Constants
    POWER_AUTOMATE_WEBHOOK_URL,
)

__all__ = [
    # Core classes
    "CXFlowSyncWorkflow",
    "PowerAutomateSyncClient",
    "MemoryManager",
    "MacroManager",
    "MetadataManager",
    
    # Data models
    "SyncPayload",
    "SyncResult",
    "SyncType",
    "SyncStatus",
    "MemoryEntry",
    "MacroDefinition",
    "MetadataRecord",
    "DataPayload",
    
    # Convenience functions
    "get_workflow",
    "sync_to_power_automate",
    "sync_to_power_automate_async",
    "set_memory",
    "get_memory",
    "register_macro",
    "set_metadata",
    "record_event",
    
    # Constants
    "POWER_AUTOMATE_WEBHOOK_URL",
]

__version__ = "1.0.0"
