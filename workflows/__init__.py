"""
Power Automate Sync Workflow Module

This module provides both the original sync workflow and enhanced capabilities:
- Basic: power_automate_sync (original functionality)
- Enhanced: cxflow_enhanced (new advanced features)
- Integration: enhanced_integration (bridge between both)
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

# Enhanced capabilities (optional imports)
try:
    from .cxflow_enhanced import (
        # Enhanced core classes
        EnhancedMemoryManager,
        MacroExecutionEngine,
        MacroTemplateLibrary,
        AuditLogger,
        ValidationSchema,
        
        # Enhanced data models
        QueryOperator,
        AggregateFunction,
        MemoryQuery,
        QueryFilter,
        MacroExecution,
        MacroExecutionStatus,
        MacroTemplate,
    )
    
    from .enhanced_integration import (
        # Integrated workflow
        EnhancedCXFlowWorkflow,
        get_enhanced_workflow,
        query_memory,
        execute_macro,
        create_macro_from_template,
        search_memory,
        get_audit_report,
    )
    
    HAS_ENHANCED = True
except ImportError:
    HAS_ENHANCED = False
    EnhancedMemoryManager = None
    MacroExecutionEngine = None
    MacroTemplateLibrary = None
    AuditLogger = None
    ValidationSchema = None
    QueryOperator = None
    AggregateFunction = None
    MemoryQuery = None
    QueryFilter = None
    MacroExecution = None
    MacroExecutionStatus = None
    MacroTemplate = None
    EnhancedCXFlowWorkflow = None
    get_enhanced_workflow = None
    query_memory = None
    execute_macro = None
    create_macro_from_template = None
    search_memory = None
    get_audit_report = None

__all__ = [
    # Core classes (original)
    "CXFlowSyncWorkflow",
    "PowerAutomateSyncClient",
    "MemoryManager",
    "MacroManager",
    "MetadataManager",
    
    # Data models (original)
    "SyncPayload",
    "SyncResult",
    "SyncType",
    "SyncStatus",
    "MemoryEntry",
    "MacroDefinition",
    "MetadataRecord",
    "DataPayload",
    
    # Convenience functions (original)
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
    
    # Enhanced capabilities flag
    "HAS_ENHANCED",
]

# Add enhanced capabilities to __all__ if available
if HAS_ENHANCED:
    __all__.extend([
        # Enhanced core classes
        "EnhancedMemoryManager",
        "MacroExecutionEngine",
        "MacroTemplateLibrary",
        "AuditLogger",
        "ValidationSchema",
        
        # Enhanced data models
        "QueryOperator",
        "AggregateFunction",
        "MemoryQuery",
        "QueryFilter",
        "MacroExecution",
        "MacroExecutionStatus",
        "MacroTemplate",
        
        # Integrated workflow
        "EnhancedCXFlowWorkflow",
        "get_enhanced_workflow",
        "query_memory",
        "execute_macro",
        "create_macro_from_template",
        "search_memory",
        "get_audit_report",
    ])

__version__ = "2.0.0"  # Updated to reflect enhanced capabilities
