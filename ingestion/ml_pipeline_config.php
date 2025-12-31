<?php

declare(strict_types=1);

/**
 * ML Pipeline Configuration for TensorFlowOnSpark Integration.
 *
 * Defines pipeline stages, data transformations, and model configurations
 * for end-to-end ML workflows triggered by CX ingestion.
 *
 * Pipeline Stages:
 *   1. Data Ingestion (php_cx_request.php)
 *   2. Data Validation & Profiling
 *   3. Feature Engineering
 *   4. Model Training (TFoS / AutoML)
 *   5. Model Evaluation
 *   6. Model Export & Deployment
 *   7. Notification & Webhook
 *
 * Environment Variables:
 *   CX_ML_PIPELINE_ENABLED=true|false
 *   CX_ML_PIPELINE_CONFIG_PATH=/path/to/pipeline.json
 *   CX_ML_PIPELINE_MODE=tfos|automl|both
 */

// ---------------------------------------------------------------------------
// Pipeline Configuration
// ---------------------------------------------------------------------------

/**
 * @return array<string, mixed>
 */
function mlpipe_get_default_config(): array
{
    return [
        'version' => '1.0',
        'name' => 'cxflow-ml-pipeline',
        'description' => 'CX Ingestion to ML Training Pipeline',

        // Pipeline stages
        'stages' => [
            'ingestion' => [
                'enabled' => true,
                'timeout_seconds' => 60,
                'retry_count' => 2,
                'retry_delay_seconds' => 5,
            ],
            'validation' => [
                'enabled' => true,
                'min_rows' => 10,
                'max_rows' => 100000,
                'required_columns' => [],
                'null_threshold' => 0.5,
            ],
            'profiling' => [
                'enabled' => true,
                'sample_size' => 1000,
                'compute_correlations' => false,
            ],
            'feature_engineering' => [
                'enabled' => true,
                'auto_encode_categoricals' => true,
                'handle_missing' => 'median',
                'scale_numerics' => true,
                'drop_high_cardinality' => 100,
            ],
            'training' => [
                'enabled' => true,
                'mode' => 'automl',  // tfos | automl | both
                'tfos' => [
                    'enabled' => false,
                    'cluster_size' => 2,
                    'num_ps' => 0,
                    'epochs' => 5,
                    'batch_size' => 64,
                    'input_mode' => 'SPARK',
                    'async' => true,
                ],
                'automl' => [
                    'enabled' => true,
                    'endpoint' => 'http://localhost:8000',
                    'enable_cv' => true,
                    'enable_tuning' => false,
                    'timeout_seconds' => 300,
                ],
            ],
            'evaluation' => [
                'enabled' => true,
                'metrics' => ['accuracy', 'f1', 'rmse', 'mae'],
                'threshold' => [
                    'classification' => ['accuracy' => 0.7, 'f1' => 0.6],
                    'regression' => ['r2' => 0.5],
                ],
            ],
            'export' => [
                'enabled' => true,
                'formats' => ['savedmodel', 'keras', 'onnx'],
                'upload_to_supabase' => true,
            ],
            'notification' => [
                'enabled' => true,
                'on_success' => true,
                'on_failure' => true,
                'channels' => ['webhook'],
            ],
        ],

        // Data schema inference
        'schema' => [
            'auto_infer' => true,
            'target_column_hints' => ['label', 'target', 'class', 'y', 'output'],
            'exclude_columns' => ['id', 'uuid', 'created_at', 'updated_at'],
            'datetime_columns' => ['timestamp', 'date', 'datetime'],
        ],

        // Problem type inference
        'problem_detection' => [
            'classification_threshold' => 20,
            'binary_threshold' => 2,
        ],

        // Resource limits
        'resources' => [
            'max_memory_mb' => 4096,
            'max_training_time_seconds' => 3600,
            'max_model_size_mb' => 500,
        ],
    ];
}

/**
 * Load pipeline configuration from file or environment.
 *
 * @return array<string, mixed>
 */
