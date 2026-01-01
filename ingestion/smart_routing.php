<?php

declare(strict_types=1);

/**
 * Smart routing module for intelligent webhook distribution.
 *
 * Provides:
 * - Load balancing across multiple endpoints
 * - Automatic failover to backup targets
 * - Priority-based routing
 * - Health-based routing decisions
 * - Round-robin and least-connections algorithms
 * - Retry with exponential backoff
 * - Circuit breaker pattern
 *
 * Usage:
 *   $router = new SmartRouter($config);
 *   $result = $router->route($payload, $routingKey);
 */

class RoutingTarget
{
    public string $name;
    public string $url;
    public int $priority = 5;  // 1-10, higher = more priority
    public int $weight = 1;     // For weighted round-robin
    public bool $enabled = true;
    public bool $backup = false;  // Only use if primary targets fail
    public int $timeoutSeconds = 15;
    public array $headers = [];
    public int $healthCheckFailures = 0;
    public ?float $lastHealthCheck = null;
    public float $avgResponseTime = 0.0;
    public int $activeConnections = 0;

    public function __construct(array $config)
    {
        $this->name = $config['name'] ?? 'unnamed';
        $this->url = $config['url'] ?? '';
        $this->priority = $config['priority'] ?? 5;
        $this->weight = max(1, $config['weight'] ?? 1);
        $this->enabled = $config['enabled'] ?? true;
        $this->backup = $config['backup'] ?? false;
        $this->timeoutSeconds = max(1, $config['timeout_seconds'] ?? 15);
        $this->headers = $config['headers'] ?? [];
    }

    public function isHealthy(): bool
    {
        // Circuit breaker: disable if too many failures
        return $this->enabled && $this->healthCheckFailures < 5;
    }

    public function recordSuccess(float $responseTimeMs): void
    {
        $this->healthCheckFailures = max(0, $this->healthCheckFailures - 1);
        // Exponential moving average
        $alpha = 0.3;
        $this->avgResponseTime = $alpha * $responseTimeMs + (1 - $alpha) * $this->avgResponseTime;
    }

    public function recordFailure(): void
    {
        $this->healthCheckFailures++;
    }
}

class RoutingStrategy
{
    const ROUND_ROBIN = 'round_robin';
    const LEAST_CONNECTIONS = 'least_connections';
    const WEIGHTED_ROUND_ROBIN = 'weighted_round_robin';
    const PRIORITY_BASED = 'priority_based';
    const FASTEST_RESPONSE = 'fastest_response';
}

class SmartRouter
{
    private array $targets = [];
    private string $strategy;
    private int $roundRobinIndex = 0;
    private int $maxRetries = 3;
    private float $retryBackoffMultiplier = 2.0;
    private int $initialRetryDelayMs = 100;
    private bool $enableCircuitBreaker = true;
    private int $circuitBreakerThreshold = 5;

    public function __construct(array $config = [])
    {
        $this->strategy = $config['strategy'] ?? RoutingStrategy::PRIORITY_BASED;
        $this->maxRetries = $config['max_retries'] ?? 3;
        $this->retryBackoffMultiplier = $config['retry_backoff_multiplier'] ?? 2.0;
        $this->initialRetryDelayMs = $config['initial_retry_delay_ms'] ?? 100;
        $this->enableCircuitBreaker = $config['enable_circuit_breaker'] ?? true;
        $this->circuitBreakerThreshold = $config['circuit_breaker_threshold'] ?? 5;

        // Load targets
        $targets = $config['targets'] ?? [];
        foreach ($targets as $targetConfig) {
            $target = new RoutingTarget($targetConfig);
            $this->targets[$target->name] = $target;
        }
    }

    public function addTarget(RoutingTarget $target): void
    {
        $this->targets[$target->name] = $target;
    }

