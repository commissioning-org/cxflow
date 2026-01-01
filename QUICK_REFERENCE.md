# Enhanced CXFlow - Quick Reference Card

## Installation

No installation required. Enhanced capabilities are built-in.

Optional for encryption:
```bash
pip install cryptography
```

## Basic Usage

### Enhanced Memory

```python
from workflows import EnhancedMemoryManager

# Initialize
manager = EnhancedMemoryManager(enable_versioning=True)

# Set
manager.set("key", "value", category="config", tags=["prod"], user="admin")

# Get
entry = manager.get("key")

# Query
from workflows import MemoryQuery, QueryOperator
query = MemoryQuery().with_category("config")
query.add_filter("metadata.priority", QueryOperator.GT, 5)
results = manager.query(query)

# Search
results = manager.search("term", fields=["key", "value"])

# Aggregate
from workflows import AggregateFunction
count = manager.aggregate("key", AggregateFunction.COUNT)

# History & Rollback
history = manager.get_history("key")
manager.rollback("key", version=2)

# Batch
keys = manager.batch_set([{"key": "k1", "value": "v1"}, ...])
count = manager.batch_delete(["k1", "k2"])

# Export/Import
manager.export_to_file(Path("backup.json"), include_versions=True)
manager.import_from_file(Path("backup.json"), merge=True)
```

### Macro Execution

```python
from workflows import MacroExecutionEngine, MacroTemplateLibrary

# Initialize
engine = MacroExecutionEngine(memory_manager)

# Execute simple macro
macro = {
    "name": "test",
    "actions": [
        {"type": "log", "message": "Hello"},
        {"type": "set_memory", "key": "test", "value": "done"}
    ]
}
execution = engine.execute_macro(macro)

# Execute with conditionals
macro = {
    "name": "alert",
    "actions": [{
        "type": "condition",
        "if": "{{errors}} > 10",
        "then": [{"type": "notify", "channel": "slack"}],
        "else": [{"type": "log", "message": "OK"}]
    }]
}
execution = engine.execute_macro(macro, context={"errors": 15})

# Create from template
macro = MacroTemplateLibrary.create_from_template(
    "scheduled_sync",
    {"source": "metrics", "destination": "power_automate", "schedule": "0 * * * *"}
)
execution = engine.execute_macro(macro)

# Dry run (validation)
execution = engine.execute_macro(macro, dry_run=True)

# View history
history = engine.get_execution_history(macro_name="test", limit=10)
```

### Audit Logging

```python
from workflows import AuditLogger
from datetime import datetime, timedelta

# Initialize
audit = AuditLogger()

# Log
audit.log("write", "memory", "key", user="admin", success=True)

# Query
all_logs = audit.query_logs(limit=100)
failed = audit.query_logs(success=False)
by_user = audit.query_logs(user="admin")
recent = audit.query_logs(since=datetime.now() - timedelta(hours=24))
by_type = audit.query_logs(entity_type="memory", operation="write")
```

### Integrated Workflow

```python
from workflows import EnhancedCXFlowWorkflow

# Initialize
workflow = EnhancedCXFlowWorkflow(enable_versioning=True)

# Query memory
results = workflow.query_memory(
    category="config",
    tags=["prod"],
    filters=[{"field": "metadata.priority", "op": "gt", "value": 5}]
)

# Search
results = workflow.search_memory("important")

# Execute macro
execution = workflow.execute_macro_by_name("daily_sync", context={})

# Create from template
macro = workflow.create_macro_from_template(
    "conditional_notification",
    {"condition_field": "errors", "threshold": 10, "channel": "slack"}
)

# Batch operations
keys = workflow.batch_set_memory([...], user="admin")

# Rollback
workflow.rollback_memory("key", version=3)

# History
history = workflow.get_memory_history("key")

# Export/Import
workflow.export_memory(Path("backup.json"), include_versions=True)
workflow.import_memory(Path("backup.json"), merge=True)

# Audit report
report = workflow.get_audit_report(entity_type="memory", limit=100)

# Macro history
history = workflow.get_macro_execution_history(macro_name="sync", limit=50)

# Sync to Power Automate (original functionality)
result = workflow.sync_all(include_metrics=True)
```

## Query Operators

- `EQ` - Equal to
- `NE` - Not equal to
- `GT` - Greater than
- `GTE` - Greater than or equal
- `LT` - Less than
- `LTE` - Less than or equal
- `IN` - In list
- `NIN` - Not in list
- `CONTAINS` - Contains substring
- `REGEX` - Regex match
- `EXISTS` - Field exists

## Aggregate Functions

- `COUNT` - Count entries
- `SUM` - Sum values
- `AVG` - Average
- `MIN` - Minimum
- `MAX` - Maximum
- `DISTINCT` - Unique values

## Transformations