function mlpipe_load_config(): array
{
    $configPath = getenv('CX_ML_PIPELINE_CONFIG_PATH') ?: '';

    if ($configPath !== '' && is_file($configPath)) {
        $raw = (string) file_get_contents($configPath);
        /** @var mixed $json */
        $json = json_decode($raw, true);
        if (is_array($json)) {
            return array_merge_recursive(mlpipe_get_default_config(), $json);
        }
    }

    // Build from environment
    $config = mlpipe_get_default_config();

    // Override from env
    if (getenv('CX_ML_PIPELINE_MODE')) {
        $config['stages']['training']['mode'] = (string) getenv('CX_ML_PIPELINE_MODE');
    }

    if (getenv('TFOS_ENABLED') === 'true') {
        $config['stages']['training']['tfos']['enabled'] = true;
        $config['stages']['training']['tfos']['cluster_size'] = (int) (getenv('TFOS_CLUSTER_SIZE') ?: 2);
        $config['stages']['training']['tfos']['epochs'] = (int) (getenv('TFOS_EPOCHS') ?: 5);
    }

    if (getenv('CX_AUTOML_ENABLED') === 'true') {
        $config['stages']['training']['automl']['enabled'] = true;
        $config['stages']['training']['automl']['endpoint'] = (string) (getenv('CX_AUTOML_ENDPOINT') ?: 'http://localhost:8000');
    }

    return $config;
}

// ---------------------------------------------------------------------------
// Pipeline Execution
// ---------------------------------------------------------------------------

/**
 * Pipeline execution context.
 */
class MLPipelineContext
{
    public string $pipelineId;
    public string $runId;
    public string $runDir;
    /** @var array<string, mixed> */
    public array $config;
    /** @var array<string, mixed> */
    public array $manifest;
    /** @var array<string, mixed> */
    public array $stageResults = [];
    public float $startTime;
    /** @var array<string, string> */
    public array $errors = [];

    public function __construct(string $runId, string $runDir, array $config, array $manifest)
    {
        $this->pipelineId = 'pipe_' . gmdate('Ymd_His') . '_' . bin2hex(random_bytes(4));
        $this->runId = $runId;
        $this->runDir = $runDir;
        $this->config = $config;
        $this->manifest = $manifest;
        $this->startTime = microtime(true);
    }

    public function addStageResult(string $stage, array $result): void
    {
        $this->stageResults[$stage] = [
            'result' => $result,
            'timestamp' => gmdate('c'),
        ];
    }

    public function addError(string $stage, string $message): void
    {
        $this->errors[$stage] = $message;
    }

    public function toArray(): array
    {
        return [
            'pipeline_id' => $this->pipelineId,
            'run_id' => $this->runId,
            'run_dir' => $this->runDir,
            'started_at' => date('c', (int) $this->startTime),
            'duration_sec' => round(microtime(true) - $this->startTime, 2),
            'stages' => $this->stageResults,
            'errors' => $this->errors,
            'ok' => empty($this->errors),
        ];
    }
}

/**
 * Run validation stage.
 *
 * @param MLPipelineContext $ctx
 * @return array<string, mixed>
 */
function mlpipe_stage_validation(MLPipelineContext $ctx): array
{
    $config = $ctx->config['stages']['validation'] ?? [];

    if (!($config['enabled'] ?? true)) {
        return ['skipped' => true];
    }

    $rowStats = $ctx->manifest['parsed']['row_stats'] ?? null;
    $rowCount = is_array($rowStats) ? ($rowStats['row_count'] ?? 0) : 0;

    $errors = [];

    // Check minimum rows
    $minRows = (int) ($config['min_rows'] ?? 10);
    if ($rowCount < $minRows) {
        $errors[] = "Insufficient rows: $rowCount < $minRows";
    }

    // Check maximum rows
    $maxRows = (int) ($config['max_rows'] ?? 100000);
    if ($rowCount > $maxRows) {
        $errors[] = "Too many rows: $rowCount > $maxRows (will be truncated)";
    }

    // Check required columns
    $columns = is_array($rowStats) ? ($rowStats['columns'] ?? []) : [];
    $required = (array) ($config['required_columns'] ?? []);
    foreach ($required as $col) {
        if (!in_array($col, $columns, true)) {
            $errors[] = "Missing required column: $col";
        }
    }

    $ok = empty($errors);

    $result = [
        'ok' => $ok,
        'row_count' => $rowCount,
        'column_count' => count($columns),
        'columns' => $columns,
        'errors' => $errors,
    ];

    $ctx->addStageResult('validation', $result);

    if (!$ok) {
        $ctx->addError('validation', implode('; ', $errors));
    }

    return $result;
}