    public function route(array $payload, ?string $routingKey = null, array $options = []): array
    {
        $startTime = microtime(true);
        $attempts = [];

        // Get available targets
        $availableTargets = $this->getAvailableTargets($routingKey);

        if (empty($availableTargets)) {
            return [
                'ok' => false,
                'error' => 'no_healthy_targets',
                'attempted_count' => 0,
                'elapsed_ms' => 0,
            ];
        }

        // Try primary targets first
        $primaryTargets = array_filter($availableTargets, fn($t) => !$t->backup);
        $backupTargets = array_filter($availableTargets, fn($t) => $t->backup);

        $result = $this->tryTargets($primaryTargets, $payload, $attempts);

        // If all primary targets fail, try backup targets
        if (!$result['ok'] && !empty($backupTargets)) {
            $result = $this->tryTargets($backupTargets, $payload, $attempts);
        }

        $elapsedMs = (int)((microtime(true) - $startTime) * 1000);

        return [
            'ok' => $result['ok'],
            'target' => $result['target'] ?? null,
            'response' => $result['response'] ?? null,
            'error' => $result['error'] ?? null,
            'attempts' => $attempts,
            'attempted_count' => count($attempts),
            'elapsed_ms' => $elapsedMs,
            'strategy' => $this->strategy,
        ];
    }

    private function getAvailableTargets(?string $routingKey): array
    {
        $targets = array_filter($this->targets, fn($t) => $t->isHealthy());

        if (empty($targets)) {
            return [];
        }

        // Sort based on strategy
        switch ($this->strategy) {
            case RoutingStrategy::PRIORITY_BASED:
                usort($targets, fn($a, $b) => $b->priority - $a->priority);
                break;

            case RoutingStrategy::LEAST_CONNECTIONS:
                usort($targets, fn($a, $b) => $a->activeConnections - $b->activeConnections);
                break;

            case RoutingStrategy::FASTEST_RESPONSE:
                usort($targets, fn($a, $b) => $a->avgResponseTime <=> $b->avgResponseTime);
                break;

            case RoutingStrategy::WEIGHTED_ROUND_ROBIN:
                // Expand targets by weight for selection
                $weighted = [];
                foreach ($targets as $target) {
                    for ($i = 0; $i < $target->weight; $i++) {
                        $weighted[] = $target;
                    }
                }
                if (!empty($weighted)) {
                    $this->roundRobinIndex = ($this->roundRobinIndex + 1) % count($weighted);
                    $selected = $weighted[$this->roundRobinIndex];
                    // Move selected to front
                    $targets = array_filter($targets, fn($t) => $t->name === $selected->name);
                    $targets = array_merge($targets, array_filter($this->targets, fn($t) => $t->name !== $selected->name && $t->isHealthy()));
                }
                break;

            case RoutingStrategy::ROUND_ROBIN:
            default:
                $this->roundRobinIndex = ($this->roundRobinIndex + 1) % count($targets);
                $targets = array_values($targets);
                // Rotate array
                $selected = $targets[$this->roundRobinIndex];
                $targets = array_merge([$selected], array_filter($targets, fn($t) => $t->name !== $selected->name));
                break;
        }

        return array_values($targets);
    }

    private function tryTargets(array $targets, array $payload, array &$attempts): array
    {
        foreach ($targets as $target) {
            $result = $this->tryTargetWithRetry($target, $payload, $attempts);
            if ($result['ok']) {
                return $result;
            }
        }

        return [
            'ok' => false,
            'error' => 'all_targets_failed',
        ];
    }

    private function tryTargetWithRetry(RoutingTarget $target, array $payload, array &$attempts): array
    {
        $retryDelay = $this->initialRetryDelayMs;

        for ($attempt = 1; $attempt <= $this->maxRetries; $attempt++) {
            $attemptStart = microtime(true);

            $result = $this->sendToTarget($target, $payload);

            $attemptElapsedMs = (int)((microtime(true) - $attemptStart) * 1000);

            $attempts[] = [
                'target' => $target->name,
                'attempt' => $attempt,
                'ok' => $result['ok'],
                'http_code' => $result['http_code'] ?? null,
                'elapsed_ms' => $attemptElapsedMs,
                'error' => $result['error'] ?? null,
            ];

            if ($result['ok']) {
                $target->recordSuccess((float)$attemptElapsedMs);
                return [
                    'ok' => true,
                    'target' => $target->name,
                    'response' => $result,
                    'attempts_needed' => $attempt,
                ];
            }

            // Record failure
            $target->recordFailure();

            // Check if we should retry
            if ($attempt < $this->maxRetries) {
                // Exponential backoff
                usleep($retryDelay * 1000);
                $retryDelay = (int)($retryDelay * $this->retryBackoffMultiplier);
            }
        }

        return [
            'ok' => false,
            'target' => $target->name,
            'error' => 'max_retries_exceeded',
        ];
    }

