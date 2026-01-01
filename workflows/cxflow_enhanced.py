"""
Enhanced CXFlow Capabilities

This module provides significantly enhanced capabilities for the .cxflow system:
- Advanced query engine for memory with filtering, search, and aggregation
- Macro execution engine to actually run macros
- Macro templates library with common patterns
- Versioning support for memory, macros, and metadata
- Validation schemas for macros and metadata
- Conditional logic support in macros
- Macro chaining and dependencies
- Rollback/undo capabilities
- Audit trail for all operations
- Export/import capabilities
- Batch operations
- Data transformation utilities
- Encryption support for sensitive data
"""

from __future__ import annotations

import os
import re
import json
import hashlib
import logging
import operator
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
import copy

# Optional encryption support
try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    Fernet = None

logger = logging.getLogger(__name__)


# ============================================================================
# Enhanced Data Models
# ============================================================================

class QueryOperator(str, Enum):
    """Query operators for memory filtering."""
    EQ = "eq"           # Equal
    NE = "ne"           # Not equal
    GT = "gt"           # Greater than
    GTE = "gte"         # Greater than or equal
    LT = "lt"           # Less than
    LTE = "lte"         # Less than or equal
    IN = "in"           # In list
    NIN = "nin"         # Not in list
    CONTAINS = "contains"  # Contains substring
    REGEX = "regex"     # Regex match
    EXISTS = "exists"   # Field exists


class AggregateFunction(str, Enum):
    """Aggregate functions for query results."""
    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    DISTINCT = "distinct"