/**
 * Run profiling stage.
 *
 * @param MLPipelineContext $ctx
 * @return array<string, mixed>
 */
function mlpipe_stage_profiling(MLPipelineContext $ctx): array
{
    $config = $ctx->config['stages']['profiling'] ?? [];

    if (!($config['enabled'] ?? true)) {
        return ['skipped' => true];
    }

    $rowsPath = $ctx->manifest['artifacts']['rows_ndjson'] ?? null;
    if (!is_string($rowsPath) || !is_file($rowsPath)) {
        return ['ok' => false, 'error' => 'no_data'];
    }

    // Read sample
    $sampleSize = (int) ($config['sample_size'] ?? 1000);
    $rows = orch_read_ndjson_rows($rowsPath, $sampleSize);

    if (empty($rows)) {
        return ['ok' => false, 'error' => 'empty_data'];
    }

    // Profile columns
    $profile = [];
    $allColumns = [];
    foreach ($rows as $row) {
        $allColumns = array_merge($allColumns, array_keys($row));
    }
    $allColumns = array_unique($allColumns);

    foreach ($allColumns as $col) {
        $values = [];
        $nullCount = 0;

        foreach ($rows as $row) {
            $val = $row[$col] ?? null;
            if ($val === null || $val === '') {
                $nullCount++;
            } else {
                $values[] = $val;
            }
        }

        $isNumeric = count($values) > 0 && is_numeric($values[0] ?? '');

        $colProfile = [
            'name' => $col,
            'null_count' => $nullCount,
            'null_pct' => count($rows) > 0 ? round($nullCount / count($rows) * 100, 2) : 0,
            'unique_count' => count(array_unique($values)),
            'is_numeric' => $isNumeric,
        ];

        if ($isNumeric && count($values) > 0) {
            $numVals = array_map('floatval', $values);
            $colProfile['min'] = min($numVals);
            $colProfile['max'] = max($numVals);
            $colProfile['mean'] = array_sum($numVals) / count($numVals);
        }

        $profile[$col] = $colProfile;
    }

    // Infer target column
    $targetHints = (array) ($ctx->config['schema']['target_column_hints'] ?? ['label', 'target']);
    $targetColumn = null;
    foreach ($targetHints as $hint) {
        if (in_array($hint, $allColumns, true)) {
            $targetColumn = $hint;
            break;
        }
    }

    // Infer problem type
    $problemType = 'unknown';
    if ($targetColumn !== null && isset($profile[$targetColumn])) {
        $targetProfile = $profile[$targetColumn];
        $threshold = (int) ($ctx->config['problem_detection']['classification_threshold'] ?? 20);
        if ($targetProfile['unique_count'] <= $threshold) {
            $problemType = 'classification';
        } else {
            $problemType = 'regression';
        }
    }

    $result = [
        'ok' => true,
        'sample_size' => count($rows),
        'column_count' => count($allColumns),
        'columns' => $profile,
        'target_column' => $targetColumn,
        'problem_type' => $problemType,
    ];

    $ctx->addStageResult('profiling', $result);

    return $result;
}

/**
 * Run training stage.
 *
 * @param MLPipelineContext $ctx
 * @return array<string, mixed>
 */
