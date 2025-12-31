# TensorFlowOnSpark Orchestration Guide

This document describes the comprehensive TensorFlowOnSpark (TFoS) integration with the CX ingestion and orchestration pipeline.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CX Orchestration Pipeline                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────────┐     ┌─────────────────┐     ┌────────────────────┐     │
│  │ php_cx_request │ ──▶ │ cx_orchestrate  │ ──▶ │ Supabase Upload    │     │
│  │   (Ingest)     │     │   (Workflow)    │     │                    │     │
│  └────────────────┘     └────────┬────────┘     └────────────────────┘     │
│                                  │                                          │
│                                  ▼                                          │
│                    ┌─────────────┴─────────────┐                           │
│                    ▼                           ▼                            │
│  ┌─────────────────────────┐   ┌─────────────────────────────┐             │
│  │   TFoS Integration      │   │    AutoML Service           │             │
│  │   (tfos_integration.php)│   │    (ml/app/main.py)         │             │
│  └───────────┬─────────────┘   └──────────────┬──────────────┘             │
│              │                                │                             │
│              ▼                                ▼                             │
│  ┌─────────────────────────┐   ┌─────────────────────────────┐             │
│  │   Spark Cluster         │   │    Local Training           │             │
│  │   (spark_cluster.php)   │   │    (scikit-learn/XGBoost)   │             │
│  └───────────┬─────────────┘   └─────────────────────────────┘             │
│              │                                                              │
│              ▼                                                              │
│  ┌─────────────────────────┐                                               │
│  │   TFoS Training Script  │                                               │
│  │   (tfos_training.py)    │                                               │
│  └───────────┬─────────────┘                                               │
│              │                                                              │
│              ▼                                                              │
│  ┌─────────────────────────────────────────────────┐                       │
│  │           TensorFlow Workers on Spark            │                       │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐         │                       │
│  │  │Worker 0 │  │Worker 1 │  │Worker N │   ...   │                       │
│  │  │ (chief) │  │         │  │         │         │                       │
│  │  └─────────┘  └─────────┘  └─────────┘         │                       │
│  └─────────────────────────────────────────────────┘                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. PHP Components

#### `tfos_integration.php`
Core TFoS integration module providing:
- `tfos_get_config()` - Configuration from environment variables
- `tfos_create_job_spec()` - Create job specifications
- `tfos_build_spark_submit()` - Build spark-submit command
- `tfos_submit_job()` - Synchronous job submission
- `tfos_submit_job_async()` - Asynchronous submission via AutoML API
- `tfos_prepare_data()` - Data preparation for training
- `orch_run_tfos_training()` - Orchestration integration function

#### `spark_cluster.php`
Spark cluster lifecycle management:
- `spark_start_master()` - Start Spark master node
- `spark_start_workers()` - Start worker nodes
- `spark_stop_cluster()` - Stop all cluster components
- `spark_health_check()` - Check cluster health
- `spark_submit()` - Generic spark-submit wrapper
- `spark_wait_for_cluster()` - Wait for cluster readiness

#### `ml_pipeline_config.php`
ML pipeline stage configuration:
- Pipeline stages: ingestion → validation → profiling → training → evaluation → export → notification
- `MLPipelineContext` class for pipeline state
- Configurable stage runners

### 2. Python Components

#### `tfos_training_script.py`
TensorFlowOnSpark training script:
- TFCluster integration via `main_fun(args, ctx)`
- Standalone training mode for non-Spark execution
- NDJSON/CSV data loading
- Automatic problem type detection (classification vs regression)
- Keras model building with MultiWorkerMirroredStrategy
- Model export in SavedModel format

#### `ml/app/main.py` (AutoML Service)
FastAPI service with TFoS endpoints:
- `POST /tfos/submit` - Submit TFoS training job
- `GET /tfos/status/{job_id}` - Check job status
- `GET /tfos/jobs` - List all TFoS jobs
- `DELETE /tfos/jobs/{job_id}` - Delete job and artifacts
- `GET /tfos/health` - Check Spark/TFoS availability

## Configuration

### Environment Variables

