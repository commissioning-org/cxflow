# Enhanced CXFlow Capabilities - Quick Start

This guide shows how to quickly get started with the enhanced .cxflow capabilities.

## Overview

The enhanced .cxflow system provides powerful new features for managing memory, executing automation macros, and tracking operations:

- **Advanced Query Engine**: Filter, search, and aggregate data
- **Macro Execution**: Actually run macros with conditional logic
- **Versioning**: Full history with rollback capabilities
- **Audit Trail**: Complete logging for compliance
- **Templates**: Reusable macro patterns
- **Batch Operations**: Efficient bulk operations
- **Encryption**: Secure sensitive data

## Installation

No additional installation required. The enhanced capabilities are built on top of the existing CXFlow system.

Optional: For encryption support, install:
```bash
pip install cryptography
```

## Quick Examples

### 1. Enhanced Memory with Querying

```python
from workflows.cxflow_enhanced import EnhancedMemoryManager, MemoryQuery, QueryOperator

# Initialize
manager = EnhancedMemoryManager(enable_versioning=True)

# Store data
manager.set(
    "user_config",
    {"theme": "dark", "language": "en"},
    category="config",
    tags=["user", "preferences"],
    metadata={"priority": 5}
)

# Query with filters
query = MemoryQuery()
query.with_category("config")
query.add_filter("metadata.priority", QueryOperator.GTE, 5)
results = manager.query(query)

# Full-text search
search_results = manager.search("theme")

# Aggregate data
count = manager.aggregate("key", AggregateFunction.COUNT)
```

### 2. Macro Execution

```python
from workflows.cxflow_enhanced import MacroExecutionEngine

# Initialize
engine = MacroExecutionEngine(memory_manager)

# Execute a macro
macro = {
    "name": "data_sync",
    "actions": [
        {"type": "log", "message": "Starting sync..."},
        {"type": "sync", "destination": "power_automate"}
    ]
}

execution = engine.execute_macro(macro)
print(f"Status: {execution.status.value}")
```

### 3. Macro with Conditionals

```python
macro = {
    "name": "alert_on_errors",
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

execution = engine.execute_macro(macro, context={"error_count": 15})
```

### 4. Using Templates

```python
from workflows.cxflow_enhanced import MacroTemplateLibrary

# List available templates
templates = MacroTemplateLibrary.get_templates()

# Create from template
macro = MacroTemplateLibrary.create_from_template(
    "scheduled_sync",
    {
        "source": "metrics",
        "destination": "power_automate",
        "schedule": "0 */6 * * *"
    }
)

# Execute
execution = engine.execute_macro(macro)
```

### 5. Versioning and Rollback

```python
# Update configuration (versioned automatically)
manager.set("config", {"v": 1}, user="admin", comment="Initial version")
manager.set("config", {"v": 2}, user="admin", comment="Updated version")

# View history
history = manager.get_history("config")
for v in history:
    print(f"v{v.version}: {v.comment}")

# Rollback
manager.rollback("config", version=1)
```

### 6. Audit Logging

```python
from workflows.cxflow_enhanced import AuditLogger

audit = AuditLogger()

# Log operations
audit.log("write", "memory", "config_key", user="admin", success=True)

# Query logs
failed_ops = audit.query_logs(success=False)
user_ops = audit.query_logs(user="admin", limit=50)
```

### 7. Integrated Workflow

```python
from workflows.enhanced_integration import EnhancedCXFlowWorkflow

# Initialize
workflow = EnhancedCXFlowWorkflow(enable_versioning=True)

# Query memory
results = workflow.query_memory(
    category="config",
    tags=["production"],
    filters=[{"field": "metadata.priority", "op": "gt", "value": 5}]
)

# Execute macro
execution = workflow.execute_macro_by_name("daily_sync")

# Get audit report
report = workflow.get_audit_report(entity_type="memory", limit=100)
```

## Key Features Demonstrated

### Advanced Querying

Build complex queries with multiple filters:

```python
query = MemoryQuery()
query.with_category("metrics")
query.with_tags(["important", "production"])
query.add_filter("value.count", QueryOperator.GT, 1000)
query.add_filter("metadata.priority", QueryOperator.IN, [5, 10])
query.sort("metadata.priority", desc=True)
query.paginate(limit=20, offset=0)

results = manager.query(query)
```

### Data Transformations in Macros

```python
macro = {
    "name": "transform_data",
    "actions": [
        {
            "type": "transform",
            "input": ["alice", "bob", "alice"],
            "operation": "unique",
            "store_as": "unique_users"
        },
        {
            "type": "transform",
            "input": "{{unique_users}}",
            "operation": "sort",
            "store_as": "sorted_users"
        },
        {
            "type": "log",
            "message": "Processed users: {{sorted_users}}"
        }
    ]
}
```

