<?php

declare(strict_types=1);

/**
 * TensorFlowOnSpark (TFoS) Integration Module.
 *
 * Provides PHP integration with Yahoo's TensorFlowOnSpark framework for
 * distributed deep learning on Spark clusters. This module bridges the
 * CX ingestion pipeline with TFoS capabilities.
 *
 * Architecture:
 *   - Ingested data (NDJSON/CSV) → Spark DataFrame
 *   - TFCluster.run() → Distributed TF workers
 *   - Model artifacts → Storage (Supabase/HDFS/S3)
 *
 * Reference: https://github.com/yahoo/TensorFlowOnSpark
 *
 * Environment Variables:
 *   TFOS_ENABLED                    Enable TFoS integration (default: false)
 *   TFOS_SPARK_MASTER               Spark master URL (default: local[*])
 *   TFOS_CLUSTER_SIZE               Number of TF workers (default: 2)
 *   TFOS_NUM_PS                     Number of parameter servers (default: 0)
 *   TFOS_INPUT_MODE                 TENSORFLOW or SPARK (default: SPARK)
 *   TFOS_TENSORBOARD                Enable TensorBoard (default: true)
 *   TFOS_MODEL_DIR                  Model output directory
 *   TFOS_EXPORT_DIR                 SavedModel export directory
 *   TFOS_EPOCHS                     Training epochs (default: 5)
 *   TFOS_BATCH_SIZE                 Batch size (default: 64)
 *   TFOS_PYTHON_EXECUTABLE          Python executable path
 *   TFOS_SPARK_SUBMIT               spark-submit path
 *   TFOS_TRAINING_SCRIPT            Custom training script path
 *   TFOS_RESERVATION_TIMEOUT        Cluster reservation timeout (default: 600)
 *   TFOS_GRACE_SECS                 Shutdown grace period (default: 30)
 *   TFOS_HDFS_PREFIX                HDFS prefix for data (optional)
 *   TFOS_API_ENDPOINT               AutoML service endpoint for job submission
 */

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/**
 * @return array<string, mixed>
 */
function tfos_get_config(): array
{
    return [
        'enabled' => tfos_bool(getenv('TFOS_ENABLED') ?: 'false'),
        'spark_master' => getenv('TFOS_SPARK_MASTER') ?: 'local[*]',
        'cluster_size' => max(1, (int) (getenv('TFOS_CLUSTER_SIZE') ?: 2)),
        'num_ps' => max(0, (int) (getenv('TFOS_NUM_PS') ?: 0)),
        'input_mode' => strtoupper(getenv('TFOS_INPUT_MODE') ?: 'SPARK'),
        'tensorboard' => tfos_bool(getenv('TFOS_TENSORBOARD') ?: 'true'),
        'model_dir' => getenv('TFOS_MODEL_DIR') ?: '/tmp/tfos_models',
        'export_dir' => getenv('TFOS_EXPORT_DIR') ?: '/tmp/tfos_exports',
        'epochs' => max(1, (int) (getenv('TFOS_EPOCHS') ?: 5)),
        'batch_size' => max(1, (int) (getenv('TFOS_BATCH_SIZE') ?: 64)),
        'python_executable' => getenv('TFOS_PYTHON_EXECUTABLE') ?: 'python3',
        'spark_submit' => getenv('TFOS_SPARK_SUBMIT') ?: 'spark-submit',
        'training_script' => getenv('TFOS_TRAINING_SCRIPT') ?: '',
        'reservation_timeout' => max(60, (int) (getenv('TFOS_RESERVATION_TIMEOUT') ?: 600)),
        'grace_secs' => max(0, (int) (getenv('TFOS_GRACE_SECS') ?: 30)),
        'hdfs_prefix' => getenv('TFOS_HDFS_PREFIX') ?: '',
        'api_endpoint' => getenv('TFOS_API_ENDPOINT') ?: 'http://localhost:8000',
        'buffer_size' => max(1000, (int) (getenv('TFOS_BUFFER_SIZE') ?: 10000)),
        'max_steps' => max(0, (int) (getenv('TFOS_MAX_STEPS') ?: 0)),
        'log_dir' => getenv('TFOS_LOG_DIR') ?: '/tmp/tfos_logs',
        'driver_ps_nodes' => tfos_bool(getenv('TFOS_DRIVER_PS_NODES') ?: 'false'),
        'master_node' => getenv('TFOS_MASTER_NODE') ?: 'chief',
        'eval_node' => tfos_bool(getenv('TFOS_EVAL_NODE') ?: 'false'),
    ];
}