```bash
# TFoS Configuration
TFOS_ENABLED=true
TFOS_SPARK_MASTER=spark://master:7077  # or yarn, k8s://...
TFOS_CLUSTER_SIZE=4
TFOS_EXECUTOR_MEMORY=4g
TFOS_NUM_PS=0
TFOS_EPOCHS=10
TFOS_BATCH_SIZE=64
TFOS_LEARNING_RATE=0.001
TFOS_INPUT_MODE=SPARK  # or TENSORFLOW
TFOS_TENSORBOARD=true
TFOS_TRAINING_SCRIPT=/app/tfos_training_script.py

# Spark Configuration
SPARK_HOME=/opt/spark
SPARK_MASTER_HOST=localhost
SPARK_MASTER_PORT=7077
SPARK_WEBUI_PORT=8080
SPARK_WORKER_CORES=4
SPARK_WORKER_MEMORY=8g
SPARK_CLUSTER_MODE=standalone  # or yarn, kubernetes

# AutoML Service
AUTOML_URL=http://localhost:8000
MODELS_DIR=/models
```

## Usage Examples

### 1. Full Pipeline via cx_orchestrate.php

```php
<?php
require_once 'cx_orchestrate.php';

// Run full orchestration with TFoS training
$result = orch_dispatch(
    src: '/data/raw_data.ndjson',
    dst: '/data/processed',
    labelCol: 'target',
    tfos_enabled: true
);

echo json_encode($result, JSON_PRETTY_PRINT);
```

### 2. Direct TFoS Job Submission (PHP)

```php
<?php
require_once 'tfos_integration.php';

// Create job specification
$jobSpec = tfos_create_job_spec(
    dataPath: '/data/training_data.ndjson',
    modelDir: '/models/my_model',
    target: 'label',
    options: [
        'epochs' => 20,
        'batch_size' => 128,
        'cluster_size' => 4
    ]
);

// Submit synchronously
$result = tfos_submit_job($jobSpec);

if ($result['success']) {
    echo "Model saved to: " . $result['model_dir'];
} else {
    echo "Error: " . $result['error'];
}
```

### 3. AutoML Service API

```bash
# Submit TFoS training job
curl -X POST http://localhost:8000/tfos/submit \
  -H "Content-Type: application/json" \
  -d '{
    "data_path": "/data/training.ndjson",
    "target_column": "label",
    "spark_master": "spark://master:7077",
    "cluster_size": 4,
    "epochs": 10,
    "batch_size": 64,
    "async_mode": true
  }'

# Check job status
curl http://localhost:8000/tfos/status/{job_id}

# List all jobs
curl http://localhost:8000/tfos/jobs

# Check TFoS health
curl http://localhost:8000/tfos/health
```

### 4. Spark Cluster Management

```php
<?php
require_once 'spark_cluster.php';

// Start cluster
$master = spark_start_master();
spark_start_workers(4);

// Wait for cluster
if (spark_wait_for_cluster(timeout: 60)) {
    echo "Cluster ready!";
    
    // Check health
    $health = spark_health_check();
    print_r($health);
}

// Stop cluster
spark_stop_cluster();
```

## TensorFlowOnSpark Concepts

### InputMode

- **SPARK**: Spark feeds data to TensorFlow workers via RDD. Best for large datasets.
- **TENSORFLOW**: Each TF worker loads data independently. Better for datasets already in TFRecords.

### Cluster Configuration

```
┌─────────────────────────────────────────────────────────────────┐
│                    Spark Cluster                                │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Spark Master                          │  │
│  │                    (7077, 8080)                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│           ┌──────────────────┼──────────────────┐              │
│           ▼                  ▼                  ▼              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐       │
│  │Spark Worker 1│   │Spark Worker 2│   │Spark Worker 3│       │
│  │  ┌────────┐  │   │  ┌────────┐  │   │  ┌────────┐  │       │
│  │  │TF Chief│  │   │  │TF Wrkr │  │   │  │TF Wrkr │  │       │
│  │  └────────┘  │   │  └────────┘  │   │  └────────┘  │       │
│  └──────────────┘   └──────────────┘   └──────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### TFCluster API

```python
from tensorflowonspark import TFCluster

