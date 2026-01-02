# Enhanced Macro Capabilities

This document describes the significantly enhanced macro capabilities implemented in `.cxflow/macros`.

## Overview

All macros in `.cxflow/macros` have been significantly enhanced with advanced features including:
- **Conditional logic** (if/then/else)
- **Loops and iterations**
- **Data transformations**
- **Error handling and retry logic**
- **Memory management**
- **Multi-stage workflows**
- **Nested operations**
- **Variable resolution with `{{variable}}` syntax**
- **Self-healing capabilities**

## Enhanced Macros

### 1. build_docs.json (v2.0.0)
**Purpose**: Build documentation on commit with error handling and validation

**Enhanced Features**:
- Conditional execution based on build success/failure
- Memory storage of build status and timestamps
- Multi-channel notifications (success and failure)
- Variable resolution for commit information
- Data transformation for commit SHA formatting

**Key Actions**:
- Health check before build
- Conditional success/failure handling
- Status persistence to memory
- Team notifications with context

### 2. daily_sync.json (v2.0.0)
**Purpose**: Daily sync of all data to Power Automate with validation and retry logic

**Enhanced Features**:
- Retry logic with configurable attempts (3 retries)
- Data validation before sync
- Metrics collection and transformation
- Conditional execution based on sync success
- Progress tracking in memory

**Key Actions**:
- Multi-source data collection (memory, macros, metadata)
- Item counting and logging
- Retry loop with exponential backoff
- Success/failure state management
- Sync completion notifications

### 3. ml_pipeline_run.json (v2.0.0)
**Purpose**: Run ML pipeline on new data with validation and transformation

**Enhanced Features**:
- Input data validation
- Multi-stage processing (preprocess, train, evaluate)
- Loop-based stage execution
- Result tracking in memory
- Conditional notifications based on validation

**Key Actions**:
- Data path validation
- Stage-by-stage execution with logging
- Status updates to memory
- Results sync to Power Automate
- Completion notifications

### 4. refresh_superset.json (v2.0.0)
**Purpose**: Refresh Superset datasets with health checks and retry logic

**Enhanced Features**:
- Health check before refresh
- Retry loop with configurable attempts
- Service availability detection
- Dataset counting and processing
- Conditional execution based on service health

**Key Actions**:
- Superset service health check
- Conditional refresh based on health
- Multiple retry attempts with delays
- Status tracking in memory
- Multi-scenario notifications

### 5. data_quality_check.json (v1.0.0)
**Purpose**: Comprehensive data quality validation with anomaly detection and auto-fix

**Enhanced Features**:
- Multi-dimension quality checks (completeness, accuracy, consistency, validity)
- Loop-based quality validation
- Automatic fixing of quality issues
- Quality score calculation
- Conditional auto-fix based on thresholds

**Key Actions**:
- Four-dimension quality check loop
- Check status tracking in memory
- Conditional auto-fix execution
- Quality score reporting
- Alert notifications for quality issues

### 6. etl_pipeline.json (v1.0.0)
**Purpose**: Advanced ETL pipeline with multi-stage transformation and validation

**Enhanced Features**:
- Three-stage ETL (Extract, Transform, Load)
- Multi-source extraction loop
- Multiple transformation steps
- Validation with rollback capability
- Parallel loading to multiple destinations

**Key Actions**:
- Extract from database, API, and files
- Transform with clean, normalize, enrich, aggregate
- Load to warehouse, data lake, and analytics
- Validation between stages
- Rollback on failure

### 7. intelligent_monitoring.json (v1.0.0)
**Purpose**: Intelligent system monitoring with anomaly detection and adaptive thresholds

**Enhanced Features**:
- Multi-metric monitoring (CPU, memory, disk, network)
- Loop-based metric collection
- Anomaly detection with nested conditionals
- Severity-based alerting
- Automatic remediation actions

**Key Actions**:
- Metric collection loop
- Health status evaluation
- Nested conditional alerts by severity
- Auto-remediation loop (scale_up, restart_service, clear_cache)
- Multi-channel notifications

### 8. self_healing_workflow.json (v1.0.0)
**Purpose**: Self-healing workflow with automatic error recovery and rollback

**Enhanced Features**:
- Service health monitoring
- Multi-attempt recovery loop (5 attempts)
- State management for rollback
- Nested conditionals for recovery success/failure
- Automatic service restart

**Key Actions**:
- Health check
- Recovery attempt loop with delays
- State capture for rollback
- Conditional success/failure handling
- Rollback on complete failure
- Detailed notifications at each stage

### 9. conditional_alerts.json (v1.0.0)
**Purpose**: Intelligent alert system with priority-based routing and escalation

**Enhanced Features**:
- Priority-based routing (high, medium, low)
- Nested conditionals for priority levels
- Multi-channel notifications based on priority
- Escalation for critical alerts
- Loop-based alert distribution

**Key Actions**:
- Priority detection and transformation
- High priority: 4 channels (teams, slack, email, SMS)
- Medium priority: 2 channels (teams, slack)
- Low priority: 1 channel (teams)
- On-call escalation for critical alerts

### 10. batch_processing.json (v1.0.0)
**Purpose**: Intelligent batch processing with dynamic sizing and parallel execution