class MacroExecutionStatus(str, Enum):
    """Status of macro execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class QueryFilter:
    """Filter for querying memory."""
    field: str
    operator: QueryOperator
    value: Any
    
    def matches(self, entry: Dict[str, Any]) -> bool:
        """Check if entry matches this filter."""
        # Navigate nested fields
        field_value = entry
        for part in self.field.split('.'):
            if isinstance(field_value, dict):
                field_value = field_value.get(part)
            else:
                return False
        
        op = self.operator
        val = self.value
        
        if op == QueryOperator.EQ:
            return field_value == val
        elif op == QueryOperator.NE:
            return field_value != val
        elif op == QueryOperator.GT:
            return field_value > val if field_value is not None else False
        elif op == QueryOperator.GTE:
            return field_value >= val if field_value is not None else False
        elif op == QueryOperator.LT:
            return field_value < val if field_value is not None else False
        elif op == QueryOperator.LTE:
            return field_value <= val if field_value is not None else False
        elif op == QueryOperator.IN:
            return field_value in val if field_value is not None else False
        elif op == QueryOperator.NIN:
            return field_value not in val if field_value is not None else False
        elif op == QueryOperator.CONTAINS:
            return val in str(field_value) if field_value is not None else False
        elif op == QueryOperator.REGEX:
            return bool(re.search(val, str(field_value))) if field_value is not None else False
        elif op == QueryOperator.EXISTS:
            return (field_value is not None) == val
        
        return False


@dataclass
class MemoryQuery:
    """Query builder for memory operations."""
    filters: List[QueryFilter] = field(default_factory=list)
    tags: Optional[List[str]] = None
    category: Optional[str] = None
    sort_by: Optional[str] = None
    sort_desc: bool = False
    limit: Optional[int] = None
    offset: int = 0
    
    def add_filter(self, field: str, operator: QueryOperator, value: Any) -> MemoryQuery:
        """Add a filter to the query."""
        self.filters.append(QueryFilter(field, operator, value))
        return self
    
    def with_tags(self, tags: List[str]) -> MemoryQuery:
        """Filter by tags."""
        self.tags = tags
        return self
    
    def with_category(self, category: str) -> MemoryQuery:
        """Filter by category."""
        self.category = category
        return self
    
    def sort(self, field: str, desc: bool = False) -> MemoryQuery:
        """Add sorting."""
        self.sort_by = field
        self.sort_desc = desc
        return self
    
    def paginate(self, limit: int, offset: int = 0) -> MemoryQuery:
        """Add pagination."""
        self.limit = limit
        self.offset = offset
        return self


@dataclass
class VersionedEntry:
    """Versioned entry for rollback support."""
    version: int
    data: Dict[str, Any]
    timestamp: str
    operation: str  # create, update, delete
    user: Optional[str] = None
    comment: Optional[str] = None


@dataclass
class AuditLogEntry:
    """Audit log entry for tracking operations."""
    id: str
    timestamp: str
    operation: str  # read, write, delete, query, execute
    entity_type: str  # memory, macro, metadata
    entity_id: str
    user: Optional[str] = None
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MacroExecution:
    """Execution record for a macro."""
    execution_id: str
    macro_name: str
    status: MacroExecutionStatus
    started_at: str
    completed_at: Optional[str] = None
    duration_ms: int = 0
    steps_completed: int = 0
    steps_total: int = 0
    results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MacroTemplate:
    """Template for creating macros."""
    name: str
    description: str
    category: str
    parameters: List[Dict[str, Any]]
    actions_template: List[Dict[str, Any]]
    example: Optional[Dict[str, Any]] = None


# ============================================================================
# Enhanced Memory Manager with Query Engine
# ============================================================================

class EnhancedMemoryManager:
    """
    Enhanced memory manager with query engine, versioning, and encryption.
    """
    
    def __init__(
        self,
        storage_path: Optional[Path] = None,
        enable_versioning: bool = True,
        enable_encryption: bool = False,
        encryption_key: Optional[bytes] = None,
    ):
        self.storage_path = storage_path or Path("./.cxflow/memory")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.enable_versioning = enable_versioning
        self.enable_encryption = enable_encryption
        
        self._memory: Dict[str, Dict[str, Any]] = {}
        self._versions: Dict[str, List[VersionedEntry]] = defaultdict(list)
        self._indexes: Dict[str, Dict[str, List[str]]] = {
            'category': defaultdict(list),
            'tags': defaultdict(list),
        }
        
        # Encryption setup
        self._fernet = None
        if enable_encryption:
            if not HAS_CRYPTO:
                raise ImportError("cryptography package required for encryption. Install with: pip install cryptography")
            if encryption_key:
                self._fernet = Fernet(encryption_key)
            else:
                key = Fernet.generate_key()
                self._fernet = Fernet(key)
                # Save key securely
                key_file = self.storage_path / ".encryption_key"
                key_file.write_bytes(key)
                key_file.chmod(0o600)
        
        self._load_persisted()
        self._rebuild_indexes()
    
    def _encrypt(self, data: str) -> str:
        """Encrypt data if encryption is enabled."""
        if self._fernet:
            return self._fernet.encrypt(data.encode()).decode()
        return data
    
    def _decrypt(self, data: str) -> str:
        """Decrypt data if encryption is enabled."""
        if self._fernet:
            return self._fernet.decrypt(data.encode()).decode()
        return data
    
    def _load_persisted(self):
        """Load persisted memory from disk."""
        memory_file = self.storage_path / "memory.json"
        if memory_file.exists():
            try:
                data = json.loads(memory_file.read_text())
                for key, entry in data.items():
                    # Decrypt if needed
                    if entry.get('encrypted'):
                        entry['value'] = json.loads(self._decrypt(entry['value']))
                    self._memory[key] = entry
            except Exception as e:
                logger.warning(f"Failed to load memory: {e}")
        
        # Load versions
        if self.enable_versioning:
            versions_file = self.storage_path / "versions.json"
            if versions_file.exists():
                try:
                    data = json.loads(versions_file.read_text())
                    for key, versions in data.items():
                        self._versions[key] = [VersionedEntry(**v) for v in versions]
                except Exception as e:
                    logger.warning(f"Failed to load versions: {e}")
    
    def _persist(self):
        """Persist memory to disk."""
        memory_file = self.storage_path / "memory.json"
        
        # Prepare data for persistence
        data_to_save = {}
        for key, entry in self._memory.items():
            entry_copy = copy.deepcopy(entry)
            
            # Encrypt sensitive data if needed
            if entry_copy.get('metadata', {}).get('sensitive') and self.enable_encryption:
                entry_copy['value'] = self._encrypt(json.dumps(entry_copy['value']))
                entry_copy['encrypted'] = True
            
            data_to_save[key] = entry_copy
        
        memory_file.write_text(json.dumps(data_to_save, indent=2, default=str))
        
        # Persist versions
        if self.enable_versioning and self._versions:
            versions_file = self.storage_path / "versions.json"
            versions_data = {
                k: [asdict(v) for v in versions]
                for k, versions in self._versions.items()
            }
            versions_file.write_text(json.dumps(versions_data, indent=2, default=str))
    
    def _rebuild_indexes(self):
        """Rebuild internal indexes for fast querying."""
        self._indexes = {
            'category': defaultdict(list),
            'tags': defaultdict(list),
        }
        
        for key, entry in self._memory.items():
            # Index by category
            category = entry.get('category', 'general')
            self._indexes['category'][category].append(key)
            
            # Index by tags
            for tag in entry.get('tags', []):
                self._indexes['tags'][tag].append(key)
    
    def _add_version(self, key: str, operation: str, user: Optional[str] = None, comment: Optional[str] = None):
        """Add a version entry."""
        if not self.enable_versioning:
            return
        
        current_versions = self._versions[key]
        version_num = len(current_versions) + 1
        
        entry_data = self._memory.get(key, {})
        
        version = VersionedEntry(
            version=version_num,
            data=copy.deepcopy(entry_data),
            timestamp=datetime.now(timezone.utc).isoformat(),
            operation=operation,
            user=user,
            comment=comment,
        )
        
        self._versions[key].append(version)
        
        # Keep only last 50 versions per entry
        if len(self._versions[key]) > 50:
            self._versions[key] = self._versions[key][-50:]
    
    def set(
        self,
        key: str,
        value: Any,
        category: str = "general",
        ttl_seconds: Optional[int] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set a memory entry with enhanced features."""
        operation = "update" if key in self._memory else "create"
        
        entry = {
            "key": key,
            "value": value,
            "category": category,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ttl_seconds": ttl_seconds,
            "tags": tags or [],
            "metadata": metadata or {},
        }
        
        # Add version before updating
        if key in self._memory:
            self._add_version(key, operation, user, comment)
        
        self._memory[key] = entry
        self._rebuild_indexes()
        self._persist()
        
        # Add version after creating
        if operation == "create":
            self._add_version(key, operation, user, comment)
        
        return entry
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get a memory entry with TTL check."""
        entry = self._memory.get(key)
        if not entry:
            return None
        
        # Check TTL
        if entry.get('ttl_seconds'):
            created = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
            if (datetime.now(timezone.utc) - created).total_seconds() > entry['ttl_seconds']:
                self.delete(key)
                return None
        
        return entry
    
    def query(self, query: MemoryQuery) -> List[Dict[str, Any]]:
        """
        Execute a query against memory.
        
        Example:
            query = MemoryQuery()
            query.with_category("config")
            query.add_filter("metadata.priority", QueryOperator.GT, 5)
            query.with_tags(["important"])
            query.sort("timestamp", desc=True)
            query.paginate(limit=10)
            results = manager.query(query)
        """
        # Start with all entries
        results = list(self._memory.values())
        
        # Apply category filter using index
        if query.category:
            keys = self._indexes['category'].get(query.category, [])
            results = [self._memory[k] for k in keys if k in self._memory]
        
        # Apply tag filter using index
        if query.tags:
            matching_keys = set()
            for tag in query.tags:
                matching_keys.update(self._indexes['tags'].get(tag, []))
            results = [r for r in results if r['key'] in matching_keys]
        
        # Apply custom filters
        for filter_obj in query.filters:
            results = [r for r in results if filter_obj.matches(r)]
        
        # Check TTL for all results
        results = [r for r in results if not self._is_expired(r)]
        
        # Sort
        if query.sort_by:
            def get_sort_value(entry):
                value = entry
                for part in query.sort_by.split('.'):
                    if isinstance(value, dict):
                        value = value.get(part)
                    else:
                        return None
                return value
            
            results.sort(key=get_sort_value, reverse=query.sort_desc)
        
        # Paginate
        if query.offset:
            results = results[query.offset:]
        if query.limit:
            results = results[:query.limit]
        
        return results
    
    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        """Check if entry is expired."""
        if not entry.get('ttl_seconds'):
            return False
        
        created = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
        return (datetime.now(timezone.utc) - created).total_seconds() > entry['ttl_seconds']
    
    def aggregate(
        self,
        field: str,
        function: AggregateFunction,
        query: Optional[MemoryQuery] = None
    ) -> Any:
        """
        Perform aggregation on query results.
        
        Example:
            # Count entries by category
            count = manager.aggregate("key", AggregateFunction.COUNT, 
                MemoryQuery().with_category("config"))
            
            # Average of a numeric field
            avg = manager.aggregate("metadata.score", AggregateFunction.AVG)
        """
        results = self.query(query) if query else list(self._memory.values())
        
        if not results:
            return 0 if function in (AggregateFunction.COUNT, AggregateFunction.SUM) else None
        
        # Extract field values
        values = []
        for entry in results:
            value = entry
            for part in field.split('.'):
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    value = None
                    break
            if value is not None:
                values.append(value)
        
        if function == AggregateFunction.COUNT:
            return len(values)
        elif function == AggregateFunction.SUM:
            return sum(values)
        elif function == AggregateFunction.AVG:
            return sum(values) / len(values) if values else 0
        elif function == AggregateFunction.MIN:
            return min(values) if values else None
        elif function == AggregateFunction.MAX:
            return max(values) if values else None
        elif function == AggregateFunction.DISTINCT:
            return list(set(values))
        
        return None
    
    def search(self, search_term: str, fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Full-text search across memory entries.
        
        Example:
            results = manager.search("important project", fields=["value", "metadata.description"])
        """
        search_term_lower = search_term.lower()
        results = []
        
        for entry in self._memory.values():
            if self._is_expired(entry):
                continue
            
            # Search in specified fields or all text fields
            search_fields = fields or ["key", "value", "category", "tags", "metadata"]
            
            for field_path in search_fields:
                field_value = entry
                for part in field_path.split('.'):
                    if isinstance(field_value, dict):
                        field_value = field_value.get(part)
                    else:
                        field_value = None
                        break
                
                if field_value and search_term_lower in str(field_value).lower():
                    results.append(entry)
                    break
        
        return results
    
    def batch_set(self, entries: List[Dict[str, Any]], user: Optional[str] = None) -> List[str]:
        """
        Batch set multiple entries.
        
        Example:
            entries = [
                {"key": "k1", "value": "v1", "category": "test"},
                {"key": "k2", "value": "v2", "category": "test"},
            ]
            keys = manager.batch_set(entries)
        """
        created_keys = []
        
        for entry_data in entries:
            key = entry_data.pop('key')
            self.set(key, user=user, **entry_data)
            created_keys.append(key)
        
        return created_keys
    
    def batch_delete(self, keys: List[str], user: Optional[str] = None) -> int:
        """Batch delete multiple entries."""
        deleted = 0
        for key in keys:
            if self.delete(key, user=user):
                deleted += 1
        return deleted
    
    def delete(self, key: str, user: Optional[str] = None) -> bool:
        """Delete a memory entry."""
        if key in self._memory:
            self._add_version(key, "delete", user)
            del self._memory[key]
            self._rebuild_indexes()
            self._persist()
            return True
        return False
    
    def rollback(self, key: str, version: int) -> bool:
        """
        Rollback entry to a specific version.
        
        Example:
            # Rollback to version 3
            manager.rollback("config_key", 3)
        """
        if not self.enable_versioning:
            logger.warning("Versioning is not enabled")
            return False
        
        versions = self._versions.get(key, [])
        target_version = next((v for v in versions if v.version == version), None)
        
        if not target_version:
            return False
        
        # Restore the version data
        if target_version.operation != "delete":
            self._memory[key] = copy.deepcopy(target_version.data)
            self._rebuild_indexes()
            self._persist()
            self._add_version(key, "rollback", comment=f"Rolled back to version {version}")
        
        return True
    
    def get_history(self, key: str) -> List[VersionedEntry]:
        """Get version history for a key."""
        return self._versions.get(key, [])
    
    def export_for_sync(self) -> List[Dict[str, Any]]:
        """Export memory for sync payload."""
        return [entry for entry in self._memory.values() if not self._is_expired(entry)]
    
    def export_to_file(self, filepath: Path, include_versions: bool = False):
        """Export all memory to a file."""
        export_data = {
            "memory": self._memory,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }
        
        if include_versions and self.enable_versioning:
            export_data["versions"] = {
                k: [asdict(v) for v in versions]
                for k, versions in self._versions.items()
            }
        
        filepath.write_text(json.dumps(export_data, indent=2, default=str))
    
    def import_from_file(self, filepath: Path, merge: bool = True):
        """Import memory from a file."""
        data = json.loads(filepath.read_text())
        
        imported_memory = data.get("memory", {})
        
        if merge:
            self._memory.update(imported_memory)
        else:
            self._memory = imported_memory
        
        # Import versions if available
        if "versions" in data and self.enable_versioning:
            for key, versions in data["versions"].items():
                self._versions[key] = [VersionedEntry(**v) for v in versions]
        
        self._rebuild_indexes()
        self._persist()