function tfos_bool(string $v): bool
{
    return in_array(strtolower(trim($v)), ['1', 'true', 'yes', 'on'], true);
}

// ---------------------------------------------------------------------------
// Job Specification
// ---------------------------------------------------------------------------

/**
 * TFoS Job specification following TFCluster.run() parameters.
 *
 * @param array<string, mixed> $data Ingested data info
 * @param array<string, mixed> $options Training options
 * @return array<string, mixed>
 */
function tfos_create_job_spec(array $data, array $options = []): array
{
    $config = tfos_get_config();
    $jobId = 'tfos_' . gmdate('Ymd_His') . '_' . bin2hex(random_bytes(4));

    return [
        'job_id' => $jobId,
        'job_type' => 'tfos_distributed_training',
        'created_at' => gmdate('c'),

        // Spark configuration
        'spark' => [
            'master' => $options['spark_master'] ?? $config['spark_master'],
            'app_name' => $options['app_name'] ?? 'CXFlow-TFoS-Training',
            'executor_instances' => $options['cluster_size'] ?? $config['cluster_size'],
            'cores_per_executor' => $options['cores_per_executor'] ?? 1,
            'executor_memory' => $options['executor_memory'] ?? '2g',
            'driver_memory' => $options['driver_memory'] ?? '1g',
            'conf' => array_merge([
                'spark.task.cpus' => '1',
                'spark.scheduler.barrier.maxConcurrentTasksCheck.maxFailures' => '3',
            ], $options['spark_conf'] ?? []),
        ],

        // TFCluster configuration (mirrors TFCluster.run() parameters)
        'tfcluster' => [
            'num_executors' => $options['cluster_size'] ?? $config['cluster_size'],
            'num_ps' => $options['num_ps'] ?? $config['num_ps'],
            'tensorboard' => $options['tensorboard'] ?? $config['tensorboard'],
            'input_mode' => $options['input_mode'] ?? $config['input_mode'],
            'log_dir' => $options['log_dir'] ?? $config['log_dir'] . '/' . $jobId,
            'driver_ps_nodes' => $options['driver_ps_nodes'] ?? $config['driver_ps_nodes'],
            'master_node' => $options['master_node'] ?? $config['master_node'],
            'reservation_timeout' => $options['reservation_timeout'] ?? $config['reservation_timeout'],
            'queues' => ['input', 'output', 'error'],
            'eval_node' => $options['eval_node'] ?? $config['eval_node'],
            'release_port' => true,
        ],

        // Training parameters
        'training' => [
            'epochs' => $options['epochs'] ?? $config['epochs'],
            'batch_size' => $options['batch_size'] ?? $config['batch_size'],
            'buffer_size' => $options['buffer_size'] ?? $config['buffer_size'],
            'max_steps' => $options['max_steps'] ?? $config['max_steps'],
            'learning_rate' => $options['learning_rate'] ?? 0.001,
            'optimizer' => $options['optimizer'] ?? 'adam',
            'loss' => $options['loss'] ?? 'sparse_categorical_crossentropy',
            'metrics' => $options['metrics'] ?? ['accuracy'],
        ],

        // Model configuration
        'model' => [
            'model_dir' => ($options['model_dir'] ?? $config['model_dir']) . '/' . $jobId,
            'export_dir' => ($options['export_dir'] ?? $config['export_dir']) . '/' . $jobId,
            'checkpoint_freq' => $options['checkpoint_freq'] ?? 'epoch',
            'save_best_only' => $options['save_best_only'] ?? true,
            'model_type' => $options['model_type'] ?? 'auto',
            'problem_type' => $options['problem_type'] ?? 'classification',
        ],

        // Data configuration (from ingestion)
        'data' => [
            'source' => $data['source'] ?? 'ingestion',
            'run_id' => $data['run_id'] ?? null,
            'run_dir' => $data['run_dir'] ?? null,
            'rows_path' => $data['rows_path'] ?? null,
            'target_column' => $options['target_column'] ?? $data['target_column'] ?? 'label',
            'feature_columns' => $options['feature_columns'] ?? $data['feature_columns'] ?? [],
            'format' => $data['format'] ?? 'ndjson',
            'row_count' => $data['row_count'] ?? 0,
            'hdfs_path' => tfos_to_hdfs_path($data['rows_path'] ?? '', $config['hdfs_prefix']),
        ],

        // Distribution strategy (matches TF DistributionStrategy)
        'distribution' => [
            'strategy' => $options['distribution_strategy'] ?? 'MultiWorkerMirroredStrategy',
            'communication' => $options['communication'] ?? 'ring',
            'num_gpus' => $options['num_gpus'] ?? 0,
        ],

        // Lifecycle
        'lifecycle' => [
            'grace_secs' => $options['grace_secs'] ?? $config['grace_secs'],
            'timeout' => $options['timeout'] ?? 86400,
            'max_retries' => $options['max_retries'] ?? 2,
        ],
    ];
}