- `uppercase` - Convert to uppercase
- `lowercase` - Convert to lowercase
- `reverse` - Reverse
- `sort` - Sort list
- `unique` - Unique values
- `count` - Count items

## Action Types

- `log` - Log message
- `set_memory` - Set memory entry
- `get_memory` - Get memory entry
- `collect` - Collect data
- `sync` - Sync to destination
- `execute` - Execute command
- `notify` - Send notification
- `api_call` - Make API call
- `condition` - If/else logic
- `loop` - Iterate over items
- `transform` - Transform data
- `delay` - Wait (seconds)

## Built-in Templates

1. **scheduled_sync** - Automated data sync
   - Parameters: source, destination, schedule

2. **conditional_notification** - Alert on condition
   - Parameters: condition_field, threshold, channel

3. **data_pipeline** - Multi-stage transformations
   - Parameters: input_key, output_key, transformations

4. **error_handler** - Retry with backoff
   - Parameters: action_type, max_retries, delay

## CLI Commands

### Memory

```bash
# Query
python -m workflows.cxflow_enhanced memory query --category config

# Search
python -m workflows.cxflow_enhanced memory search "term"

# Aggregate
python -m workflows.cxflow_enhanced memory aggregate field count

# History
python -m workflows.cxflow_enhanced memory history key

# Rollback
python -m workflows.cxflow_enhanced memory rollback key 2

# Export
python -m workflows.cxflow_enhanced memory export backup.json --include-versions

# Import
python -m workflows.cxflow_enhanced memory import backup.json --merge
```

### Macros

```bash
# Execute
python -m workflows.cxflow_enhanced macro execute macro_name

# Dry run
python -m workflows.cxflow_enhanced macro execute macro_name --dry-run

# With context
python -m workflows.cxflow_enhanced macro execute macro_name \
  --context '{"key": "value"}'

# Validate
python -m workflows.cxflow_enhanced macro validate macro.json

# From template
python -m workflows.cxflow_enhanced macro from-template template_name \
  --params '{"param": "value"}'

# List templates
python -m workflows.cxflow_enhanced macro templates

# History
python -m workflows.cxflow_enhanced macro history --macro name --limit 20
```

### Audit

```bash
# Query
python -m workflows.cxflow_enhanced audit query --operation write

# By entity
python -m workflows.cxflow_enhanced audit query --entity-type memory

# By user
python -m workflows.cxflow_enhanced audit query --user admin --limit 50
```

## Examples

Run comprehensive demos:
```bash
python workflows/examples/enhanced_usage.py
python workflows/examples/integration_test.py
```

## Documentation

- **Complete Guide**: `docs/CXFLOW_ENHANCED.md`
- **Summary**: `docs/ENHANCEMENT_SUMMARY.md`
- **Quick Start**: `workflows/examples/README.md`

## Convenience Functions

```python
from workflows import (
    query_memory,
    execute_macro,
    create_macro_from_template,
    search_memory,
    get_audit_report,
)

# Use without initializing workflow
results = query_memory(category="config", tags=["prod"])
execution = execute_macro("macro_name", context={})
macro = create_macro_from_template("template", {...})
results = search_memory("term")
report = get_audit_report(limit=100)
```

## Feature Detection

```python
from workflows import HAS_ENHANCED

if HAS_ENHANCED:
    print("Enhanced capabilities available")
    from workflows import EnhancedMemoryManager
```

## Backwards Compatibility

All original functionality preserved:
```python
from workflows import CXFlowSyncWorkflow, set_memory, get_memory

# Original workflow still works
workflow = CXFlowSyncWorkflow()
set_memory("key", "value")
value = get_memory("key")
workflow.sync_all()
```

## Performance Tips

1. Use category/tag filters (indexed)
2. Use batch operations for bulk ops
3. Limit query results with pagination
4. Use specific field searches vs full-text
5. Version history auto-pruned at 50 versions

## Security

### Encryption
```python
manager = EnhancedMemoryManager(
    enable_encryption=True,
    encryption_key=your_key
)
manager.set("secret", "value", metadata={"sensitive": True})
```

### Audit Trail
All operations automatically logged with timestamp, user, operation, success/failure.

## Troubleshooting

### Import Issues
Ensure correct path:
```bash
cd /path/to/cxflow
python -m workflows.examples.enhanced_usage
```

### Encryption Not Available
```bash
pip install cryptography
```

### Storage Issues
```python
from pathlib import Path
Path("./.cxflow/memory").mkdir(parents=True, exist_ok=True)
```

## Support

- Check documentation: `docs/CXFLOW_ENHANCED.md`
- Run examples: `workflows/examples/`
- Enable debug: `logging.basicConfig(level=logging.DEBUG)`
- Use dry-run for macros
- Review audit logs

---

**Version**: 2.0.0 | **Status**: Production Ready ✅
