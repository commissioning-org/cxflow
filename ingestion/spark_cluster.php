<?php

declare(strict_types=1);

/**
 * Spark Cluster Manager for TensorFlowOnSpark integration.
 *
 * Provides cluster lifecycle management and health monitoring for
 * Spark Standalone, YARN, and Kubernetes deployments.
 *
 * Reference: TFoS requires Spark Standalone or YARN (not Spark Local mode)
 * because TFoS executors must run in separate processes.
 *
 * Environment Variables:
 *   SPARK_HOME                 Path to Spark installation
 *   SPARK_MASTER               Spark master URL
 *   SPARK_WORKER_INSTANCES     Number of worker instances
 *   SPARK_CORES_PER_WORKER     Cores per worker (default: 1)
 *   SPARK_MEMORY_PER_WORKER    Memory per worker (default: 2G)
 *   SPARK_CLUSTER_MODE         standalone|yarn|kubernetes
 *   SPARK_CLASSPATH            Additional JARs (e.g., tensorflow-hadoop)
 */

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/**
 * @return array<string, mixed>
 */
function spark_get_config(): array
{
    $sparkHome = getenv('SPARK_HOME') ?: '/opt/spark';

    return [
        'spark_home' => $sparkHome,
        'master' => getenv('SPARK_MASTER') ?: getenv('MASTER') ?: 'spark://localhost:7077',
        'worker_instances' => max(1, (int) (getenv('SPARK_WORKER_INSTANCES') ?: 2)),
        'cores_per_worker' => max(1, (int) (getenv('SPARK_CORES_PER_WORKER') ?: getenv('CORES_PER_WORKER') ?: 1)),
        'memory_per_worker' => getenv('SPARK_MEMORY_PER_WORKER') ?: '2G',
        'cluster_mode' => strtolower(getenv('SPARK_CLUSTER_MODE') ?: 'standalone'),
        'classpath' => getenv('SPARK_CLASSPATH') ?: '',
        'sbin' => $sparkHome . '/sbin',
        'bin' => $sparkHome . '/bin',
        'conf_dir' => getenv('SPARK_CONF_DIR') ?: $sparkHome . '/conf',
        'log_dir' => getenv('SPARK_LOG_DIR') ?: '/tmp/spark_logs',
        'local_ip' => getenv('SPARK_LOCAL_IP') ?: '127.0.0.1',
        'ui_port' => (int) (getenv('SPARK_MASTER_WEBUI_PORT') ?: 8080),
        'worker_ui_port' => (int) (getenv('SPARK_WORKER_WEBUI_PORT') ?: 8081),
    ];
}

// ---------------------------------------------------------------------------
// Cluster Lifecycle
// ---------------------------------------------------------------------------

/**
 * Start Spark master node.
 *
 * @return array<string, mixed>
 */
function spark_start_master(): array
{
    $config = spark_get_config();
    $script = $config['sbin'] . '/start-master.sh';

    if (!is_file($script)) {
        return ['ok' => false, 'error' => 'spark_not_installed', 'path' => $script];
    }

    $env = [
        'SPARK_LOCAL_IP' => $config['local_ip'],
    ];
    $envStr = '';
    foreach ($env as $k => $v) {
        $envStr .= "export $k=" . escapeshellarg($v) . "; ";
    }

    $cmd = $envStr . escapeshellarg($script);
    $output = [];
    $rc = 0;
    exec($cmd . ' 2>&1', $output, $rc);

    // Wait a moment for master to start
    usleep(500000);

    return [
        'ok' => $rc === 0,
        'exit_code' => $rc,
        'output' => implode("\n", $output),
        'master_url' => $config['master'],
        'ui_url' => 'http://' . $config['local_ip'] . ':' . $config['ui_port'],
    ];
}

/**
 * Start Spark worker nodes.
 *
 * @param string|null $masterUrl Override master URL
 * @return array<string, mixed>
 */
