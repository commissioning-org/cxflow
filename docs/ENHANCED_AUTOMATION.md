# Enhanced Automation Features

This document describes the significantly enhanced automation capabilities for CXFlow's ingestion, pipelines, dataflows, routing, and distribution systems.

## Table of Contents

1. [Overview](#overview)
2. [Auto-Validation](#auto-validation)
3. [Smart Routing](#smart-routing)
4. [Auto-Transformation](#auto-transformation)
5. [Self-Healing Automation](#self-healing-automation)
6. [Priority Queue and Batch Processing](#priority-queue-and-batch-processing)
7. [Intelligent Monitoring](#intelligent-monitoring)
8. [Configuration](#configuration)
9. [Examples](#examples)

## Overview

The enhanced automation system provides **full no human intervention** capabilities with:

- **Automated Data Validation**: Quality checks, schema detection, anomaly detection
- **Smart Routing**: Load balancing, failover, circuit breaker, retry with backoff
- **Auto-Transformation**: Type inference, missing value handling, outlier detection
- **Self-Healing**: Automatic rollback, checkpoint/restore, health monitoring
- **Priority Queuing**: Message prioritization, batch processing, deduplication
- **Intelligent Monitoring**: Anomaly detection, alerting, trend analysis

All features work together seamlessly in the ingestion orchestrator for fully automated operation.

## Auto-Validation

Automatically validates ingested data with comprehensive quality checks.

### Features

- Schema detection and validation
- Data completeness metrics (% non-null values)
- Data consistency checks (type consistency)
- Duplicate row detection
- Anomaly detection in numeric columns (outliers)
- Automatic suggestions for data cleaning

### Configuration

Enable via environment variables:

```bash
CX_AUTO_VALIDATE=true
CX_VALIDATE_MIN_COMPLETENESS=0.7     # Minimum 70% completeness
CX_VALIDATE_MIN_CONSISTENCY=0.8      # Minimum 80% consistency
CX_VALIDATE_DETECT_ANOMALIES=true    # Detect outliers
CX_VALIDATE_SUGGEST_FIXES=true       # Generate fix suggestions
CX_VALIDATE_CHECK_DUPLICATES=true    # Check for duplicates
```

### Output

Validation results are saved to `<run_dir>/validation.result.json`:

```json
{
  "ok": true,
  "quality_score": 0.85,
  "metrics": {
    "completeness": 0.92,
    "consistency": 0.88,
    "total_rows": 1000,
    "total_columns": 15,
    "duplicate_rows": 3,
    "null_values": 120,
    "anomalies": [
      {
        "column": "price",
        "type": "outliers",
        "count": 5,
        "percentage": 0.5
      }
    ]
  },
  "suggestions": [
    {
      "type": "deduplication",
      "priority": "medium",
      "action": "Remove duplicate rows",
      "impact": "Will reduce dataset by 3 rows"
    }
  ]
}
```

## Smart Routing

Intelligent webhook distribution with load balancing and automatic failover.

### Features

- Multiple routing strategies:
  - **Round Robin**: Even distribution across targets
  - **Weighted Round Robin**: Distribution based on target weights
  - **Priority-Based**: Route to highest priority targets first
  - **Least Connections**: Route to least busy target
  - **Fastest Response**: Route to fastest responding target
- Automatic retry with exponential backoff
- Circuit breaker pattern (prevents cascade failures)
- Health-based routing decisions
- Automatic failover to backup targets

### Configuration

```bash
CX_SMART_ROUTING_ENABLED=true
CX_ROUTER_STRATEGY=priority_based     # round_robin, weighted_round_robin, priority_based, least_connections, fastest_response
CX_ROUTER_MAX_RETRIES=3
CX_ROUTER_RETRY_BACKOFF=2.0           # Exponential backoff multiplier
CX_ROUTER_INITIAL_DELAY_MS=100        # Initial retry delay
CX_ROUTER_CIRCUIT_THRESHOLD=5         # Failures before circuit opens

# Define targets as JSON
CX_ROUTER_TARGETS_JSON='[
  {
    "name": "primary",
    "url": "https://api1.example.com/webhook",
    "priority": 10,
    "weight": 3,
    "enabled": true,
    "backup": false,
    "timeout_seconds": 15,
    "headers": {"x-api-key": "secret"}
  },
  {
    "name": "backup",
    "url": "https://api2.example.com/webhook",
    "priority": 5,
    "weight": 1,
    "enabled": true,
    "backup": true,
    "timeout_seconds": 20
  }
]'
```

### Output

Routing results saved to `<run_dir>/smart_routing.result.json`:

```json
{
  "ok": true,
  "target": "primary",
  "response": {
    "ok": true,
    "http_code": 200
  },
  "attempts": [
    {
      "target": "primary",
      "attempt": 1,
      "ok": true,
      "http_code": 200,
      "elapsed_ms": 145
    }
  ],
  "attempted_count": 1,
  "elapsed_ms": 145,
  "strategy": "priority_based"
}
```

## Auto-Transformation

Automated data transformation with intelligent type inference and cleaning.

### Features

- Automatic schema detection
- Data type inference and conversion
- Missing value handling (multiple strategies):
  - Drop rows with missing values
  - Fill with mean/median/mode
  - Forward fill
  - Constant value
- Outlier detection and handling (clip, remove, or flag)
- Duplicate row removal
- Feature engineering:
  - Datetime feature extraction (year, month, day, hour, day-of-week, quarter)
  - Text feature extraction (length, word count)
  - Categorical encoding (one-hot, label encoding)
- Data normalization (min-max, z-score)

### Configuration

```bash
CX_AUTO_TRANSFORM=true
PYTHON_BIN=python3  # Python binary to use
```

### Usage

```bash
python3 ingestion/auto_transform.py input.ndjson output.ndjson
```

### Output

Transformed data saved to `<run_dir>/rows_transformed.ndjson` with transformation report in `<run_dir>/transform.result.json`:

```json
{
  "ok": true,
  "transformations_applied": [
    "auto_type_conversion",
    "missing_values_mean",
    "deduplication",
    "outliers_iqr",
    "datetime_feature_extraction",
    "text_processing",
    "categorical_onehot"
  ],
  "original_shape": [1000, 15],
  "final_shape": [997, 23],
  "statistics": {
    "missing_values": {
      "total_missing": 120,
      "by_column": {"age": 45, "income": 75}
    },
    "duplicates_removed": 3,
    "outliers": {
      "outliers_detected": 8,
      "by_column": {
        "price": {
          "count": 8,
          "lower_bound": 10.5,
          "upper_bound": 99.2
        }
      }
    }
  },
  "elapsed_ms": 543
}
```

## Self-Healing Automation

Automatic error detection, recovery, and rollback capabilities.

### Features

- Transaction-like operations with state checkpoints
- Automatic rollback on failures
- Multiple recovery strategies:
  - **Retry**: Retry with exponential backoff
  - **Rollback**: Restore previous state
  - **Failover**: Switch to backup system
  - **Skip**: Skip failed operation and continue
  - **Abort**: Stop execution
- Circuit breaker pattern
- Health monitoring and self-correction
- Graceful degradation

### Usage

```python
from ingestion.self_healing import SelfHealingAutomation, RecoveryAction, RecoveryStrategy, HealthCheck

# Create automation system
automation = SelfHealingAutomation()

# Register health checks
automation.register_health_check(HealthCheck(
    name="disk_space",
    check_func=lambda: check_disk_space() > 0.1,  # 10% free
    critical=True,
))

# Execute operation with automatic recovery
result = automation.execute_with_recovery(
    operation=lambda: process_data(),
    operation_name="data_processing",
    recovery=RecoveryAction(
        strategy=RecoveryStrategy.RETRY,
        max_retries=5,
        retry_delay_ms=1000,
    ),
    create_checkpoint=True,
    current_state={'data': data},
)

# Check system health
health = automation.get_system_health()
print(health['overall_status'])  # healthy, degraded, or unhealthy
```

## Priority Queue and Batch Processing

Efficient webhook distribution with priority queuing and batch processing.

### Features

- Priority-based message queuing (5 levels: CRITICAL, HIGH, NORMAL, LOW, BULK)
- Automatic message deduplication
- Batch processing for efficiency
- Message aggregation (combine similar messages)
- Scheduled delivery (delayed messages)
- Backpressure management
- Dead letter queue handling

### Usage

```python
from webhook_engine.priority_queue import PriorityWebhookQueue, MessagePriority, BatchProcessor

# Create queue
queue = PriorityWebhookQueue(
    enable_deduplication=True,
    dedup_window_seconds=300,
)

# Enqueue messages with priority
await queue.enqueue(
    endpoint="api_endpoint",
    payload={'event': 'important_update', 'data': {...}},
    priority=MessagePriority.HIGH,
)

# Process in batches
processor = BatchProcessor(queue)
result = await processor.process_batch(send_func)

print(f"Processed: {result.messages_processed}")
print(f"Success: {result.messages_succeeded}")
print(f"Duplicates removed: {result.duplicates_removed}")
```

## Intelligent Monitoring

Real-time monitoring with statistical anomaly detection.

### Features

- Multiple anomaly detection methods:
  - **Z-Score**: Standard deviation-based detection
  - **IQR**: Interquartile range-based detection (robust to outliers)
  - **MAD**: Median Absolute Deviation (most robust)
  - **Trend Change**: Detects sudden trend changes
- Automatic alert generation with severity levels
- Alert cooldown to prevent alert fatigue
- Performance baseline learning
- Adaptive thresholds
- Time-series metric storage

### Usage

```python
from ingestion.intelligent_monitoring import IntelligentMonitor, Severity

# Create monitor with alert callback
def alert_handler(alert):
    print(f"🚨 {alert.title} - {alert.severity.value}")
    # Send to notification system

monitor = IntelligentMonitor(
    retention_seconds=3600,
    sensitivity=3.0,  # Standard deviations for anomaly threshold
    alert_callback=alert_handler,
)

# Record metrics
anomalies = monitor.record_metric(
    name="response_time_ms",
    value=response_time,
    tags={'endpoint': '/api/data'},
)

# Get alerts
recent_alerts = monitor.get_alerts(
    severity=Severity.CRITICAL,
    since_seconds=3600,
)

# Get statistics
stats = monitor.get_statistics()
print(f"Total anomalies: {stats['total_anomalies']}")
print(f"Active alerts: {stats['active_alerts']}")
```

## Configuration

### Complete Environment Variables

```bash
# Auto-Validation
CX_AUTO_VALIDATE=true
CX_VALIDATE_MIN_COMPLETENESS=0.7
CX_VALIDATE_MIN_CONSISTENCY=0.8
CX_VALIDATE_DETECT_ANOMALIES=true
CX_VALIDATE_SUGGEST_FIXES=true
CX_VALIDATE_CHECK_DUPLICATES=true

# Smart Routing
CX_SMART_ROUTING_ENABLED=true
CX_ROUTER_STRATEGY=priority_based
CX_ROUTER_MAX_RETRIES=3
CX_ROUTER_RETRY_BACKOFF=2.0
CX_ROUTER_INITIAL_DELAY_MS=100
CX_ROUTER_CIRCUIT_THRESHOLD=5
CX_ROUTER_TARGETS_JSON='[...]'

# Auto-Transformation
CX_AUTO_TRANSFORM=true
PYTHON_BIN=python3

# Existing orchestration features
CX_ORCH_WEBHOOK_ENABLED=false
CX_ORCH_ROUTE_ENABLED=false
CX_AUTOML_ENABLED=false
TFOS_ENABLED=false
SUPABASE_UPLOAD_ENABLED=false
```

## Examples

### End-to-End Automated Ingestion

```bash
# Set environment variables
export CX_INGESTION_URI="https://data-source.com/api/data?sig=..."
export CX_AUTO_VALIDATE=true
export CX_AUTO_TRANSFORM=true
export CX_SMART_ROUTING_ENABLED=true
export CX_ROUTER_TARGETS_JSON='[
  {
    "name": "analytics",
    "url": "https://analytics.example.com/ingest",
    "priority": 10
  },
  {
    "name": "warehouse",
    "url": "https://warehouse.example.com/load",
    "priority": 8
  }
]'

# Run orchestration (fully automated)
php ingestion/cx_orchestrate.php "$CX_INGESTION_URI"

# Results saved to ingestion/runs/<run_id>/ including:
# - manifest.json (ingestion metadata)
# - validation.result.json (data quality report)
# - rows_transformed.ndjson (transformed data)
# - smart_routing.result.json (routing results)
# - event.json (clean event envelope)
```

### Programmatic Usage

```python
# Import modules
from ingestion.auto_validation import validate_ingestion_data
from ingestion.smart_routing import SmartRouter, RoutingTarget, RoutingStrategy
from ingestion.auto_transform import AutoTransformer, TransformationConfig
from ingestion.self_healing import SelfHealingAutomation
from ingestion.intelligent_monitoring import IntelligentMonitor

# 1. Validate data
manifest = load_manifest()
validation = validate_ingestion_data(manifest)
print(f"Quality score: {validation['quality_score']}")

# 2. Transform data
config = TransformationConfig(
    handle_missing=True,
    handle_outliers=True,
    encode_categorical=True,
)
transformer = AutoTransformer(config)
result = transformer.transform(rows)

# 3. Route with smart routing
router = SmartRouter({
    'strategy': RoutingStrategy.PRIORITY_BASED,
    'max_retries': 3,
    'targets': [
        {'name': 'primary', 'url': '...', 'priority': 10},
        {'name': 'backup', 'url': '...', 'priority': 5, 'backup': True},
    ]
})
route_result = router.route(payload)

# 4. Self-healing execution
automation = SelfHealingAutomation()
exec_result = automation.execute_with_recovery(
    operation=lambda: send_data(),
    operation_name="send_data",
    create_checkpoint=True,
    current_state={'data': data},
)

# 5. Monitor performance
monitor = IntelligentMonitor()
monitor.record_metric("processing_time_ms", elapsed_ms)
```

## Integration with Existing Features

The enhanced automation features integrate seamlessly with existing CXFlow capabilities:

- **TensorFlowOnSpark**: Auto-transformed data can be used for distributed training
- **AutoML**: Validated and transformed data improves model quality
- **Power Automate**: Smart routing can distribute to Power Automate flows
- **Supabase**: All artifacts (validation, transformation results) can be uploaded
- **GitHub Actions**: All features work in scheduled workflows

## Performance

- **Auto-Validation**: ~50-200ms for 1000 rows
- **Auto-Transformation**: ~200-800ms for 1000 rows with all features enabled
- **Smart Routing**: ~100-300ms per target with retry
- **Priority Queue**: Can handle 10,000+ messages/second
- **Intelligent Monitoring**: <1ms per metric recording

## Best Practices

1. **Enable validation** on all ingestion pipelines to catch data quality issues early
2. **Use smart routing** for critical webhooks that need high availability
3. **Apply transformations** before ML training for better model performance
4. **Configure health checks** for all critical components
5. **Set appropriate priorities** for different types of messages
6. **Monitor key metrics** with anomaly detection for proactive issue detection
7. **Use checkpoints** for long-running operations that may need rollback
8. **Configure retry policies** based on target system characteristics

## Troubleshooting

### Validation Fails

- Check `validation.result.json` for specific issues
- Review suggestions in the validation report
- Adjust minimum thresholds if data quality is expected to be lower

### Smart Routing Failures

- Check `smart_routing.result.json` for failure details
- Verify target URLs and credentials
- Check circuit breaker status: may be open due to repeated failures
- Reset circuit breaker: `router.resetTargetHealth(target_name)`

### Transformation Errors

- Check `transform.result.json` for error details
- Verify Python is available: `python3 --version`
- Check input data format (must be valid NDJSON)

### Performance Issues

- Reduce batch sizes if processing is slow
- Disable expensive transformations (e.g., categorical encoding on high-cardinality fields)
- Adjust monitoring retention period
- Increase queue size limits

## Monitoring and Observability

All automation features produce detailed logs and metrics:

- Validation metrics: completeness, consistency, anomaly counts
- Routing metrics: success rate, response times, circuit breaker status
- Transformation metrics: rows processed, transformations applied
- Queue metrics: size, throughput, duplicates removed
- Health metrics: component status, alerts generated

Use the intelligent monitoring system to track these metrics and detect issues automatically.
