# Enhanced Macros Quick Reference

Quick reference guide for all enhanced macros in `.cxflow/macros`.

## 🎯 All Macros at a Glance

| Macro | Version | Trigger | Features | Complexity |
|-------|---------|---------|----------|------------|
| batch_processing | 1.0.0 | schedule | Dynamic sizing, parallel execution, error handling | 18 actions |
| build_docs | 2.0.0 | webhook | Conditionals, notifications, transformations | 13 actions |
| conditional_alerts | 1.0.0 | event | Priority routing, multi-channel, escalation | 14 actions |
| daily_sync | 2.0.0 | schedule | Retry logic, validation, metrics | 17 actions |
| data_quality_check | 1.0.0 | event | Multi-dimension checks, auto-fix, anomaly detection | 18 actions |
| etl_pipeline | 1.0.0 | manual | 3-stage ETL, validation, rollback | 25 actions |
| intelligent_monitoring | 1.0.0 | schedule | 4 metrics, anomaly detection, auto-remediation | 20 actions |
| ml_pipeline_run | 2.0.0 | event | Data validation, multi-stage processing | 17 actions |
| refresh_superset | 2.0.0 | schedule | Health checks, retry with backoff | 15 actions |
| self_healing_workflow | 1.0.0 | event | 5-attempt recovery, rollback, state mgmt | 17 actions |

**Total**: 10 macros, 100% enhanced, avg 17.4 actions per macro

## 🔧 Quick Start

### Load and Execute a Macro

```python
from workflows.cxflow_enhanced import (
    MacroExecutionEngine,
    EnhancedMemoryManager,
)
import json
from pathlib import Path

# Initialize
memory = EnhancedMemoryManager()
engine = MacroExecutionEngine(memory)

# Load macro
macro = json.loads(Path(".cxflow/macros/daily_sync.json").read_text())

# Execute
execution = engine.execute_macro(macro, context={
    "timestamp": "2026-01-02T00:00:00Z",
})

print(f"Status: {execution.status.value}")
```

### Dry Run (Validation)

```python
execution = engine.execute_macro(macro, dry_run=True)
# Returns what would execute without actually doing it
```

## 📚 Macro Categories

### Data Processing
- **etl_pipeline**: Multi-stage Extract-Transform-Load
- **batch_processing**: Intelligent batch processing
- **data_quality_check**: Quality validation with auto-fix

### Monitoring & Healing
- **intelligent_monitoring**: Anomaly detection + auto-remediation
- **self_healing_workflow**: Automatic recovery with rollback

### Sync & Integration
- **daily_sync**: Full sync with retry logic
- **refresh_superset**: Superset dataset refresh

### Build & Deploy
- **build_docs**: Documentation build with notifications
- **ml_pipeline_run**: ML pipeline execution

### Alerting
- **conditional_alerts**: Priority-based alert routing

## 🎨 Feature Matrix

| Feature | Macros Using |
|---------|--------------|
| Conditionals | 10/10 (100%) |
| Loops | 8/10 (80%) |
| Transformations | 7/10 (70%) |
| Error Handling | 4/10 (40%) |
| Validation | 4/10 (40%) |
| Nested Conditionals | 3/10 (30%) |
| Retry Logic | 2/10 (20%) |

## 🔍 Common Patterns

### Pattern 1: Retry Loop
```json
{
  "type": "loop",
  "items": [1, 2, 3],
  "as": "attempt",
  "actions": [
    {"type": "execute", "command": "..."},
    {"type": "delay", "seconds": 5}
  ]
}
```
**Used in**: daily_sync, refresh_superset, self_healing_workflow

### Pattern 2: Conditional with Else
```json
{
  "type": "condition",
  "if": "True",
  "then": [
    {"type": "log", "message": "Success"}
  ],
  "else": [
    {"type": "log", "message": "Failed"}
  ]
}
```
**Used in**: All macros

### Pattern 3: Variable Resolution
```json
{
  "type": "log",
  "message": "Processing {{context.item}} at {{context.timestamp}}"
}
```
**Used in**: All macros

### Pattern 4: Memory Storage
```json
{
  "type": "set_memory",
  "key": "last_run_{{context.service}}",
  "value": "{{context.timestamp}}"
}
```
**Used in**: build_docs, daily_sync, ml_pipeline_run, refresh_superset

### Pattern 5: Nested Loops
```json
{
  "type": "loop",
  "items": ["batch_1", "batch_2"],
  "as": "batch",
  "actions": [
    {
      "type": "loop",
      "items": ["stage_1", "stage_2"],
      "as": "stage",
      "actions": [...]
    }
  ]
}
```
**Used in**: batch_processing, etl_pipeline

## 🚀 Testing

### Run All Tests
```bash
cd /home/runner/work/cxflow/cxflow
PYTHONPATH=/home/runner/work/cxflow/cxflow python3 workflows/test_enhanced_macros.py
```

### Run Demonstration
```bash
PYTHONPATH=/home/runner/work/cxflow/cxflow python3 workflows/demo_enhanced_macros.py
```

## 📊 Statistics

- **Total Lines**: ~40,000 (all macros combined)
- **Total Actions**: 83 top-level actions
- **Total Nested Actions**: 91 nested actions
- **Average Complexity**: 17.4 actions per macro
- **Enhancement Rate**: 100%

## 🔗 Related Documentation

- [Enhanced Macros Full Guide](ENHANCED_MACROS.md) - Complete documentation
- [CXFlow Enhanced](CXFLOW_ENHANCED.md) - Framework documentation
- [Enhanced Automation](ENHANCED_AUTOMATION.md) - Automation features

## 💡 Tips

1. **Start with dry-run**: Always test with `dry_run=True` first
2. **Use templates**: Create new macros from templates in `MacroTemplateLibrary`
3. **Validate first**: Use `ValidationSchema.validate_macro()` before execution
4. **Monitor execution**: Check `execution.status` and `execution.errors`
5. **Use memory**: Store state for tracking and debugging
6. **Leverage conditionals**: Add error handling with if/then/else
7. **Implement retry**: Use loops for retry logic
8. **Track metrics**: Use transformations to count and analyze

## 📞 Support

For issues or questions:
- Check examples in `workflows/examples/`
- Run test suite: `workflows/test_enhanced_macros.py`
- View demo: `workflows/demo_enhanced_macros.py`
- Read full docs: `docs/ENHANCED_MACROS.md`