function spark_start_workers(?string $masterUrl = null): array
{
    $config = spark_get_config();
    $script = $config['sbin'] . '/start-worker.sh';

    if (!is_file($script)) {
        return ['ok' => false, 'error' => 'spark_not_installed', 'path' => $script];
    }

    $master = $masterUrl ?? $config['master'];
    $cores = $config['cores_per_worker'];
    $memory = $config['memory_per_worker'];
    $instances = $config['worker_instances'];

    $results = [];
    $allOk = true;

    // Start multiple worker instances
    for ($i = 0; $i < $instances; $i++) {
        $cmd = sprintf(
            '%s -c %d -m %s %s 2>&1',
            escapeshellarg($script),
            $cores,
            escapeshellarg($memory),
            escapeshellarg($master)
        );

        $output = [];
        $rc = 0;
        exec($cmd, $output, $rc);

        $results[] = [
            'instance' => $i,
            'ok' => $rc === 0,
            'output' => implode("\n", $output),
        ];

        if ($rc !== 0) {
            $allOk = false;
        }

        // Small delay between worker starts
        usleep(200000);
    }

    return [
        'ok' => $allOk,
        'master' => $master,
        'worker_count' => $instances,
        'cores_per_worker' => $cores,
        'total_cores' => $instances * $cores,
        'results' => $results,
    ];
}

/**
 * Start full Spark Standalone cluster (master + workers).
 *
 * @return array<string, mixed>
 */
function spark_start_cluster(): array
{
    $masterResult = spark_start_master();
    if (!$masterResult['ok']) {
        return $masterResult;
    }

    // Wait for master to be ready
    sleep(1);

    $workersResult = spark_start_workers();

    return [
        'ok' => $masterResult['ok'] && $workersResult['ok'],
        'master' => $masterResult,
        'workers' => $workersResult,
        'cluster_ready' => $masterResult['ok'] && $workersResult['ok'],
    ];
}

/**
 * Stop Spark worker nodes.
 *
 * @return array<string, mixed>
 */
function spark_stop_workers(): array
{
    $config = spark_get_config();
    $script = $config['sbin'] . '/stop-worker.sh';

    if (!is_file($script)) {
        return ['ok' => false, 'error' => 'spark_not_installed'];
    }

    $output = [];
    $rc = 0;
    exec(escapeshellarg($script) . ' 2>&1', $output, $rc);

    return [
        'ok' => $rc === 0,
        'exit_code' => $rc,
        'output' => implode("\n", $output),
    ];
}

/**
 * Stop Spark master node.
 *
 * @return array<string, mixed>
 */
function spark_stop_master(): array
{
    $config = spark_get_config();
    $script = $config['sbin'] . '/stop-master.sh';

    if (!is_file($script)) {
        return ['ok' => false, 'error' => 'spark_not_installed'];
    }

    $output = [];
    $rc = 0;
    exec(escapeshellarg($script) . ' 2>&1', $output, $rc);

    return [
        'ok' => $rc === 0,
        'exit_code' => $rc,
        'output' => implode("\n", $output),
    ];
}

/**
 * Stop full Spark Standalone cluster.
 *
 * @return array<string, mixed>
 */
function spark_stop_cluster(): array
{
    $workersResult = spark_stop_workers();
    $masterResult = spark_stop_master();

    return [
        'ok' => $workersResult['ok'] && $masterResult['ok'],
        'workers' => $workersResult,
        'master' => $masterResult,
    ];
}

// ---------------------------------------------------------------------------
// Cluster Health & Status
// ---------------------------------------------------------------------------

/**
 * Get cluster status from Spark Master REST API.
 *
 * @return array<string, mixed>
 */