**Enhanced Features**:
- Dynamic batch sizing based on item count
- Nested loops for batch and stage processing
- Per-batch validation
- Error handling with failed batch tracking
- Multi-stage processing per batch

**Key Actions**:
- Item counting and validation
- Batch creation and processing loop
- Stage execution per batch (validate, transform, load)
- Per-batch success/failure tracking
- Batch completion notifications

## Feature Statistics

- **Total Macros**: 10
- **All Enhanced**: 100%
- **Average Actions per Macro**: 8.3
- **Average Nested Actions**: 9.1
- **Average Total Complexity**: 17.4

### Feature Usage Across All Macros:
- **Conditionals**: 10 macros (100%)
- **Loops**: 8 macros (80%)
- **Transformations**: 7 macros (70%)
- **Error Handling**: 4 macros (40%)
- **Validation**: 4 macros (40%)
- **Nested Conditionals**: 3 macros (30%)
- **Retry Logic**: 2 macros (20%)
- **Multi-stage**: 2 macros (20%)

## Using Enhanced Macros

### Loading and Validating

```python
from workflows.cxflow_enhanced import ValidationSchema
import json

# Load a macro
macro = json.loads(Path(".cxflow/macros/build_docs.json").read_text())

# Validate
is_valid, errors = ValidationSchema.validate_macro(macro)
if is_valid:
    print("✅ Macro is valid")
```

### Executing Macros

```python
from workflows.cxflow_enhanced import (
    MacroExecutionEngine,
    EnhancedMemoryManager,
)

# Initialize
memory = EnhancedMemoryManager()
engine = MacroExecutionEngine(memory)

# Load macro
macro = json.loads(Path(".cxflow/macros/daily_sync.json").read_text())

# Execute with context
execution = engine.execute_macro(
    macro,
    context={
        "timestamp": datetime.now().isoformat(),
        "user": "system",
    }
)

# Check results
print(f"Status: {execution.status.value}")
print(f"Duration: {execution.duration_ms}ms")
print(f"Steps: {execution.steps_completed}/{execution.steps_total}")
```

### Dry Run (Validation)

```python
# Execute in dry-run mode to validate without actually running
execution = engine.execute_macro(macro, dry_run=True)
print(f"Would execute: {execution.results['dry_run']}")
```

### Using Integration Layer

```python
from workflows.enhanced_integration import EnhancedCXFlowWorkflow

# Initialize enhanced workflow
workflow = EnhancedCXFlowWorkflow()

# Execute a macro by name
execution = workflow.execute_macro_by_name(
    "daily_sync",
    context={"timestamp": datetime.now().isoformat()},
    dry_run=False
)

# View execution history
history = workflow.get_macro_execution_history(macro_name="daily_sync")
```

## Testing

Run the comprehensive test suite:

```bash
cd /home/runner/work/cxflow/cxflow
PYTHONPATH=/home/runner/work/cxflow/cxflow python3 workflows/test_enhanced_macros.py
```

The test suite validates:
1. ✅ JSON loading and syntax
2. ✅ Schema validation
3. ✅ Execution (dry-run)
4. ✅ Enhanced features presence
5. ✅ Complexity analysis

## Advanced Patterns

### 1. Nested Conditionals
```json
{
  "type": "condition",
  "if": "high_priority",
  "then": [
    {
      "type": "condition",
      "if": "critical_severity",
      "then": [{"type": "escalate"}],
      "else": [{"type": "notify"}]
    }
  ]
}
```

### 2. Multi-Stage Loops
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
      "actions": [{"type": "process"}]
    }
  ]
}
```

### 3. Variable Resolution
```json
{
  "type": "log",
  "message": "Processing {{context.item}} at {{context.timestamp}}"
}
```

### 4. Memory Management
```json
{
  "type": "set_memory",
  "key": "last_run_{{context.service}}",
  "value": "{{context.timestamp}}"
}
```

### 5. Transformations
```json
{
  "type": "transform",
  "input": "{{context.data}}",
  "operation": "count",
  "store_as": "item_count"
}
```

## Benefits

1. **Reliability**: Retry logic and error handling ensure robust execution
2. **Observability**: Comprehensive logging and state tracking
3. **Flexibility**: Variable resolution enables dynamic behavior
4. **Scalability**: Batch processing and parallel execution
5. **Maintainability**: Clear structure and validation
6. **Intelligence**: Self-healing and auto-remediation
7. **Audit Trail**: All actions logged to memory and audit system

## Integration with Power Automate

All enhanced macros are designed to work seamlessly with Power Automate sync:

1. Data collection from multiple sources
2. Transformation and validation
3. Sync to Power Automate webhook
4. Result tracking and notifications

## Next Steps

To create your own enhanced macros:

1. Use existing macros as templates
2. Follow the validation schema
3. Test with dry-run first
4. Leverage conditionals, loops, and transformations
5. Implement error handling and retry logic
6. Add comprehensive logging
7. Store state in memory for tracking

## See Also

- `docs/CXFLOW_ENHANCED.md` - Complete enhanced framework documentation
- `workflows/examples/enhanced_usage.py` - Comprehensive usage examples
- `workflows/cxflow_enhanced.py` - Core enhanced framework
- `workflows/enhanced_integration.py` - Integration layer