    private function sendToTarget(RoutingTarget $target, array $payload): array
    {
        $target->activeConnections++;

        try {
            $ch = curl_init($target->url);
            if ($ch === false) {
                return ['ok' => false, 'error' => 'curl_init_failed'];
            }

            $body = json_encode($payload, JSON_UNESCAPED_SLASHES);
            if (!is_string($body)) {
                $body = '{}';
            }

            $headers = [
                'Content-Type: application/json',
                'Accept: application/json',
                'User-Agent: cxflow-smart-router/1.0',
            ];
            foreach ($target->headers as $k => $v) {
                $k = trim((string)$k);
                if ($k !== '') {
                    $headers[] = $k . ': ' . (string)$v;
                }
            }

            curl_setopt_array($ch, [
                CURLOPT_POST => true,
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_FOLLOWLOCATION => true,
                CURLOPT_MAXREDIRS => 2,
                CURLOPT_CONNECTTIMEOUT => min(10, max(1, $target->timeoutSeconds)),
                CURLOPT_TIMEOUT => max(1, $target->timeoutSeconds),
                CURLOPT_HTTPHEADER => $headers,
                CURLOPT_POSTFIELDS => $body,
            ]);

            $resp = curl_exec($ch);
            $errno = curl_errno($ch);
            $err = curl_error($ch);
            $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
            curl_close($ch);

            if ($resp === false) {
                return [
                    'ok' => false,
                    'http_code' => $code,
                    'curl_errno' => $errno,
                    'error' => $err
                ];
            }

            return [
                'ok' => $code >= 200 && $code < 300,
                'http_code' => $code,
                'response_body' => $resp,
            ];
        } finally {
            $target->activeConnections--;
        }
    }

    public function getTargetHealth(): array
    {
        $health = [];
        foreach ($this->targets as $name => $target) {
            $health[$name] = [
                'enabled' => $target->enabled,
                'healthy' => $target->isHealthy(),
                'failures' => $target->healthCheckFailures,
                'avg_response_ms' => round($target->avgResponseTime, 2),
                'active_connections' => $target->activeConnections,
                'priority' => $target->priority,
                'backup' => $target->backup,
            ];
        }
        return $health;
    }

    public function resetTargetHealth(string $name): bool
    {
        if (!isset($this->targets[$name])) {
            return false;
        }

        $this->targets[$name]->healthCheckFailures = 0;
        $this->targets[$name]->enabled = true;
        return true;
    }
}

/**
 * Helper function to create and configure a smart router from environment.
 */
function create_smart_router_from_env(): SmartRouter
{
    $strategy = getenv('CX_ROUTER_STRATEGY') ?: RoutingStrategy::PRIORITY_BASED;
    $maxRetries = (int)(getenv('CX_ROUTER_MAX_RETRIES') ?: 3);

    $config = [
        'strategy' => $strategy,
        'max_retries' => $maxRetries,
        'retry_backoff_multiplier' => (float)(getenv('CX_ROUTER_RETRY_BACKOFF') ?: 2.0),
        'initial_retry_delay_ms' => (int)(getenv('CX_ROUTER_INITIAL_DELAY_MS') ?: 100),
        'enable_circuit_breaker' => true,
        'circuit_breaker_threshold' => (int)(getenv('CX_ROUTER_CIRCUIT_THRESHOLD') ?: 5),
        'targets' => [],
    ];

    // Load targets from environment variable
    $targetsJson = getenv('CX_ROUTER_TARGETS_JSON');
    if ($targetsJson) {
        $targets = json_decode($targetsJson, true);
        if (is_array($targets)) {
            $config['targets'] = $targets;
        }
    }

    return new SmartRouter($config);
}