function spark_get_cluster_status(): array
{
    $config = spark_get_config();
    $restUrl = str_replace(':7077', ':6066', $config['master']);
    $restUrl = str_replace('spark://', 'http://', $restUrl);
    $statusEndpoint = $restUrl . '/v1/submissions/status/driver-0';

    // Try REST API first
    $ch = curl_init($config['master']);
    if ($ch === false) {
        return ['ok' => false, 'error' => 'curl_init_failed'];
    }

    // Actually check the web UI JSON endpoint
    $uiUrl = 'http://' . $config['local_ip'] . ':' . $config['ui_port'] . '/json/';

    $ch = curl_init($uiUrl);
    if ($ch === false) {
        return ['ok' => false, 'error' => 'curl_init_failed'];
    }

    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 5,
        CURLOPT_TIMEOUT => 10,
    ]);

    $resp = curl_exec($ch);
    $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    if ($resp === false || $code !== 200) {
        return [
            'ok' => false,
            'reachable' => false,
            'http_code' => $code,
            'message' => 'Spark Master not reachable',
        ];
    }

    /** @var mixed $json */
    $json = json_decode((string) $resp, true);

    if (!is_array($json)) {
        return [
            'ok' => true,
            'reachable' => true,
            'raw' => (string) $resp,
        ];
    }

    return [
        'ok' => true,
        'reachable' => true,
        'status' => $json['status'] ?? 'unknown',
        'workers' => $json['workers'] ?? [],
        'alive_workers' => $json['aliveworkers'] ?? 0,
        'cores' => $json['cores'] ?? 0,
        'cores_used' => $json['coresused'] ?? 0,
        'memory' => $json['memory'] ?? 0,
        'memory_used' => $json['memoryused'] ?? 0,
        'active_apps' => $json['activeapps'] ?? [],
        'completed_apps' => $json['completedapps'] ?? [],
    ];
}

/**
 * Check if Spark cluster is ready for TFoS jobs.
 *
 * @return array<string, mixed>
 */
function spark_health_check(): array
{
    $config = spark_get_config();

    // Check if Spark binaries exist
    $sparkSubmit = $config['bin'] . '/spark-submit';
    if (!is_file($sparkSubmit)) {
        return [
            'healthy' => false,
            'error' => 'spark_not_installed',
            'spark_home' => $config['spark_home'],
            'message' => 'spark-submit not found at ' . $sparkSubmit,
        ];
    }

    // Get cluster status
    $status = spark_get_cluster_status();

    $healthy = $status['ok'] && ($status['alive_workers'] ?? 0) > 0;

    return [
        'healthy' => $healthy,
        'spark_home' => $config['spark_home'],
        'master' => $config['master'],
        'cluster_mode' => $config['cluster_mode'],
        'reachable' => $status['reachable'] ?? false,
        'alive_workers' => $status['alive_workers'] ?? 0,
        'total_cores' => $status['cores'] ?? 0,
        'cores_used' => $status['cores_used'] ?? 0,
        'memory_mb' => $status['memory'] ?? 0,
        'memory_used_mb' => $status['memory_used'] ?? 0,
        'active_apps' => count($status['active_apps'] ?? []),
    ];
}

// ---------------------------------------------------------------------------
// Spark Submit Helpers
// ---------------------------------------------------------------------------

/**
 * Run a Spark application.
 *
 * @param string $script Python script to run
 * @param array<string> $args Script arguments
 * @param array<string, mixed> $sparkConf Spark configuration
 * @return array<string, mixed>
 */
function spark_submit(string $script, array $args = [], array $sparkConf = []): array
{
    $config = spark_get_config();
    $sparkSubmit = $config['bin'] . '/spark-submit';

    if (!is_file($sparkSubmit)) {
        return ['ok' => false, 'error' => 'spark_not_installed'];
    }

    if (!is_file($script)) {
        return ['ok' => false, 'error' => 'script_not_found', 'script' => $script];
    }

    $cmdParts = [$sparkSubmit];

    // Master
    $cmdParts[] = '--master';
    $cmdParts[] = $config['master'];

    // Add Spark conf
    $defaultConf = [
        'spark.cores.max' => (string) ($config['worker_instances'] * $config['cores_per_worker']),
        'spark.task.cpus' => (string) $config['cores_per_worker'],
    ];

    foreach (array_merge($defaultConf, $sparkConf) as $key => $value) {
        $cmdParts[] = '--conf';
        $cmdParts[] = $key . '=' . $value;
    }

    // Add classpath if set
    if ($config['classpath'] !== '') {
        $cmdParts[] = '--jars';
        $cmdParts[] = $config['classpath'];
    }

    // Script
    $cmdParts[] = $script;

    // Script arguments
    foreach ($args as $arg) {
        $cmdParts[] = $arg;
    }

    // Build command
    $cmd = implode(' ', array_map('escapeshellarg', $cmdParts));

    // Execute
    $output = [];
    $rc = 0;
    $startTime = microtime(true);
    exec($cmd . ' 2>&1', $output, $rc);
    $duration = microtime(true) - $startTime;

    return [
        'ok' => $rc === 0,
        'exit_code' => $rc,
        'duration_sec' => round($duration, 2),
        'output' => implode("\n", $output),
    ];
}