/**
 * Convert local path to HDFS path if prefix is set.
 */
function tfos_to_hdfs_path(string $localPath, string $hdfsPrefix): ?string
{
    if ($localPath === '' || $hdfsPrefix === '') {
        return null;
    }

    // If already HDFS path, return as-is
    if (str_starts_with($localPath, 'hdfs://') || str_starts_with($localPath, 'file://')) {
        return $localPath;
    }

    return rtrim($hdfsPrefix, '/') . '/' . ltrim($localPath, '/');
}

// ---------------------------------------------------------------------------
// Spark Submit Command Builder
// ---------------------------------------------------------------------------

/**
 * Build spark-submit command for TFoS job.
 *
 * @param array<string, mixed> $jobSpec
 * @return array{command: string, args: array<string>}
 */
function tfos_build_spark_submit(array $jobSpec): array
{
    $config = tfos_get_config();
    $spark = $jobSpec['spark'] ?? [];
    $tfcluster = $jobSpec['tfcluster'] ?? [];
    $training = $jobSpec['training'] ?? [];
    $model = $jobSpec['model'] ?? [];
    $data = $jobSpec['data'] ?? [];

    $sparkSubmit = $config['spark_submit'];

    $args = [
        '--master', $spark['master'] ?? 'local[*]',
        '--conf', 'spark.cores.max=' . (($spark['executor_instances'] ?? 2) * ($spark['cores_per_executor'] ?? 1)),
        '--conf', 'spark.task.cpus=' . ($spark['cores_per_executor'] ?? 1),
        '--conf', 'spark.executor.memory=' . ($spark['executor_memory'] ?? '2g'),
        '--conf', 'spark.driver.memory=' . ($spark['driver_memory'] ?? '1g'),
    ];

    // Add extra Spark conf
    foreach (($spark['conf'] ?? []) as $key => $value) {
        $args[] = '--conf';
        $args[] = $key . '=' . $value;
    }

    // Determine training script
    $trainingScript = $config['training_script'];
    if ($trainingScript === '' || !is_file($trainingScript)) {
        $trainingScript = __DIR__ . '/tfos_training_script.py';
    }

    $args[] = $trainingScript;

    // TFoS arguments (passed to the Python script)
    $args[] = '--cluster_size';
    $args[] = (string) ($tfcluster['num_executors'] ?? 2);

    $args[] = '--num_ps';
    $args[] = (string) ($tfcluster['num_ps'] ?? 0);

    $args[] = '--epochs';
    $args[] = (string) ($training['epochs'] ?? 5);

    $args[] = '--batch_size';
    $args[] = (string) ($training['batch_size'] ?? 64);

    $args[] = '--buffer_size';
    $args[] = (string) ($training['buffer_size'] ?? 10000);

    $args[] = '--model_dir';
    $args[] = $model['model_dir'] ?? '/tmp/tfos_model';

    $args[] = '--export_dir';
    $args[] = $model['export_dir'] ?? '/tmp/tfos_export';

    // Data path
    $dataPath = $data['hdfs_path'] ?? $data['rows_path'] ?? '';
    if ($dataPath !== '') {
        $args[] = '--data_path';
        $args[] = $dataPath;
    }

    // Target column
    $args[] = '--target_column';
    $args[] = $data['target_column'] ?? 'label';

    // TensorBoard
    if ($tfcluster['tensorboard'] ?? false) {
        $args[] = '--tensorboard';
    }

    // Input mode
    $args[] = '--input_mode';
    $args[] = strtoupper($tfcluster['input_mode'] ?? 'SPARK');

    // Master node (chief/master)
    $masterNode = $tfcluster['master_node'] ?? '';
    if ($masterNode !== '') {
        $args[] = '--master_node';
        $args[] = $masterNode;
    }

    // Learning rate
    $args[] = '--learning_rate';
    $args[] = (string) ($training['learning_rate'] ?? 0.001);

    // Format
    $args[] = '--format';
    $args[] = $data['format'] ?? 'ndjson';

    return [
        'command' => $sparkSubmit,
        'args' => $args,
    ];
}