function mlpipe_stage_training(MLPipelineContext $ctx): array
{
    $config = $ctx->config['stages']['training'] ?? [];

    if (!($config['enabled'] ?? true)) {
        return ['skipped' => true];
    }

    $mode = strtolower((string) ($config['mode'] ?? 'automl'));
    $results = [];

    // Get profiling results for target column
    $profilingResult = $ctx->stageResults['profiling']['result'] ?? [];
    $targetColumn = $profilingResult['target_column'] ?? 'label';

    // TensorFlowOnSpark training
    if (in_array($mode, ['tfos', 'both'], true)) {
        $tfosConfig = (array) ($config['tfos'] ?? []);
        if ($tfosConfig['enabled'] ?? false) {
            $tfosOptions = [
                'target_column' => $targetColumn,
                'epochs' => (int) ($tfosConfig['epochs'] ?? 5),
                'batch_size' => (int) ($tfosConfig['batch_size'] ?? 64),
                'cluster_size' => (int) ($tfosConfig['cluster_size'] ?? 2),
            ];
            $tfosResult = orch_run_tfos_training($ctx->manifest, $ctx->runDir, $tfosOptions);
            $results['tfos'] = $tfosResult;
        }
    }

    // AutoML training
    if (in_array($mode, ['automl', 'both'], true)) {
        $automlConfig = (array) ($config['automl'] ?? []);
        if ($automlConfig['enabled'] ?? true) {
            // Set env vars for automl function
            if (isset($automlConfig['endpoint'])) {
                putenv('CX_AUTOML_ENDPOINT=' . $automlConfig['endpoint']);
            }
            putenv('CX_AUTOML_TARGET_COLUMN=' . $targetColumn);
            putenv('CX_AUTOML_ENABLED=true');

            $automlResult = orch_run_automl_training($ctx->manifest, $ctx->runDir);
            $results['automl'] = $automlResult;
        }
    }

    $ok = false;
    foreach ($results as $r) {
        if (is_array($r) && ($r['ok'] ?? false)) {
            $ok = true;
            break;
        }
    }

    $result = [
        'ok' => $ok,
        'mode' => $mode,
        'results' => $results,
    ];

    $ctx->addStageResult('training', $result);

    if (!$ok) {
        $ctx->addError('training', 'All training methods failed');
    }

    return $result;
}

/**
 * Run full ML pipeline.
 *
 * @param array<string, mixed> $manifest
 * @param string $runDir
 * @param array<string, mixed>|null $config
 * @return array<string, mixed>
 */
function mlpipe_run(array $manifest, string $runDir, ?array $config = null): array
{
    $config = $config ?? mlpipe_load_config();
    $runId = (string) ($manifest['run_id'] ?? 'unknown');

    $ctx = new MLPipelineContext($runId, $runDir, $config, $manifest);

    // Stage 1: Validation
    $validationResult = mlpipe_stage_validation($ctx);
    if (!($validationResult['ok'] ?? false) && !($validationResult['skipped'] ?? false)) {
        // Validation failed - abort pipeline
        $pipelineResult = $ctx->toArray();
        mlpipe_save_result($runDir, $pipelineResult);
        return $pipelineResult;
    }

    // Stage 2: Profiling
    mlpipe_stage_profiling($ctx);

    // Stage 3: Training
    mlpipe_stage_training($ctx);

    // Save pipeline result
    $pipelineResult = $ctx->toArray();
    mlpipe_save_result($runDir, $pipelineResult);

    return $pipelineResult;
}

/**
 * Save pipeline result to file.
 */
function mlpipe_save_result(string $runDir, array $result): void
{
    $path = rtrim($runDir, '/') . '/pipeline.result.json';
    file_put_contents($path, json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");
}

// ---------------------------------------------------------------------------
// Orchestration Integration
// ---------------------------------------------------------------------------

/**
 * Run ML pipeline from orchestration (called after ingestion).
 *
 * @param array<string, mixed>|null $manifest
 * @param string|null $runDir
 * @return array<string, mixed>|null
 */
function orch_run_ml_pipeline(?array $manifest, ?string $runDir): ?array
{
    $enabled = orch_bool((string) (getenv('CX_ML_PIPELINE_ENABLED') ?: 'false'), false);

    if (!$enabled) {
        return null;
    }

    if (!is_array($manifest) || !is_string($runDir) || $runDir === '') {
        return ['ok' => false, 'error' => 'missing_data'];
    }

    return mlpipe_run($manifest, $runDir);
}