/**
 * Get environment variables for TFoS Spark job.
 *
 * @return array<string, string>
 */
function spark_get_tfos_env(): array
{
    $config = spark_get_config();

    return [
        'SPARK_HOME' => $config['spark_home'],
        'MASTER' => $config['master'],
        'SPARK_WORKER_INSTANCES' => (string) $config['worker_instances'],
        'CORES_PER_WORKER' => (string) $config['cores_per_worker'],
        'TOTAL_CORES' => (string) ($config['worker_instances'] * $config['cores_per_worker']),
        'SPARK_CLASSPATH' => $config['classpath'],
    ];
}

// ---------------------------------------------------------------------------
// YARN Integration
// ---------------------------------------------------------------------------

/**
 * Check YARN cluster status (for YARN mode).
 *
 * @return array<string, mixed>
 */
function yarn_get_cluster_status(): array
{
    $yarnBin = getenv('YARN_HOME') ?: getenv('HADOOP_HOME');
    if (!$yarnBin) {
        return ['ok' => false, 'error' => 'yarn_not_configured'];
    }

    $cmd = $yarnBin . '/bin/yarn node -list 2>&1';
    $output = [];
    $rc = 0;
    exec($cmd, $output, $rc);

    return [
        'ok' => $rc === 0,
        'exit_code' => $rc,
        'output' => implode("\n", $output),
    ];
}

// ---------------------------------------------------------------------------
// Kubernetes Integration
// ---------------------------------------------------------------------------

/**
 * Check Kubernetes Spark operator status.
 *
 * @return array<string, mixed>
 */
function k8s_get_spark_status(): array
{
    $namespace = getenv('SPARK_K8S_NAMESPACE') ?: 'spark';

    $cmd = sprintf(
        'kubectl get sparkapplications -n %s -o json 2>&1',
        escapeshellarg($namespace)
    );

    $output = [];
    $rc = 0;
    exec($cmd, $output, $rc);

    if ($rc !== 0) {
        return ['ok' => false, 'error' => 'kubectl_failed', 'output' => implode("\n", $output)];
    }

    /** @var mixed $json */
    $json = json_decode(implode("\n", $output), true);

    return [
        'ok' => true,
        'namespace' => $namespace,
        'applications' => is_array($json) ? ($json['items'] ?? []) : [],
    ];
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

/**
 * Wait for cluster to be ready with timeout.
 *
 * @param int $timeoutSec Maximum seconds to wait
 * @param int $intervalSec Check interval
 * @return array<string, mixed>
 */
function spark_wait_for_cluster(int $timeoutSec = 60, int $intervalSec = 5): array
{
    $start = time();
    $attempts = 0;

    while (time() - $start < $timeoutSec) {
        $attempts++;
        $health = spark_health_check();

        if ($health['healthy']) {
            return [
                'ok' => true,
                'attempts' => $attempts,
                'elapsed_sec' => time() - $start,
                'health' => $health,
            ];
        }

        sleep($intervalSec);
    }

    return [
        'ok' => false,
        'error' => 'timeout',
        'attempts' => $attempts,
        'elapsed_sec' => time() - $start,
        'last_health' => spark_health_check(),
    ];
}