/**
 * Build the full command string (for exec()).
 */
function tfos_build_command_string(array $jobSpec): string
{
    $cmd = tfos_build_spark_submit($jobSpec);
    $parts = [$cmd['command']];

    foreach ($cmd['args'] as $arg) {
        $parts[] = escapeshellarg($arg);
    }

    return implode(' ', $parts);
}

// ---------------------------------------------------------------------------
// Job Submission & Management
// ---------------------------------------------------------------------------

/**
 * Submit a TFoS job for execution.
 *
 * @param array<string, mixed> $jobSpec
 * @return array<string, mixed>
 */
function tfos_submit_job(array $jobSpec): array
{
    $config = tfos_get_config();

    if (!$config['enabled']) {
        return [
            'ok' => false,
            'error' => 'tfos_disabled',
            'message' => 'TFoS integration is not enabled. Set TFOS_ENABLED=true.',
        ];
    }

    $jobId = $jobSpec['job_id'] ?? 'unknown';
    $modelDir = $jobSpec['model']['model_dir'] ?? '/tmp/tfos_model';
    $logDir = $jobSpec['tfcluster']['log_dir'] ?? '/tmp/tfos_logs/' . $jobId;

    // Ensure directories exist
    @mkdir($modelDir, 0775, true);
    @mkdir($logDir, 0775, true);

    // Write job spec to file
    $jobSpecPath = $logDir . '/job_spec.json';
    file_put_contents($jobSpecPath, json_encode($jobSpec, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");

    // Build command
    $commandStr = tfos_build_command_string($jobSpec);

    // Log command (redact sensitive parts)
    $logPath = $logDir . '/job.log';
    $startTime = microtime(true);

    file_put_contents($logPath, "[" . gmdate('c') . "] Starting TFoS job: $jobId\n", FILE_APPEND);
    file_put_contents($logPath, "[" . gmdate('c') . "] Command: spark-submit ... (see job_spec.json)\n", FILE_APPEND);

    // Execute
    $output = [];
    $returnCode = 0;
    exec($commandStr . ' 2>&1', $output, $returnCode);

    $duration = microtime(true) - $startTime;
    $outputStr = implode("\n", $output);

    file_put_contents($logPath, $outputStr . "\n", FILE_APPEND);
    file_put_contents($logPath, "[" . gmdate('c') . "] Exit code: $returnCode, Duration: " . round($duration, 2) . "s\n", FILE_APPEND);

    // Write output
    file_put_contents($logDir . '/spark_output.log', $outputStr . "\n");

    $result = [
        'ok' => $returnCode === 0,
        'job_id' => $jobId,
        'exit_code' => $returnCode,
        'duration_sec' => round($duration, 2),
        'model_dir' => $modelDir,
        'log_dir' => $logDir,
        'job_spec_path' => $jobSpecPath,
    ];

    // Check for exported model
    $exportDir = $jobSpec['model']['export_dir'] ?? '';
    if ($exportDir !== '' && is_dir($exportDir)) {
        $result['export_dir'] = $exportDir;
        $result['has_export'] = true;
    }

    // Write result
    $resultPath = $logDir . '/job_result.json';
    file_put_contents($resultPath, json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");
    $result['result_path'] = $resultPath;

    return $result;
}

/**
 * Submit job asynchronously (background process).
 *
 * @param array<string, mixed> $jobSpec
 * @return array<string, mixed>
 */
function tfos_submit_job_async(array $jobSpec): array
{
    $config = tfos_get_config();

    if (!$config['enabled']) {
        return [
            'ok' => false,
            'error' => 'tfos_disabled',
            'message' => 'TFoS integration is not enabled.',
        ];
    }

    $jobId = $jobSpec['job_id'] ?? 'unknown';
    $logDir = $jobSpec['tfcluster']['log_dir'] ?? '/tmp/tfos_logs/' . $jobId;

    @mkdir($logDir, 0775, true);

    // Write job spec
    $jobSpecPath = $logDir . '/job_spec.json';
    file_put_contents($jobSpecPath, json_encode($jobSpec, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");

    // Build command and run in background
    $commandStr = tfos_build_command_string($jobSpec);
    $logPath = $logDir . '/spark_output.log';
    $pidPath = $logDir . '/job.pid';

    $bgCommand = sprintf(
        'nohup %s > %s 2>&1 & echo $! > %s',
        $commandStr,
        escapeshellarg($logPath),
        escapeshellarg($pidPath)
    );

    exec($bgCommand);

    // Read PID
    $pid = null;
    if (is_file($pidPath)) {
        $pid = (int) trim((string) file_get_contents($pidPath));
    }

    // Write status file
    $statusPath = $logDir . '/job_status.json';
    $status = [
        'status' => 'running',
        'job_id' => $jobId,
        'pid' => $pid,
        'started_at' => gmdate('c'),
        'log_path' => $logPath,
    ];
    file_put_contents($statusPath, json_encode($status, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");

    return [
        'ok' => true,
        'job_id' => $jobId,
        'status' => 'running',
        'pid' => $pid,
        'log_dir' => $logDir,
        'status_path' => $statusPath,
    ];
}

/**
 * Check status of an async job.
 *
 * @return array<string, mixed>
 */
function tfos_check_job_status(string $jobId, string $logDir): array
{
    $statusPath = $logDir . '/job_status.json';
    $resultPath = $logDir . '/job_result.json';
    $pidPath = $logDir . '/job.pid';

    // Check if result exists (completed)
    if (is_file($resultPath)) {
        /** @var mixed $result */
        $result = json_decode((string) file_get_contents($resultPath), true);
        if (is_array($result)) {
            $result['status'] = $result['ok'] ? 'completed' : 'failed';
            return $result;
        }
    }

    // Check if process is still running
    if (is_file($pidPath)) {
        $pid = (int) trim((string) file_get_contents($pidPath));
        if ($pid > 0) {
            // Check if process exists
            $exists = posix_kill($pid, 0);
            if (!$exists) {
                // Process finished but no result file - check log
                return [
                    'ok' => false,
                    'job_id' => $jobId,
                    'status' => 'failed',
                    'message' => 'Process exited without result file',
                ];
            }

            return [
                'ok' => true,
                'job_id' => $jobId,
                'status' => 'running',
                'pid' => $pid,
            ];
        }
    }

    return [
        'ok' => false,
        'job_id' => $jobId,
        'status' => 'unknown',
    ];
}

// ---------------------------------------------------------------------------
// Data Preparation
// ---------------------------------------------------------------------------

/**
 * Prepare ingested data for TFoS consumption.
 *
 * @param array<string, mixed> $manifest Ingestion manifest
 * @param string $runDir Ingestion run directory
 * @return array<string, mixed>
 */
function tfos_prepare_data(array $manifest, string $runDir): array
{
    $rowsPath = $manifest['artifacts']['rows_ndjson'] ?? null;
    $rowsCsvPath = $manifest['artifacts']['rows_csv'] ?? null;
    $rowStats = $manifest['parsed']['row_stats'] ?? null;

    // Prefer NDJSON, fall back to CSV
    $dataPath = null;
    $format = 'unknown';

    if (is_string($rowsPath) && is_file($rowsPath)) {
        $dataPath = $rowsPath;
        $format = 'ndjson';
    } elseif (is_string($rowsCsvPath) && is_file($rowsCsvPath)) {
        $dataPath = $rowsCsvPath;
        $format = 'csv';
    }

    // Infer schema from row stats
    $columns = [];
    $targetColumn = null;
    $featureColumns = [];

    if (is_array($rowStats)) {
        $columns = $rowStats['columns'] ?? [];

        // Heuristic: common target column names
        foreach (['label', 'target', 'class', 'y', 'output', 'prediction'] as $candidate) {
            if (in_array($candidate, $columns, true)) {
                $targetColumn = $candidate;
                break;
            }
        }

        // All other columns are features
        if ($targetColumn !== null) {
            $featureColumns = array_values(array_filter($columns, fn ($c) => $c !== $targetColumn));
        }
    }

    return [
        'source' => 'ingestion',
        'run_id' => $manifest['run_id'] ?? null,
        'run_dir' => $runDir,
        'rows_path' => $dataPath,
        'format' => $format,
        'row_count' => $rowStats['row_count'] ?? 0,
        'columns' => $columns,
        'target_column' => $targetColumn,
        'feature_columns' => $featureColumns,
        'http_code' => $manifest['response']['http_code'] ?? null,
        'content_type' => $manifest['response']['content_type'] ?? null,
    ];
}

// ---------------------------------------------------------------------------
// API Integration
// ---------------------------------------------------------------------------

/**
 * Submit job via AutoML API (for containerized deployment).
 *
 * @param array<string, mixed> $jobSpec
 * @return array<string, mixed>
 */
function tfos_submit_via_api(array $jobSpec): array
{
    $config = tfos_get_config();
    $endpoint = rtrim($config['api_endpoint'], '/') . '/tfos/submit';

    $ch = curl_init($endpoint);
    if ($ch === false) {
        return ['ok' => false, 'error' => 'curl_init_failed'];
    }

    $body = json_encode($jobSpec, JSON_UNESCAPED_SLASHES);
    if (!is_string($body)) {
        $body = '{}';
    }

    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_CONNECTTIMEOUT => 10,
        CURLOPT_TIMEOUT => 30,
        CURLOPT_HTTPHEADER => [
            'Content-Type: application/json',
            'Accept: application/json',
            'User-Agent: cxflow-tfos/1.0',
        ],
        CURLOPT_POSTFIELDS => $body,
    ]);

    $resp = curl_exec($ch);
    $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err = curl_error($ch);
    curl_close($ch);

    if ($resp === false) {
        return ['ok' => false, 'http_code' => $code, 'error' => $err];
    }

    /** @var mixed $json */
    $json = json_decode((string) $resp, true);
    if (!is_array($json)) {
        return ['ok' => false, 'http_code' => $code, 'error' => 'invalid_response'];
    }

    return $json;
}

// ---------------------------------------------------------------------------
// Orchestration Integration
// ---------------------------------------------------------------------------

/**
 * Run TFoS training from orchestration pipeline.
 *
 * This is the main entry point called from cx_orchestrate.php.
 *
 * @param array<string, mixed>|null $manifest
 * @param string|null $runDir
 * @param array<string, mixed> $options
 * @return array<string, mixed>|null
 */
function orch_run_tfos_training(?array $manifest, ?string $runDir, array $options = []): ?array
{
    $config = tfos_get_config();

    if (!$config['enabled']) {
        return null;
    }

    if (!is_array($manifest) || !is_string($runDir) || $runDir === '') {
        return ['ok' => false, 'error' => 'missing_data'];
    }

    // Check if we have data to train on
    $rowsPath = $manifest['artifacts']['rows_ndjson'] ?? $manifest['artifacts']['rows_csv'] ?? null;
    if (!is_string($rowsPath) || !is_file($rowsPath)) {
        return ['ok' => false, 'error' => 'no_training_data'];
    }

    // Prepare data from ingestion
    $data = tfos_prepare_data($manifest, $runDir);

    if ($data['row_count'] < 10) {
        return ['ok' => false, 'error' => 'insufficient_rows', 'row_count' => $data['row_count']];
    }

    // Create job specification
    $jobSpec = tfos_create_job_spec($data, $options);

    // Determine submission mode
    $useApi = tfos_bool(getenv('TFOS_USE_API') ?: 'false');
    $async = tfos_bool(getenv('TFOS_ASYNC') ?: 'true');

    if ($useApi) {
        $result = tfos_submit_via_api($jobSpec);
    } elseif ($async) {
        $result = tfos_submit_job_async($jobSpec);
    } else {
        $result = tfos_submit_job($jobSpec);
    }

    // Store result in run directory
    $resultPath = rtrim($runDir, '/') . '/tfos.result.json';
    file_put_contents($resultPath, json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");

    return $result;
}