### Batch Operations

```python
# Batch insert
entries = [
    {"key": f"metric_{i}", "value": i, "category": "metrics"}
    for i in range(100)
]
created_keys = manager.batch_set(entries)

# Batch delete
deleted_count = manager.batch_delete(created_keys[:50])
```

### Export and Import

```python
# Export
manager.export_to_file(
    Path("backup.json"),
    include_versions=True
)

# Import
manager.import_from_file(
    Path("backup.json"),
    merge=True
)
```

## CLI Usage

### Memory Operations

```bash
# Query memory
python -m workflows.cxflow_enhanced memory query --category config

# Search
python -m workflows.cxflow_enhanced memory search "important"

# View history
python -m workflows.cxflow_enhanced memory history config_key

# Rollback
python -m workflows.cxflow_enhanced memory rollback config_key 2
```

### Macro Operations

```bash
# Execute macro
python -m workflows.cxflow_enhanced macro execute daily_sync

# Dry run
python -m workflows.cxflow_enhanced macro execute daily_sync --dry-run

# List templates
python -m workflows.cxflow_enhanced macro templates

# Create from template
python -m workflows.cxflow_enhanced macro from-template scheduled_sync \
  --params '{"source": "metrics", "destination": "power_automate"}'
```

### Audit Operations

```bash
# Query logs
python -m workflows.cxflow_enhanced audit query --operation write

# Filter by entity
python -m workflows.cxflow_enhanced audit query --entity-type memory --limit 50
```

## Running Examples

### Comprehensive Demo

```bash
python workflows/examples/enhanced_usage.py
```

This runs 5 demos:
1. Enhanced memory manager
2. Macro execution engine
3. Macro templates
4. Audit logging
5. Complete workflow

### Integration Test

```bash
python workflows/examples/integration_test.py
```

Tests integration between enhanced features and existing Power Automate sync.

## Available Templates

1. **scheduled_sync** - Automated data synchronization
   - Parameters: source, destination, schedule
   
2. **conditional_notification** - Alert based on conditions
   - Parameters: condition_field, threshold, channel
   
3. **data_pipeline** - Multi-stage data transformations
   - Parameters: input_key, output_key, transformations
   
4. **error_handler** - Retry logic with exponential backoff
   - Parameters: action_type, max_retries, delay

## Supported Query Operators

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

## Supported Transformations

- `uppercase` - Convert to uppercase
- `lowercase` - Convert to lowercase
- `reverse` - Reverse string or list
- `sort` - Sort list
- `unique` - Get unique values
- `count` - Count items

## Documentation

- **Complete Guide**: `docs/CXFLOW_ENHANCED.md`
- **API Reference**: In the complete guide
- **Examples**: `workflows/examples/`

## Performance Tips

1. Use category and tag filters (indexed) before custom filters
2. Use batch operations for bulk inserts/deletes
3. Limit query results with pagination
4. Use specific field searches instead of full-text when possible

## Security

### Enable Encryption

```python
manager = EnhancedMemoryManager(
    enable_encryption=True,
    encryption_key=your_secure_key
)

# Mark as sensitive
manager.set(
    "api_key",
    "secret",
    metadata={"sensitive": True}
)
```

### Audit Trail

All operations are automatically logged with:
- Timestamp
- User
- Operation type
- Success/failure
- Error details

## Migration from Basic Manager

The enhanced manager is fully backwards compatible:

```python
# Old code
from workflows.power_automate_sync import MemoryManager
manager = MemoryManager()

# New code (drop-in replacement)
from workflows.cxflow_enhanced import EnhancedMemoryManager
manager = EnhancedMemoryManager()

# All old methods still work
manager.set("key", "value")
entry = manager.get("key")
```

## Troubleshooting

### Import Errors

Ensure you're in the correct directory:
```bash
cd /path/to/cxflow
python -m workflows.examples.enhanced_usage
```

### Encryption Not Available

Install cryptography:
```bash
pip install cryptography
```

### Storage Path Issues

Ensure the directory is writable:
```python
from pathlib import Path
storage_path = Path("./.cxflow/memory")
storage_path.mkdir(parents=True, exist_ok=True)
```

## Next Steps

1. Run the examples: `python workflows/examples/enhanced_usage.py`
2. Read the complete guide: `docs/CXFLOW_ENHANCED.md`
3. Try the integration test: `python workflows/examples/integration_test.py`
4. Explore available templates
5. Build your own macros and workflows

## Support

For questions or issues:
- Check `docs/CXFLOW_ENHANCED.md` for complete documentation
- Review examples in `workflows/examples/`
- Enable debug logging: `logging.basicConfig(level=logging.DEBUG)`
- Use dry-run mode for macros
- Review audit logs for debugging

## License

Same as the main CXFlow project.