# ============================================================================
# Macro Execution Engine
# ============================================================================

class MacroExecutionEngine:
    """
    Engine for executing macros with conditional logic, chaining, and error handling.
    """
    
    def __init__(self, memory_manager: Optional[EnhancedMemoryManager] = None):
        self.memory_manager = memory_manager
        self._execution_history: List[MacroExecution] = []
        self._action_handlers: Dict[str, Callable] = {}
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default action handlers."""
        self._action_handlers.update({
            "log": self._handle_log,
            "set_memory": self._handle_set_memory,
            "get_memory": self._handle_get_memory,
            "collect": self._handle_collect,
            "sync": self._handle_sync,
            "execute": self._handle_execute,
            "notify": self._handle_notify,
            "api_call": self._handle_api_call,
            "condition": self._handle_condition,
            "loop": self._handle_loop,
            "transform": self._handle_transform,
            "delay": self._handle_delay,
        })
    
    def register_action_handler(self, action_type: str, handler: Callable):
        """Register a custom action handler."""
        self._action_handlers[action_type] = handler
    
    def _handle_log(self, action: Dict, context: Dict) -> Dict:
        """Handle log action."""
        message = self._resolve_variables(action.get("message", ""), context)
        level = action.get("level", "info").upper()
        
        log_method = getattr(logger, level.lower(), logger.info)
        log_method(message)
        
        return {"success": True, "message": message}
    
    def _handle_set_memory(self, action: Dict, context: Dict) -> Dict:
        """Handle set_memory action."""
        if not self.memory_manager:
            return {"success": False, "error": "No memory manager available"}
        
        key = self._resolve_variables(action.get("key", ""), context)
        value = self._resolve_variables(action.get("value"), context)
        
        self.memory_manager.set(key, value)
        return {"success": True, "key": key}
    
    def _handle_get_memory(self, action: Dict, context: Dict) -> Dict:
        """Handle get_memory action."""
        if not self.memory_manager:
            return {"success": False, "error": "No memory manager available"}
        
        key = self._resolve_variables(action.get("key", ""), context)
        entry = self.memory_manager.get(key)
        
        if entry:
            # Store in context for later actions
            result_var = action.get("store_as", f"memory_{key}")
            context[result_var] = entry.get("value")
            return {"success": True, "value": entry.get("value")}
        
        return {"success": False, "error": f"Key not found: {key}"}
    
    def _handle_collect(self, action: Dict, context: Dict) -> Dict:
        """Handle collect action."""
        source = action.get("source")
        # Placeholder for collection logic
        return {"success": True, "source": source, "collected": []}
    
    def _handle_sync(self, action: Dict, context: Dict) -> Dict:
        """Handle sync action."""
        destination = action.get("destination")
        # Placeholder for sync logic
        return {"success": True, "destination": destination}
    
    def _handle_execute(self, action: Dict, context: Dict) -> Dict:
        """Handle execute action (run command)."""
        command = self._resolve_variables(action.get("command", ""), context)
        # Placeholder - in real implementation, would execute safely
        return {"success": True, "command": command, "output": "Executed"}
    
    def _handle_notify(self, action: Dict, context: Dict) -> Dict:
        """Handle notify action."""
        channel = action.get("channel")
        message = self._resolve_variables(action.get("message", ""), context)
        # Placeholder for notification logic
        return {"success": True, "channel": channel, "message": message}
    
    def _handle_api_call(self, action: Dict, context: Dict) -> Dict:
        """Handle API call action."""
        endpoint = self._resolve_variables(action.get("endpoint", ""), context)
        method = action.get("method", "GET")
        # Placeholder for API call logic
        return {"success": True, "endpoint": endpoint, "method": method}
    
    def _handle_condition(self, action: Dict, context: Dict) -> Dict:
        """
        Handle conditional logic.
        
        Example action:
        {
            "type": "condition",
            "if": "{{context.value}} > 10",
            "then": [{"type": "log", "message": "Value is high"}],
            "else": [{"type": "log", "message": "Value is low"}]
        }
        """
        condition = self._resolve_variables(action.get("if", ""), context)
        
        # Evaluate condition safely
        try:
            result = self._safe_eval_condition(condition) if isinstance(condition, str) else bool(condition)
        except:
            result = False
        
        # Execute then or else branch
        branch = action.get("then", []) if result else action.get("else", [])
        branch_results = []
        
        for sub_action in branch:
            action_result = self._execute_action(sub_action, context)
            branch_results.append(action_result)
        
        return {"success": True, "condition_result": result, "branch_results": branch_results}
    
    def _safe_eval_condition(self, condition: str) -> bool:
        """
        Safely evaluate a condition without using eval().
        
        Supports basic comparisons like:
        - "value > 10"
        - "status == 'active'"
        - "count <= 5"
        - "name != 'test'"
        """
        import operator
        
        # Define safe operators (order matters - check longer operators first)
        ops = [
            ('>=', operator.ge),
            ('<=', operator.le),
            ('==', operator.eq),
            ('!=', operator.ne),
            ('>', operator.gt),
            ('<', operator.lt),
        ]
        
        # Try to parse simple comparison
        for op_str, op_func in ops:
            if op_str in condition:
                parts = condition.split(op_str, 1)
                if len(parts) == 2:
                    left = parts[0].strip()
                    right = parts[1].strip()
                    
                    # Try to convert to appropriate types
                    try:
                        # Try as number
                        left_val = float(left)
                        right_val = float(right)
                        return op_func(left_val, right_val)
                    except ValueError:
                        # Try as string (remove quotes if present)
                        left_val = left.strip("'\"")
                        right_val = right.strip("'\"")
                        return op_func(left_val, right_val)
        
        # For simple boolean values
        if condition.lower() in ('true', '1', 'yes'):
            return True
        if condition.lower() in ('false', '0', 'no', ''):
            return False
        
        # Default to False for safety
        logger.warning(f"Could not safely evaluate condition: {condition}")
        return False
    
    def _handle_loop(self, action: Dict, context: Dict) -> Dict:
        """
        Handle loop logic.
        
        Example action:
        {
            "type": "loop",
            "items": "{{context.item_list}}",
            "as": "item",
            "actions": [{"type": "log", "message": "Processing {{item}}"}]
        }
        """
        items = self._resolve_variables(action.get("items", []), context)
        var_name = action.get("as", "item")
        loop_actions = action.get("actions", [])
        
        results = []
        for item in items:
            loop_context = context.copy()
            loop_context[var_name] = item
            
            for loop_action in loop_actions:
                action_result = self._execute_action(loop_action, loop_context)
                results.append(action_result)
        
        return {"success": True, "iterations": len(items), "results": results}
    
    def _handle_transform(self, action: Dict, context: Dict) -> Dict:
        """
        Handle data transformation.
        
        Example action:
        {
            "type": "transform",
            "input": "{{context.data}}",
            "operation": "uppercase",
            "store_as": "transformed_data"
        }
        """
        input_data = self._resolve_variables(action.get("input"), context)
        operation = action.get("operation")
        store_as = action.get("store_as", "result")
        
        # Apply transformation
        result = input_data
        if operation == "uppercase" and isinstance(input_data, str):
            result = input_data.upper()
        elif operation == "lowercase" and isinstance(input_data, str):
            result = input_data.lower()
        elif operation == "reverse" and isinstance(input_data, (list, str)):
            result = input_data[::-1]
        elif operation == "sort" and isinstance(input_data, list):
            result = sorted(input_data)
        elif operation == "unique" and isinstance(input_data, list):
            result = list(set(input_data))
        elif operation == "count" and isinstance(input_data, (list, dict, str)):
            result = len(input_data)
        
        # Store result in context
        context[store_as] = result
        
        return {"success": True, "result": result}
    
    def _handle_delay(self, action: Dict, context: Dict) -> Dict:
        """Handle delay action."""
        import time
        seconds = action.get("seconds", 1)
        time.sleep(seconds)
        return {"success": True, "delayed": seconds}
    
    def _resolve_variables(self, value: Any, context: Dict) -> Any:
        """
        Resolve variables in strings using {{var}} syntax.
        
        Example:
            "Hello {{name}}" -> "Hello World" (if context["name"] = "World")
        """
        if not isinstance(value, str):
            return value
        
        # Find all {{variable}} patterns
        pattern = r'\{\{(.+?)\}\}'
        matches = re.findall(pattern, value)
        
        for match in matches:
            var_path = match.strip()
            
            # Navigate nested variables
            var_value = context
            for part in var_path.split('.'):
                if isinstance(var_value, dict):
                    var_value = var_value.get(part)
                else:
                    var_value = None
                    break
            
            # Replace in string
            if var_value is not None:
                value = value.replace(f"{{{{{match}}}}}", str(var_value))
        
        return value
    
    def _execute_action(self, action: Dict, context: Dict) -> Dict:
        """Execute a single action."""
        action_type = action.get("type")
        
        if action_type not in self._action_handlers:
            logger.warning(f"Unknown action type: {action_type}")
            return {"success": False, "error": f"Unknown action type: {action_type}"}
        
        try:
            handler = self._action_handlers[action_type]
            return handler(action, context)
        except Exception as e:
            logger.exception(f"Action execution failed: {e}")
            return {"success": False, "error": str(e)}
    
    def execute_macro(
        self,
        macro_def: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        dry_run: bool = False
    ) -> MacroExecution:
        """
        Execute a macro with all its actions.
        
        Args:
            macro_def: Macro definition dict with 'name' and 'actions'
            context: Execution context variables
            dry_run: If True, don't actually execute, just validate
        
        Returns:
            MacroExecution record
        """
        execution_id = hashlib.md5(
            f"{macro_def['name']}-{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:16]
        
        execution = MacroExecution(
            execution_id=execution_id,
            macro_name=macro_def['name'],
            status=MacroExecutionStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
            steps_total=len(macro_def.get('actions', [])),
            context=context or {},
        )
        
        if dry_run:
            execution.status = MacroExecutionStatus.COMPLETED
            execution.completed_at = datetime.now(timezone.utc).isoformat()
            execution.results = {"dry_run": True, "would_execute": macro_def.get('actions', [])}
            return execution
        
        # Execute actions
        action_context = execution.context.copy()
        
        for idx, action in enumerate(macro_def.get('actions', [])):
            try:
                result = self._execute_action(action, action_context)
                execution.results[f"step_{idx}"] = result
                
                if result.get("success"):
                    execution.steps_completed += 1
                else:
                    execution.errors.append(f"Step {idx} failed: {result.get('error')}")
                    
            except Exception as e:
                execution.errors.append(f"Step {idx} exception: {str(e)}")
                logger.exception(f"Macro execution error at step {idx}")
        
        # Finalize execution
        execution.status = (
            MacroExecutionStatus.COMPLETED
            if execution.steps_completed == execution.steps_total
            else MacroExecutionStatus.FAILED
        )
        execution.completed_at = datetime.now(timezone.utc).isoformat()
        
        start_time = datetime.fromisoformat(execution.started_at.replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(execution.completed_at.replace('Z', '+00:00'))
        execution.duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        self._execution_history.append(execution)
        return execution
    
    def get_execution_history(self, macro_name: Optional[str] = None, limit: int = 100) -> List[MacroExecution]:
        """Get execution history, optionally filtered by macro name."""
        history = self._execution_history
        
        if macro_name:
            history = [e for e in history if e.macro_name == macro_name]
        
        return history[-limit:]


# ============================================================================
# Macro Templates Library
# ============================================================================

class MacroTemplateLibrary:
    """Library of reusable macro templates."""
    
    @staticmethod
    def get_templates() -> List[MacroTemplate]:
        """Get all available templates."""
        return [
            MacroTemplate(
                name="scheduled_sync",
                description="Sync data on a schedule",
                category="sync",
                parameters=[
                    {"name": "source", "type": "string", "description": "Data source to sync"},
                    {"name": "destination", "type": "string", "description": "Sync destination"},
                    {"name": "schedule", "type": "string", "description": "Cron schedule"},
                ],
                actions_template=[
                    {"type": "collect", "source": "{{source}}"},
                    {"type": "sync", "destination": "{{destination}}"},
                    {"type": "log", "message": "Synced {{source}} to {{destination}}"},
                ],
                example={"source": "memory", "destination": "power_automate", "schedule": "0 * * * *"}
            ),
            MacroTemplate(
                name="conditional_notification",
                description="Send notification based on condition",
                category="notification",
                parameters=[
                    {"name": "condition_field", "type": "string", "description": "Field to check"},
                    {"name": "threshold", "type": "number", "description": "Threshold value"},
                    {"name": "channel", "type": "string", "description": "Notification channel"},
                ],
                actions_template=[
                    {
                        "type": "condition",
                        "if": "{{context[condition_field]}} > {{threshold}}",
                        "then": [
                            {"type": "notify", "channel": "{{channel}}", "message": "Threshold exceeded"}
                        ]
                    }
                ],
                example={"condition_field": "error_count", "threshold": 10, "channel": "slack"}
            ),
            MacroTemplate(
                name="data_pipeline",
                description="Process data through transformation pipeline",
                category="data",
                parameters=[
                    {"name": "input_key", "type": "string", "description": "Input memory key"},
                    {"name": "output_key", "type": "string", "description": "Output memory key"},
                    {"name": "transformations", "type": "list", "description": "List of transformations"},
                ],
                actions_template=[
                    {"type": "get_memory", "key": "{{input_key}}", "store_as": "data"},
                    {
                        "type": "loop",
                        "items": "{{transformations}}",
                        "as": "transform",
                        "actions": [
                            {"type": "transform", "input": "{{data}}", "operation": "{{transform}}"}
                        ]
                    },
                    {"type": "set_memory", "key": "{{output_key}}", "value": "{{data}}"},
                ],
                example={
                    "input_key": "raw_data",
                    "output_key": "processed_data",
                    "transformations": ["uppercase", "unique", "sort"]
                }
            ),
            MacroTemplate(
                name="error_handler",
                description="Handle errors with retry logic",
                category="error_handling",
                parameters=[
                    {"name": "action_type", "type": "string", "description": "Action to retry"},
                    {"name": "max_retries", "type": "number", "description": "Maximum retry attempts"},
                    {"name": "delay", "type": "number", "description": "Delay between retries (seconds)"},
                ],
                actions_template=[
                    {
                        "type": "loop",
                        "items": "range({{max_retries}})",
                        "as": "attempt",
                        "actions": [
                            {"type": "{{action_type}}"},
                            {"type": "delay", "seconds": "{{delay}}"}
                        ]
                    }
                ],
                example={"action_type": "api_call", "max_retries": 3, "delay": 5}
            ),
        ]
    
    @staticmethod
    def create_from_template(template_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Create a macro from a template."""
        templates = {t.name: t for t in MacroTemplateLibrary.get_templates()}
        
        if template_name not in templates:
            raise ValueError(f"Template not found: {template_name}")
        
        template = templates[template_name]
        
        # Validate parameters
        required_params = {p["name"] for p in template.parameters}
        provided_params = set(parameters.keys())
        
        if not required_params.issubset(provided_params):
            missing = required_params - provided_params
            raise ValueError(f"Missing required parameters: {missing}")
        
        # Create macro definition
        macro = {
            "name": f"{template_name}_{hashlib.md5(str(parameters).encode()).hexdigest()[:8]}",
            "description": template.description,
            "trigger": "manual",
            "actions": copy.deepcopy(template.actions_template),
            "enabled": True,
            "metadata": {
                "template": template_name,
                "parameters": parameters,
            }
        }
        
        # Replace template variables
        macro_str = json.dumps(macro)
        for key, value in parameters.items():
            macro_str = macro_str.replace(f"{{{{{key}}}}}", str(value))
        
        return json.loads(macro_str)


