# Enhanced CXFlow Capabilities

This document describes the significantly enhanced capabilities of the .cxflow system.

## Table of Contents

1. [Overview](#overview)
2. [Enhanced Memory Manager](#enhanced-memory-manager)
3. [Macro Execution Engine](#macro-execution-engine)
4. [Macro Templates](#macro-templates)
5. [Audit Logging](#audit-logging)
6. [Validation Schemas](#validation-schemas)
7. [CLI Tools](#cli-tools)
8. [Examples](#examples)

## Overview

The enhanced .cxflow system provides a comprehensive suite of capabilities for managing memory, executing automation macros, and tracking all operations with full audit trails.

### Key Features

- **Advanced Query Engine**: Filter, search, and aggregate memory with SQL-like capabilities
- **Macro Execution**: Actually execute macros with conditional logic, loops, and error handling
- **Versioning**: Full version history with rollback capabilities
- **Audit Trail**: Complete audit logging for compliance and debugging
- **Templates**: Reusable macro templates for common patterns
- **Batch Operations**: Efficient bulk operations for memory and metadata
- **Encryption**: Optional encryption for sensitive data
- **Export/Import**: Easy backup and migration capabilities

## Enhanced Memory Manager

The `EnhancedMemoryManager` extends the basic memory manager with powerful new features.

### Initialization

```python
from workflows.cxflow_enhanced import EnhancedMemoryManager

manager = EnhancedMemoryManager(
    storage_path=Path("./.cxflow/memory"),
    enable_versioning=True,      # Track all changes
    enable_encryption=False,     # Encrypt sensitive data
    encryption_key=None          # Auto-generate if not provided
)
```

### Advanced Querying

Build complex queries with filtering, sorting, and pagination:

```python
from workflows.cxflow_enhanced import MemoryQuery, QueryOperator

# Create a query
query = MemoryQuery()

# Filter by category
query.with_category("config")

# Filter by tags
query.with_tags(["important", "production"])

# Add custom filters
query.add_filter("metadata.priority", QueryOperator.GT, 5)
query.add_filter("value.status", QueryOperator.EQ, "active")

# Sort results
query.sort("metadata.priority", desc=True)

# Paginate
query.paginate(limit=10, offset=0)

# Execute query
results = manager.query(query)
```

### Query Operators

- `EQ` - Equal to
- `NE` - Not equal to
- `GT` - Greater than
- `GTE` - Greater than or equal
- `LT` - Less than
- `LTE` - Less than or equal
- `IN` - In list
- `NIN` - Not in list
- `CONTAINS` - Contains substring
- `REGEX` - Regular expression match
- `EXISTS` - Field exists

### Full-Text Search

Search across all memory entries:

```python
# Search in all text fields
results = manager.search("important project")

# Search in specific fields
results = manager.search(
    "error",
    fields=["key", "value", "metadata.description"]
)
```

### Aggregations

Perform aggregations on query results:

```python
from workflows.cxflow_enhanced import AggregateFunction

# Count entries
count = manager.aggregate("key", AggregateFunction.COUNT)

# Average of numeric field
avg_priority = manager.aggregate(
    "metadata.priority",
    AggregateFunction.AVG,
    query=MemoryQuery().with_category("config")
)

# Get distinct values
unique_categories = manager.aggregate(
    "category",
    AggregateFunction.DISTINCT
)
```

### Versioning and Rollback

Track all changes with full version history:

```python
# Set with versioning
manager.set(
    "config_key",
    {"theme": "dark"},
    user="admin",
    comment="Changed to dark theme"
)

# Update
manager.set(
    "config_key",
    {"theme": "light"},
    user="admin",
    comment="Changed to light theme"
)

# View history
history = manager.get_history("config_key")
for version in history:
    print(f"v{version.version}: {version.operation} by {version.user}")
    print(f"  Comment: {version.comment}")

# Rollback to previous version
manager.rollback("config_key", version=1)
```

### Batch Operations

Perform bulk operations efficiently:

```python
# Batch set
entries = [
    {"key": "k1", "value": "v1", "category": "test"},
    {"key": "k2", "value": "v2", "category": "test"},
    {"key": "k3", "value": "v3", "category": "test"},
]
created_keys = manager.batch_set(entries, user="admin")

# Batch delete
deleted_count = manager.batch_delete(["k1", "k2"], user="admin")
```

### Export and Import

Backup and restore memory:

```python
# Export to file
manager.export_to_file(
    Path("backup.json"),
    include_versions=True
)

# Import from file
manager.import_from_file(
    Path("backup.json"),
    merge=True  # Merge with existing data
)
```

## Macro Execution Engine

The `MacroExecutionEngine` can actually execute macros with advanced features.

### Initialization

```python
from workflows.cxflow_enhanced import (
    MacroExecutionEngine,
    EnhancedMemoryManager
)

memory_manager = EnhancedMemoryManager()
engine = MacroExecutionEngine(memory_manager)
```

### Executing Macros

```python
# Define a macro
macro = {
    "name": "data_sync",
    "description": "Sync data to external system",
    "trigger": "manual",
    "actions": [
        {"type": "log", "message": "Starting sync..."},
        {"type": "collect", "source": "memory"},
        {"type": "sync", "destination": "power_automate"},
        {"type": "log", "message": "Sync completed"}
    ]
}

# Execute
execution = engine.execute_macro(macro)

# Check results
print(f"Status: {execution.status.value}")
print(f"Steps completed: {execution.steps_completed}/{execution.steps_total}")
print(f"Duration: {execution.duration_ms}ms")
```

### Conditional Logic

Add if/else logic to macros:

```python
macro = {
    "name": "conditional_alert",
    "actions": [
        {
            "type": "condition",
            "if": "{{context.error_count}} > 10",
            "then": [
                {"type": "notify", "channel": "slack", "message": "High errors!"}
            ],
            "else": [
                {"type": "log", "message": "Error count normal"}
            ]
        }
    ]
}

# Execute with context
execution = engine.execute_macro(
    macro,
    context={"error_count": 15}
)
```

### Loops

Iterate over collections:

```python
macro = {
    "name": "process_items",
    "actions": [
        {
            "type": "loop",
            "items": ["item1", "item2", "item3"],
            "as": "item",
            "actions": [
                {"type": "log", "message": "Processing {{item}}"},
                {"type": "set_memory", "key": "processed_{{item}}", "value": True}
            ]
        }
    ]
}

execution = engine.execute_macro(macro)
```

### Data Transformations

Transform data in macros:

```python
macro = {
    "name": "transform_data",
    "actions": [
        {
            "type": "transform",
            "input": "hello world",
            "operation": "uppercase",
            "store_as": "upper_text"
        },
        {
            "type": "log",
            "message": "Result: {{upper_text}}"
        }
    ]
}
```

Supported transformations:
- `uppercase` - Convert to uppercase
- `lowercase` - Convert to lowercase
- `reverse` - Reverse string or list
- `sort` - Sort list
- `unique` - Get unique values from list
- `count` - Count items

### Variable Resolution

Use `{{variable}}` syntax in actions:

```python
macro = {
    "name": "dynamic_message",
    "actions": [
        {
            "type": "log",
            "message": "Hello {{context.user}}, you have {{context.count}} messages"
        }
    ]
}

execution = engine.execute_macro(
    macro,
    context={"user": "Alice", "count": 5}
)
```

### Dry Run

Validate macros without executing:

```python
execution = engine.execute_macro(macro, dry_run=True)
# Returns what would be executed without actually doing it
```

### Custom Action Handlers

Register custom action types:

```python
def custom_handler(action: Dict, context: Dict) -> Dict:
    """Handle custom action type."""
    print(f"Custom action: {action}")
    return {"success": True, "result": "Custom action executed"}

engine.register_action_handler("custom_action", custom_handler)

# Now you can use it in macros
macro = {
    "name": "custom_macro",
    "actions": [
        {"type": "custom_action", "param": "value"}
    ]
}
```

## Macro Templates

Reusable templates for common patterns.

### Available Templates

```python
from workflows.cxflow_enhanced import MacroTemplateLibrary

# List all templates
templates = MacroTemplateLibrary.get_templates()
for template in templates:
    print(f"{template.name}: {template.description}")
    print(f"  Category: {template.category}")
    print(f"  Parameters: {[p['name'] for p in template.parameters]}")
```

Built-in templates:

1. **scheduled_sync** - Sync data on a schedule
2. **conditional_notification** - Send notification based on condition
3. **data_pipeline** - Process data through transformation pipeline
4. **error_handler** - Handle errors with retry logic

### Creating Macros from Templates

```python
# Create from template
macro = MacroTemplateLibrary.create_from_template(
    "scheduled_sync",
    {
        "source": "metrics",
        "destination": "power_automate",
        "schedule": "0 */6 * * *"
    }
)

# Execute the generated macro
execution = engine.execute_macro(macro)
```

### Example: Conditional Notification

```python
macro = MacroTemplateLibrary.create_from_template(
    "conditional_notification",
    {
        "condition_field": "error_count",
        "threshold": 10,
        "channel": "slack"
    }
)

execution = engine.execute_macro(
    macro,
    context={"error_count": 15}
)
```

### Example: Data Pipeline

```python
macro = MacroTemplateLibrary.create_from_template(
    "data_pipeline",
    {
        "input_key": "raw_data",
        "output_key": "processed_data",
        "transformations": ["uppercase", "unique", "sort"]
    }
)
```

## Audit Logging

Complete audit trail for all operations.

### Initialization

```python
from workflows.cxflow_enhanced import AuditLogger

audit = AuditLogger(storage_path=Path("./.cxflow/audit"))
```

### Logging Operations

```python
# Log successful operation
audit.log(
    operation="write",
    entity_type="memory",
    entity_id="config_key",
    user="admin",
    success=True
)

# Log failed operation
audit.log(
    operation="execute",
    entity_type="macro",
    entity_id="sync_macro",
    user="system",
    success=False,
    error="Connection timeout",
    metadata={"duration_ms": 30000}
)
```

### Querying Audit Logs

```python
from datetime import datetime, timedelta

# All recent operations
logs = audit.query_logs(limit=100)

# Failed operations
failed = audit.query_logs(success=False)

# Operations by user
admin_logs = audit.query_logs(user="admin", limit=50)

# Operations by type
memory_ops = audit.query_logs(entity_type="memory")

# Operations in time range
since = datetime.now() - timedelta(hours=24)
recent = audit.query_logs(since=since)

# Specific operation
writes = audit.query_logs(
    operation="write",
    entity_type="memory",
    success=True
)
```

### Compliance Reporting

```python
# Generate compliance report
from datetime import datetime, timedelta

start_date = datetime.now() - timedelta(days=30)
all_ops = audit.query_logs(since=start_date, limit=10000)

report = {
    "period": "Last 30 days",
    "total_operations": len(all_ops),
    "by_operation": {},
    "by_user": {},
    "failures": []
}

for log in all_ops:
    # Count by operation type
    report["by_operation"][log.operation] = \
        report["by_operation"].get(log.operation, 0) + 1
    
    # Count by user
    report["by_user"][log.user or "system"] = \
        report["by_user"].get(log.user or "system", 0) + 1
    
    # Track failures
    if not log.success:
        report["failures"].append({
            "operation": log.operation,
            "entity": f"{log.entity_type}:{log.entity_id}",
            "error": log.error,
            "timestamp": log.timestamp
        })

print(json.dumps(report, indent=2))
```

## Validation Schemas

Validate macro and metadata definitions.

### Validating Macros

```python
from workflows.cxflow_enhanced import ValidationSchema

macro_def = {
    "name": "test_macro",
    "description": "Test macro",
    "trigger": "manual",
    "actions": [
        {"type": "log", "message": "Test"}
    ]
}

is_valid, errors = ValidationSchema.validate_macro(macro_def)

if is_valid:
    print("✅ Macro is valid")
else:
    print("❌ Validation errors:")
    for error in errors:
        print(f"  - {error}")
```

### Validating Metadata

```python
metadata = {
    "entity_type": "project",
    "entity_id": "cxflow",
    "attributes": {
        "version": "2.0.0",
        "status": "active"
    }
}

is_valid, errors = ValidationSchema.validate_metadata(metadata)
```

## CLI Tools

Enhanced command-line interface for all features.

### Memory Operations

```bash
# Query memory
python -m workflows.cxflow_enhanced memory query --category config --limit 10

# Full-text search
python -m workflows.cxflow_enhanced memory search "important" --fields key value

# Aggregate data
python -m workflows.cxflow_enhanced memory aggregate metadata.priority count

# View history
python -m workflows.cxflow_enhanced memory history config_key

# Rollback to version
python -m workflows.cxflow_enhanced memory rollback config_key 2

# Export
python -m workflows.cxflow_enhanced memory export backup.json --include-versions

# Import
python -m workflows.cxflow_enhanced memory import backup.json --merge
```

### Macro Operations

```bash
# Execute macro
python -m workflows.cxflow_enhanced macro execute daily_sync

# Dry run
python -m workflows.cxflow_enhanced macro execute daily_sync --dry-run

# Execute with context
python -m workflows.cxflow_enhanced macro execute alert_macro --context '{"error_count": 15}'

# Validate macro
python -m workflows.cxflow_enhanced macro validate macro_def.json

# Create from template
python -m workflows.cxflow_enhanced macro from-template scheduled_sync \
  --params '{"source": "metrics", "destination": "power_automate", "schedule": "0 * * * *"}'

# List templates
python -m workflows.cxflow_enhanced macro templates

# View execution history
python -m workflows.cxflow_enhanced macro history --macro daily_sync --limit 20
```

### Audit Operations

```bash
# Query audit logs
python -m workflows.cxflow_enhanced audit query --operation write --limit 50

# Filter by entity type
python -m workflows.cxflow_enhanced audit query --entity-type memory

# Filter by user
python -m workflows.cxflow_enhanced audit query --user admin
```

## Examples

### Example 1: Automated Monitoring

```python
from workflows.cxflow_enhanced import (
    EnhancedMemoryManager,
    MacroExecutionEngine,
    MacroTemplateLibrary,
    AuditLogger
)
from pathlib import Path

# Initialize
memory = EnhancedMemoryManager(Path("./.cxflow/memory"))
engine = MacroExecutionEngine(memory)
audit = AuditLogger()

# Store metrics
memory.set(
    "system_metrics",
    {"cpu": 85, "memory": 75, "disk": 60},
    category="metrics",
    tags=["system", "monitoring"]
)

# Create monitoring macro
macro = MacroTemplateLibrary.create_from_template(
    "conditional_notification",
    {
        "condition_field": "cpu",
        "threshold": 80,
        "channel": "slack"
    }
)

# Execute
execution = engine.execute_macro(
    macro,
    context=memory.get("system_metrics")["value"]
)

# Log execution
audit.log(
    "execute",
    "macro",
    macro["name"],
    success=(execution.status.value == "completed")
)
```

### Example 2: Data Processing Pipeline

```python
# Create pipeline macro
pipeline = MacroTemplateLibrary.create_from_template(
    "data_pipeline",
    {
        "input_key": "raw_customer_data",
        "output_key": "processed_customer_data",
        "transformations": ["uppercase", "unique", "sort"]
    }
)

# Store raw data
memory.set(
    "raw_customer_data",
    ["alice", "bob", "Alice", "charlie", "bob"],
    category="data"
)

# Execute pipeline
execution = engine.execute_macro(pipeline)

# Retrieve processed data
processed = memory.get("processed_customer_data")
print(processed["value"])  # ['ALICE', 'BOB', 'CHARLIE']
```

### Example 3: Version Control Workflow

```python
# Store configuration
memory.set(
    "app_config",
    {"debug": False, "timeout": 30},
    user="admin",
    comment="Initial configuration"
)

# Update configuration
memory.set(
    "app_config",
    {"debug": True, "timeout": 30},
    user="developer",
    comment="Enabled debug mode"
)

memory.set(
    "app_config",
    {"debug": True, "timeout": 60},
    user="developer",
    comment="Increased timeout"
)

# View history
history = memory.get_history("app_config")
for v in history:
    print(f"v{v.version}: {v.comment} (by {v.user})")

# Rollback to stable version
memory.rollback("app_config", 1)
```

### Example 4: Audit and Compliance

```python
from datetime import datetime, timedelta

# Query all write operations in last 24 hours
since = datetime.now() - timedelta(hours=24)
writes = audit.query_logs(
    operation="write",
    since=since
)

# Generate report
report = {
    "total_writes": len(writes),
    "by_user": {},
    "by_entity": {}
}

for log in writes:
    user = log.user or "system"
    report["by_user"][user] = report["by_user"].get(user, 0) + 1
    
    entity = log.entity_type
    report["by_entity"][entity] = report["by_entity"].get(entity, 0) + 1

print(json.dumps(report, indent=2))
```

## Performance Considerations

### Indexing

The enhanced memory manager automatically indexes entries by:
- Category
- Tags

This provides fast filtering for common queries.

### Batch Operations

Use batch operations for bulk inserts/deletes:

```python
# More efficient than individual sets
manager.batch_set(entries, user="admin")
```

### Query Optimization

- Use category and tag filters first (indexed)
- Limit results with pagination
- Use specific field filters instead of full-text search when possible

### Version History

Version history is limited to 50 versions per entry by default. Older versions are automatically pruned.

## Security

### Encryption

Enable encryption for sensitive data:

```python
manager = EnhancedMemoryManager(
    enable_encryption=True,
    encryption_key=your_secure_key
)

# Mark entries as sensitive
manager.set(
    "api_key",
    "secret",
    metadata={"sensitive": True}
)
```

### Audit Trail

All operations are logged with:
- Timestamp
- User
- Operation type
- Success/failure
- Error details

### Access Control

Implement access control in your application layer:

```python
def authorized_operation(user, operation, entity):
    # Check permissions
    if not has_permission(user, operation, entity):
        audit.log(
            operation,
            entity["type"],
            entity["id"],
            user=user,
            success=False,
            error="Unauthorized"
        )
        raise PermissionError("Unauthorized")
    
    # Perform operation
    result = perform_operation(operation, entity)
    
    # Log success
    audit.log(
        operation,
        entity["type"],
        entity["id"],
        user=user,
        success=True
    )
    
    return result
```

## Migration Guide

### From Basic to Enhanced Memory Manager

```python
# Old code
from workflows.power_automate_sync import MemoryManager
manager = MemoryManager()

# New code
from workflows.cxflow_enhanced import EnhancedMemoryManager
manager = EnhancedMemoryManager(enable_versioning=True)

# API is backwards compatible
manager.set("key", "value", category="test")
entry = manager.get("key")
```

The enhanced manager is fully backwards compatible with the basic manager API.

## Troubleshooting

### Memory Not Persisting

Ensure the storage path is writable:

```python
storage_path = Path("./.cxflow/memory")
storage_path.mkdir(parents=True, exist_ok=True)
```

### Macro Execution Failures

Use dry-run to validate:

```python
execution = engine.execute_macro(macro, dry_run=True)
print(execution.results)
```

### Query Performance

Add indexes for frequently queried fields, or use batch operations.

### Encryption Issues

Ensure the `cryptography` package is installed:

```bash
pip install cryptography
```

## Support

For issues or questions:
- Check the examples in `workflows/examples/`
- Review audit logs for debugging
- Use dry-run mode for macros
- Enable debug logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```