cluster = TFCluster.run(
    sc,                      # SparkContext
    main_fun,                # Training function
    tf_args,                 # Arguments passed to training
    num_executors,           # Number of TF workers
    num_ps=0,                # Number of parameter servers
    tensorboard=True,        # Enable TensorBoard
    input_mode=InputMode.SPARK,
    master_node="chief"      # or "master"
)
```

## Data Flow

### 1. Ingestion Phase

```
Raw Data (NDJSON/CSV)
        │
        ▼
    php_cx_request.php
    - Parse input
    - Validate schema
    - Transform data
        │
        ▼
    cx_orchestrate.php
    - Route to handlers
    - Coordinate services
        │
        ▼
    Supabase Upload
    - Store processed data
    - Get data URL/path
```

### 2. Training Phase

```
    Data Path
        │
        ▼
    tfos_integration.php
    - Create job spec
    - Prepare data
    - Build spark-submit
        │
        ▼
    spark-submit
    - Launch Spark job
    - Initialize TFCluster
        │
        ▼
    TFoS Training Script
    - Load data
    - Build model
    - Distributed training
    - Export model
        │
        ▼
    SavedModel Output
    /models/tfos/{job_id}/
```

### 3. Inference Phase

```
    Trained Model
        │
        ▼
    AutoML Service
    /predict endpoint
        │
        ▼
    Predictions
```

## Monitoring

### TensorBoard

When `TFOS_TENSORBOARD=true`, TensorBoard logs are written to:
```
/tmp/tfos_logs/{job_id}/
```

Launch TensorBoard:
```bash
tensorboard --logdir=/tmp/tfos_logs
```

### Job Status API

```bash
# Get detailed job status
curl http://localhost:8000/tfos/status/{job_id}

# Response
{
    "job_id": "uuid-here",
    "status": "running",
    "progress": 0.45,
    "model_dir": "/models/tfos/uuid",
    "metrics": null,
    "created_at": "2024-01-15T10:30:00Z",
    "completed_at": null
}
```

### Spark Web UI

- Master UI: `http://spark-master:8080`
- Application UI: `http://spark-master:4040` (during job execution)

## Troubleshooting

### Common Issues

#### 1. Spark cluster not available

```bash
# Check Spark master
curl http://localhost:8080/json/

# Check environment
echo $SPARK_HOME
which spark-submit
```

#### 2. TFoS job fails immediately

Check logs in `/tmp/tfos_logs/{job_id}/stderr.log`

Common causes:
- Python environment mismatch
- Missing TensorFlow/TensorFlowOnSpark packages
- Incorrect Spark master URL

#### 3. Out of memory errors

Increase executor memory:
```bash
export TFOS_EXECUTOR_MEMORY=8g
```

Or adjust in job request:
```json
{
    "executor_memory": "8g"
}
```

#### 4. Model not exported

Check model directory permissions:
```bash
ls -la /models/tfos/
```

Ensure the TensorFlow worker has write access.

## Best Practices

1. **Cluster Sizing**: Start with 2-4 workers, scale based on data size
2. **Batch Size**: Use larger batches for distributed training (128-512)
3. **Data Format**: NDJSON for flexibility, TFRecords for performance
4. **Input Mode**: Use SPARK for data already in Spark, TENSORFLOW for TFRecords
5. **Checkpointing**: Enable for long-running jobs
6. **Monitoring**: Always enable TensorBoard for training visibility

## Security Considerations

1. **Network**: Ensure Spark cluster is on private network
2. **Authentication**: Configure Spark authentication if needed
3. **Data Access**: Validate data paths before training
4. **Model Storage**: Secure model directory with proper permissions

## Integration Checklist

- [ ] Spark cluster running (Standalone, YARN, or Kubernetes)
- [ ] TensorFlow and TensorFlowOnSpark installed on all workers
- [ ] Environment variables configured
- [ ] Model directory writable
- [ ] AutoML service accessible
- [ ] Network connectivity between components