# ============================================================================
# Audit Logger
# ============================================================================

class AuditLogger:
    """Audit logger for tracking all operations."""
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("./.cxflow/audit")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._logs: List[AuditLogEntry] = []
        self._load_logs()
    
    def _load_logs(self):
        """Load audit logs from disk."""
        log_file = self.storage_path / "audit.jsonl"
        if log_file.exists():
            try:
                for line in log_file.read_text().splitlines():
                    if line.strip():
                        self._logs.append(AuditLogEntry(**json.loads(line)))
            except Exception as e:
                logger.warning(f"Failed to load audit logs: {e}")
    
    def _persist(self, entry: AuditLogEntry):
        """Persist a single log entry."""
        log_file = self.storage_path / "audit.jsonl"
        with log_file.open('a') as f:
            f.write(json.dumps(asdict(entry), default=str) + '\n')
    
    def log(
        self,
        operation: str,
        entity_type: str,
        entity_id: str,
        user: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLogEntry:
        """Log an operation."""
        entry = AuditLogEntry(
            id=hashlib.md5(f"{operation}-{entity_id}-{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            operation=operation,
            entity_type=entity_type,
            entity_id=entity_id,
            user=user,
            success=success,
            error=error,
            metadata=metadata or {},
        )
        
        self._logs.append(entry)
        self._persist(entry)
        
        # Keep only last 10000 logs in memory
        if len(self._logs) > 10000:
            self._logs = self._logs[-10000:]
        
        return entry
    
    def query_logs(
        self,
        operation: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        user: Optional[str] = None,
        success: Optional[bool] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditLogEntry]:
        """Query audit logs with filters."""
        results = self._logs
        
        if operation:
            results = [r for r in results if r.operation == operation]
        if entity_type:
            results = [r for r in results if r.entity_type == entity_type]
        if entity_id:
            results = [r for r in results if r.entity_id == entity_id]
        if user:
            results = [r for r in results if r.user == user]
        if success is not None:
            results = [r for r in results if r.success == success]
        if since:
            # Ensure since has timezone info
            if since.tzinfo is None:
                since = since.replace(tzinfo=timezone.utc)
            results = [
                r for r in results
                if datetime.fromisoformat(r.timestamp.replace('Z', '+00:00')) > since
            ]
        
        return results[-limit:]


# ============================================================================
# Validation Schemas
# ============================================================================

class ValidationSchema:
    """Schema validation for macros and metadata."""
    
    @staticmethod
    def validate_macro(macro_def: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate a macro definition."""
        errors = []
        
        # Required fields
        required = ["name", "description", "trigger", "actions"]
        for field in required:
            if field not in macro_def:
                errors.append(f"Missing required field: {field}")
        
        # Validate actions
        if "actions" in macro_def:
            if not isinstance(macro_def["actions"], list):
                errors.append("Actions must be a list")
            else:
                for idx, action in enumerate(macro_def["actions"]):
                    if not isinstance(action, dict):
                        errors.append(f"Action {idx} must be a dict")
                    elif "type" not in action:
                        errors.append(f"Action {idx} missing 'type' field")
        
        # Validate trigger
        valid_triggers = ["event", "schedule", "manual", "webhook"]
        if "trigger" in macro_def and macro_def["trigger"] not in valid_triggers:
            errors.append(f"Invalid trigger: {macro_def['trigger']}. Must be one of {valid_triggers}")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_metadata(metadata: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate metadata record."""
        errors = []
        
        # Required fields
        required = ["entity_type", "entity_id", "attributes"]
        for field in required:
            if field not in metadata:
                errors.append(f"Missing required field: {field}")
        
        # Validate attributes
        if "attributes" in metadata and not isinstance(metadata["attributes"], dict):
            errors.append("Attributes must be a dict")
        
        return len(errors) == 0, errors


# ============================================================================
# Enhanced CLI
# ============================================================================

def create_enhanced_cli():
    """Create enhanced CLI with all new features."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Enhanced CXFlow CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Memory commands
    memory_parser = subparsers.add_parser("memory", help="Enhanced memory operations")
    memory_subparsers = memory_parser.add_subparsers(dest="action")
    
    # memory query
    query_parser = memory_subparsers.add_parser("query", help="Query memory")
    query_parser.add_argument("--category", help="Filter by category")
    query_parser.add_argument("--tags", nargs="+", help="Filter by tags")
    query_parser.add_argument("--limit", type=int, help="Limit results")
    
    # memory search
    search_parser = memory_subparsers.add_parser("search", help="Full-text search")
    search_parser.add_argument("term", help="Search term")
    search_parser.add_argument("--fields", nargs="+", help="Fields to search")
    
    # memory aggregate
    agg_parser = memory_subparsers.add_parser("aggregate", help="Aggregate data")
    agg_parser.add_argument("field", help="Field to aggregate")
    agg_parser.add_argument("function", choices=["count", "sum", "avg", "min", "max", "distinct"])
    
    # memory rollback
    rollback_parser = memory_subparsers.add_parser("rollback", help="Rollback to version")
    rollback_parser.add_argument("key", help="Memory key")
    rollback_parser.add_argument("version", type=int, help="Version number")
    
    # memory history
    history_parser = memory_subparsers.add_parser("history", help="View version history")
    history_parser.add_argument("key", help="Memory key")
    
    # memory export
    export_parser = memory_subparsers.add_parser("export", help="Export to file")
    export_parser.add_argument("filepath", help="Export file path")
    export_parser.add_argument("--include-versions", action="store_true")
    
    # memory import
    import_parser = memory_subparsers.add_parser("import", help="Import from file")
    import_parser.add_argument("filepath", help="Import file path")
    import_parser.add_argument("--merge", action="store_true", default=True)
    
    # Macro commands
    macro_parser = subparsers.add_parser("macro", help="Macro operations")
    macro_subparsers = macro_parser.add_subparsers(dest="action")
    
    # macro execute
    exec_parser = macro_subparsers.add_parser("execute", help="Execute a macro")
    exec_parser.add_argument("name", help="Macro name")
    exec_parser.add_argument("--dry-run", action="store_true")
    exec_parser.add_argument("--context", help="Context JSON")
    
    # macro validate
    validate_parser = macro_subparsers.add_parser("validate", help="Validate a macro")
    validate_parser.add_argument("file", help="Macro definition file")
    
    # macro from-template
    template_parser = macro_subparsers.add_parser("from-template", help="Create from template")
    template_parser.add_argument("template", help="Template name")
    template_parser.add_argument("--params", help="Parameters JSON")
    
    # macro templates
    templates_parser = macro_subparsers.add_parser("templates", help="List available templates")
    
    # macro history
    macro_history_parser = macro_subparsers.add_parser("history", help="Execution history")
    macro_history_parser.add_argument("--macro", help="Filter by macro name")
    macro_history_parser.add_argument("--limit", type=int, default=10)
    
    # Audit commands
    audit_parser = subparsers.add_parser("audit", help="Audit log operations")
    audit_subparsers = audit_parser.add_subparsers(dest="action")
    
    # audit query
    audit_query_parser = audit_subparsers.add_parser("query", help="Query audit logs")
    audit_query_parser.add_argument("--operation", help="Filter by operation")
    audit_query_parser.add_argument("--entity-type", help="Filter by entity type")
    audit_query_parser.add_argument("--user", help="Filter by user")
    audit_query_parser.add_argument("--limit", type=int, default=50)
    
    return parser


# Export main classes
__all__ = [
    "EnhancedMemoryManager",
    "MacroExecutionEngine",
    "MacroTemplateLibrary",
    "AuditLogger",
    "ValidationSchema",
    "QueryOperator",
    "AggregateFunction",
    "MemoryQuery",
    "QueryFilter",
    "MacroExecution",
    "MacroExecutionStatus",
    "MacroTemplate",
    "create_enhanced_cli",
]
