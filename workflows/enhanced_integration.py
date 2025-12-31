"""
Integration bridge between enhanced cxflow and existing power_automate_sync.

This module provides seamless integration between the new enhanced capabilities
and the existing sync workflow.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

from workflows.cxflow_enhanced import (
    EnhancedMemoryManager,
    MacroExecutionEngine,
    MacroTemplateLibrary,
    AuditLogger,
    MemoryQuery,
    QueryOperator,
)

from workflows.power_automate_sync import (
    CXFlowSyncWorkflow,
    SyncStatus,
)

logger = logging.getLogger(__name__)


class EnhancedCXFlowWorkflow(CXFlowSyncWorkflow):
    """
    Enhanced version of CXFlowSyncWorkflow with all new capabilities.
    
    This extends the original workflow with:
    - Advanced query engine
    - Macro execution
    - Audit logging
    - Versioning
    """
    
    def __init__(
        self,
        webhook_url: Optional[str] = None,
        base_path: Path = Path("./.cxflow"),
        enable_versioning: bool = True,
        enable_encryption: bool = False,
    ):
        # Initialize parent
        super().__init__(webhook_url, base_path)
        
        # Replace standard memory manager with enhanced version
        self.enhanced_memory = EnhancedMemoryManager(
            storage_path=base_path / "memory",
            enable_versioning=enable_versioning,
            enable_encryption=enable_encryption,
        )
        
        # Initialize macro execution engine
        self.macro_engine = MacroExecutionEngine(self.enhanced_memory)
        
        # Initialize audit logger
        self.audit = AuditLogger(storage_path=base_path / "audit")
        
        # Override memory manager for backwards compatibility
        self.memory = self.enhanced_memory
    
    def query_memory(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query memory with advanced filtering.
        
        Args:
            category: Filter by category
            tags: Filter by tags
            filters: Custom filters as list of {"field": str, "op": str, "value": any}
            limit: Limit results
        
        Returns:
            List of matching memory entries
        """
        query = MemoryQuery()
        
        if category:
            query.with_category(category)
        
        if tags:
            query.with_tags(tags)
        
        if filters:
            for f in filters:
                op = QueryOperator(f.get("op", "eq"))
                query.add_filter(f["field"], op, f["value"])
        
        if limit:
            query.paginate(limit=limit)
        
        results = self.enhanced_memory.query(query)
        
        # Log query
        self.audit.log(
            "query",
            "memory",
            f"category={category},tags={tags}",
            success=True,
            metadata={"result_count": len(results)}
        )
        
        return results
    
    def execute_macro_by_name(
        self,
        macro_name: str,
        context: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
    ):
        """
        Execute a registered macro by name.
        
        Args:
            macro_name: Name of the macro to execute
            context: Execution context variables
            dry_run: If True, validate without executing
        
        Returns:
            MacroExecution result
        """
        # Get macro definition
        macro_def = self.macros.get(macro_name)
        
        if not macro_def:
            error = f"Macro not found: {macro_name}"
            logger.error(error)
            self.audit.log(
                "execute",
                "macro",
                macro_name,
                success=False,
                error=error
            )
            raise ValueError(error)
        
        # Convert MacroDefinition to dict
        from dataclasses import asdict
        macro_dict = asdict(macro_def)
        
        # Execute
        execution = self.macro_engine.execute_macro(
            macro_dict,
            context=context,
            dry_run=dry_run
        )
        
        # Log execution
        self.audit.log(
            "execute",
            "macro",
            macro_name,
            success=(execution.status.value == "completed"),
            error=", ".join(execution.errors) if execution.errors else None,
            metadata={
                "duration_ms": execution.duration_ms,
                "steps_completed": execution.steps_completed,
                "dry_run": dry_run,
            }
        )
        
        return execution
    
    def create_macro_from_template(
        self,
        template_name: str,
        parameters: Dict[str, Any],
        auto_register: bool = True,
    ):
        """
        Create a macro from a template.
        
        Args:
            template_name: Name of the template
            parameters: Template parameters
            auto_register: Automatically register the created macro
        
        Returns:
            Created macro definition
        """
        try:
            macro_dict = MacroTemplateLibrary.create_from_template(
                template_name,
                parameters
            )
            
            if auto_register:
                # Register in the workflow
                from workflows.power_automate_sync import MacroDefinition
                macro = MacroDefinition(**macro_dict)
                self.macros._macros[macro.name] = macro
                self.macros._save_macro(macro)
            
            self.audit.log(
                "create",
                "macro",
                macro_dict["name"],
                success=True,
                metadata={
                    "template": template_name,
                    "parameters": parameters,
                }
            )
            
            return macro_dict
            
        except Exception as e:
            self.audit.log(
                "create",
                "macro",
                f"from_template_{template_name}",
                success=False,
                error=str(e)
            )
            raise
    
    def rollback_memory(self, key: str, version: int) -> bool:
        """
        Rollback a memory entry to a specific version.
        
        Args:
            key: Memory key
            version: Version number to rollback to
        
        Returns:
            True if successful
        """
        success = self.enhanced_memory.rollback(key, version)
        
        self.audit.log(
            "rollback",
            "memory",
            key,
            success=success,
            metadata={"target_version": version}
        )
        
        return success
    
    def get_memory_history(self, key: str) -> List[Dict[str, Any]]:
        """
        Get version history for a memory entry.
        
        Args:
            key: Memory key
        
        Returns:
            List of version entries
        """
        from dataclasses import asdict
        
        history = self.enhanced_memory.get_history(key)
        
        self.audit.log(
            "read",
            "memory",
            key,
            success=True,
            metadata={"operation": "get_history", "versions": len(history)}
        )
        
        return [asdict(v) for v in history]
    
    def batch_set_memory(
        self,
        entries: List[Dict[str, Any]],
        user: Optional[str] = None
    ) -> List[str]:
        """
        Batch set multiple memory entries.
        
        Args:
            entries: List of entry dicts with key, value, etc.
            user: User performing the operation
        
        Returns:
            List of created keys
        """
        keys = self.enhanced_memory.batch_set(entries, user=user)
        
        self.audit.log(
            "batch_write",
            "memory",
            f"{len(keys)}_entries",
            user=user,
            success=True,
            metadata={"keys": keys}
        )
        
        return keys
    
    def search_memory(
        self,
        search_term: str,
        fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Full-text search across memory.
        
        Args:
            search_term: Term to search for
            fields: Specific fields to search in
        
        Returns:
            List of matching entries
        """
        results = self.enhanced_memory.search(search_term, fields)
        
        self.audit.log(
            "search",
            "memory",
            search_term,
            success=True,
            metadata={"result_count": len(results), "fields": fields}
        )
        
        return results
    
    def export_memory(
        self,
        filepath: Path,
        include_versions: bool = False
    ):
        """
        Export all memory to a file.
        
        Args:
            filepath: Export file path
            include_versions: Include version history
        """
        self.enhanced_memory.export_to_file(filepath, include_versions)
        
        self.audit.log(
            "export",
            "memory",
            str(filepath),
            success=True,
            metadata={"include_versions": include_versions}
        )
    
    def import_memory(
        self,
        filepath: Path,
        merge: bool = True
    ):
        """
        Import memory from a file.
        
        Args:
            filepath: Import file path
            merge: Merge with existing data
        """
        self.enhanced_memory.import_from_file(filepath, merge)
        
        self.audit.log(
            "import",
            "memory",
            str(filepath),
            success=True,
            metadata={"merge": merge}
        )
    
    def get_audit_report(
        self,
        operation: Optional[str] = None,
        entity_type: Optional[str] = None,
        success: Optional[bool] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Get audit report with statistics.
        
        Args:
            operation: Filter by operation
            entity_type: Filter by entity type
            success: Filter by success status
            limit: Limit results
        
        Returns:
            Report dict with logs and statistics
        """
        logs = self.audit.query_logs(
            operation=operation,
            entity_type=entity_type,
            success=success,
            limit=limit
        )
        
        # Calculate statistics
        stats = {
            "total": len(logs),
            "by_operation": {},
            "by_entity_type": {},
            "by_status": {"success": 0, "failed": 0},
        }
        
        for log in logs:
            # Count by operation
            stats["by_operation"][log.operation] = \
                stats["by_operation"].get(log.operation, 0) + 1
            
            # Count by entity type
            stats["by_entity_type"][log.entity_type] = \
                stats["by_entity_type"].get(log.entity_type, 0) + 1
            
            # Count by status
            if log.success:
                stats["by_status"]["success"] += 1
            else:
                stats["by_status"]["failed"] += 1
        
        return {
            "logs": [
                {
                    "timestamp": log.timestamp,
                    "operation": log.operation,
                    "entity": f"{log.entity_type}:{log.entity_id}",
                    "user": log.user,
                    "success": log.success,
                    "error": log.error,
                }
                for log in logs
            ],
            "statistics": stats,
        }
    
    def get_macro_execution_history(
        self,
        macro_name: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get macro execution history.
        
        Args:
            macro_name: Filter by macro name
            limit: Limit results
        
        Returns:
            List of execution records
        """
        from dataclasses import asdict
        
        history = self.macro_engine.get_execution_history(
            macro_name=macro_name,
            limit=limit
        )
        
        return [asdict(execution) for execution in history]


# Convenience functions for backwards compatibility
_enhanced_workflow: Optional[EnhancedCXFlowWorkflow] = None


def get_enhanced_workflow() -> EnhancedCXFlowWorkflow:
    """Get or create enhanced workflow instance."""
    global _enhanced_workflow
    if _enhanced_workflow is None:
        _enhanced_workflow = EnhancedCXFlowWorkflow()
    return _enhanced_workflow


def query_memory(
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
    **kwargs
) -> List[Dict[str, Any]]:
    """Query memory with enhanced filtering."""
    return get_enhanced_workflow().query_memory(category, tags, **kwargs)


def execute_macro(
    macro_name: str,
    context: Optional[Dict[str, Any]] = None,
    dry_run: bool = False,
):
    """Execute a macro by name."""
    return get_enhanced_workflow().execute_macro_by_name(macro_name, context, dry_run)


def create_macro_from_template(
    template_name: str,
    parameters: Dict[str, Any]
):
    """Create a macro from a template."""
    return get_enhanced_workflow().create_macro_from_template(template_name, parameters)


def search_memory(search_term: str, fields: Optional[List[str]] = None):
    """Search memory."""
    return get_enhanced_workflow().search_memory(search_term, fields)


def get_audit_report(**kwargs):
    """Get audit report."""
    return get_enhanced_workflow().get_audit_report(**kwargs)


__all__ = [
    "EnhancedCXFlowWorkflow",
    "get_enhanced_workflow",
    "query_memory",
    "execute_macro",
    "create_macro_from_template",
    "search_memory",
    "get_audit_report",
]
